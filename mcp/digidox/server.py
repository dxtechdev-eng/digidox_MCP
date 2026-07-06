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


def _inject_permission_filter(sql: str, perm: dict) -> str:
    """쿼리에서 doc/form 테이블 참조를 권한 필터링된 서브쿼리로 교체"""
    import re

    if not perm or perm.get("level", 0) >= 100:
        return sql  # admin/master: 필터 없음

    allowed_docs = perm.get("allowed_docSeqs")
    allowed_forms = perm.get("allowed_formSeqs")

    # doc 테이블 필터링
    if allowed_docs is not None:
        doc_ids = ",".join(str(s) for s in allowed_docs) if allowed_docs else "-1"
        # FROM doc, JOIN doc 패턴을 서브쿼리로 교체 (대소문자 무시)
        sql = re.sub(
            r'\b(FROM|JOIN)\s+doc\b(?!\w)',
            rf'\1 (SELECT * FROM doc WHERE seq IN ({doc_ids})) doc',
            sql, flags=re.IGNORECASE
        )

    # form 테이블 필터링
    if allowed_forms is not None:
        form_ids = ",".join(str(s) for s in allowed_forms) if allowed_forms else "-1"
        sql = re.sub(
            r'\b(FROM|JOIN)\s+form\b(?!\w)',
            rf'\1 (SELECT * FROM form WHERE seq IN ({form_ids})) form',
            sql, flags=re.IGNORECASE
        )

    return sql


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

    # 권한 필터 주입
    user_id = current_user.get()
    import logging
    logging.getLogger(__name__).info(f"[PERM] user_id={user_id}, sql_before={stripped[:100]}")
    if user_id:
        from digidox.auth import get_permissions
        perm = get_permissions(user_id)
        stripped = _inject_permission_filter(stripped, perm)

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(stripped)
        rows = cursor.fetchall()
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
