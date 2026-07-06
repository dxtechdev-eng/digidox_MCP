"""
DigiDox MCP Server
"""
import configparser
import json
import os
import pymysql
from mcp.server.fastmcp import FastMCP

BLOCKED_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE"]

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


@mcp.tool()
def query(sql: str) -> str:
    """DigiDox DB에 SELECT 쿼리를 실행합니다.

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
    from starlette.routing import Mount
    from starlette.applications import Starlette
    from digidox.auth import AuthMiddleware, auth_routes

    host = _cfg.get("mcp", "host", fallback="0.0.0.0")
    port = _cfg.getint("mcp", "port", fallback=8080)

    mcp_app = mcp.streamable_http_app()

    # auth 라우트 + MCP 앱을 합친 래퍼
    app = Starlette(
        routes=auth_routes + [Mount("/", app=mcp_app)],
    )
    app.add_middleware(AuthMiddleware)

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
