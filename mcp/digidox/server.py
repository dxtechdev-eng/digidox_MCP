"""
DigiDox MCP Server
"""
import configparser
import contextvars
import json
import os
import pymysql
from mcp.server.fastmcp import FastMCP

BLOCKED_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE"]

# 현재 요청의 사용자 ID (미들웨어에서 설정)
current_user = contextvars.ContextVar("current_user", default=None)

_ini_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.ini")
_cfg = configparser.ConfigParser()
_cfg.read(_ini_path, encoding="utf-8")

mcp = FastMCP("DigiDox", transport_security={"enable_dns_rebinding_protection": False})


def get_db_config():
    return {
        "host": _cfg.get("database", "host", fallback="127.0.0.1"),
        "port": _cfg.getint("database", "port", fallback=3306),
        "user": _cfg.get("database", "user", fallback=""),
        "password": _cfg.get("database", "password", fallback=""),
        "database": _cfg.get("database", "name", fallback=""),
        "charset": "utf8mb4",
    }


def get_db():
    return pymysql.connect(**get_db_config(), cursorclass=pymysql.cursors.DictCursor)


def serialize_rows(rows):
    for row in rows:
        for key, val in row.items():
            if hasattr(val, 'isoformat'):
                row[key] = val.isoformat()
            elif isinstance(val, bytes):
                row[key] = val.decode('utf-8', errors='replace')
    return rows


def _filter_rows_by_permission(rows: list, perm: dict) -> list:
    """쿼리 결과에서 권한 밖의 doc/form 행을 제거"""
    if not perm or perm.get("level", 0) >= 100:
        return rows  # admin/master: 필터 없음

    allowed_docs = perm.get("allowed_docSeqs")
    allowed_forms = perm.get("allowed_formSeqs")

    filtered = []
    for row in rows:
        # doc.seq 또는 docSeq 컬럼이 있으면 필터
        doc_seq = row.get("seq") or row.get("docSeq")
        if doc_seq is not None and allowed_docs is not None:
            if doc_seq not in allowed_docs:
                continue

        # formSeq 컬럼이 있으면 필터
        form_seq = row.get("formSeq")
        if form_seq is not None and allowed_forms is not None:
            if form_seq not in allowed_forms:
                continue

        filtered.append(row)
    return filtered


# 권한 제한 대상 테이블
_RESTRICTED_TABLES = {"doc", "form", "docfield", "docpage", "addondoc", "stroke", "strokepage"}


def _query_touches_restricted_table(sql_upper: str) -> bool:
    """쿼리가 권한 필터링 대상 테이블을 참조하는지 확인"""
    for table in _RESTRICTED_TABLES:
        if table.upper() in sql_upper:
            return True
    return False


@mcp.tool()
def query(sql: str) -> str:
    """DigiDox DB에 SELECT 쿼리를 실행합니다.
    사용자 권한에 따라 조회 가능한 문서/폼이 자동으로 필터링됩니다.

    주요 테이블:
    - doc: 문서 (seq, formSeq, pageCnt, status, memo, insDt, updDt)
    - form: 폼/양식 (seq, id, name, class, version, isOcr, promptInfo)
    - docfield: 문서 필드 데이터 (docSeq, id, data, writeData, podData, editData)
    - formfield: 폼 필드 정의 (formSeq, id, description, top, left, width, height, inputType)
    - docpage: 문서 페이지
    - formpage: 폼 페이지
    - member: 사용자
    - stroke: 필기 데이터
    - apikeymgr: API 키 관리

    Args:
        sql: 실행할 SELECT 쿼리
    """
    stripped = sql.strip()
    if not stripped.upper().startswith("SELECT"):
        return json.dumps({"error": "SELECT 쿼리만 허용됩니다."}, ensure_ascii=False)

    upper = stripped.upper()
    for blocked in BLOCKED_KEYWORDS:
        if blocked in upper:
            return json.dumps({"error": f"{blocked} 키워드가 포함된 쿼리는 실행할 수 없습니다."}, ensure_ascii=False)

    # 권한 확인
    user_id = current_user.get()
    perm = {}
    if user_id:
        from digidox.auth import get_permissions
        perm = get_permissions(user_id)

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(stripped)
        rows = cursor.fetchall()

        # 권한 제한 대상 테이블 쿼리면 필터링 적용
        if _query_touches_restricted_table(upper):
            rows = _filter_rows_by_permission(rows, perm)

        return json.dumps(serialize_rows(rows), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        conn.close()


def main():
    import uvicorn
    from starlette.routing import Route
    from digidox.auth import AuthMiddleware, login

    host = _cfg.get("mcp", "host", fallback="0.0.0.0")
    port = _cfg.getint("mcp", "port", fallback=8080)

    app = mcp.streamable_http_app()

    # 로그인 라우트 추가
    app.routes.insert(0, Route("/auth/login", login, methods=["POST"]))

    # 인증 미들웨어 적용
    app.add_middleware(AuthMiddleware)

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
