"""
MCP 인증 미들웨어 — JWT 기반
"""
import configparser
import os
from datetime import datetime, timedelta, timezone

import jwt
import pymysql
import bcrypt
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

_ini_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.ini")
_cfg = configparser.ConfigParser()
_cfg.read(_ini_path, encoding="utf-8")

JWT_SECRET = _cfg.get("auth", "jwt_secret", fallback="change-me-in-production")
JWT_EXPIRE_HOURS = _cfg.getint("auth", "jwt_expire_hours", fallback=24)


def _get_db():
    return pymysql.connect(
        host=_cfg.get("database", "host", fallback="127.0.0.1"),
        port=_cfg.getint("database", "port", fallback=3306),
        user=_cfg.get("database", "user", fallback=""),
        password=_cfg.get("database", "password", fallback=""),
        database=_cfg.get("database", "name", fallback=""),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


async def login(request: Request):
    """POST /auth/login — ID/PW 검증 후 JWT 발급"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    user_id = body.get("id", "")
    password = body.get("pw", "")

    if not user_id or not password:
        return JSONResponse({"error": "id and pw required"}, status_code=400)

    conn = _get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT pw, name, level, status FROM member WHERE id = %s", (user_id,))
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)

    if row["status"] != 1:
        return JSONResponse({"error": "Account disabled"}, status_code=403)

    stored_hash = row["pw"]
    if not stored_hash:
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)

    # bcrypt 검증 ($2y$ → $2b$ 호환 처리)
    hash_to_check = stored_hash.replace("$2y$", "$2b$")
    if not bcrypt.checkpw(password.encode("utf-8"), hash_to_check.encode("utf-8")):
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)

    # JWT 발급
    payload = {
        "sub": user_id,
        "name": row["name"],
        "level": row["level"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    return JSONResponse({
        "token": token,
        "user": {"id": user_id, "name": row["name"], "level": row["level"]},
    })


def verify_token(token: str) -> dict | None:
    """JWT 토큰 검증. 성공 시 payload 반환, 실패 시 None."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


class AuthMiddleware:
    """MCP 요청 전 JWT 검증 미들웨어"""

    # 인증 없이 접근 가능한 경로
    EXEMPT_PATHS = {"/auth/login"}

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # 인증 제외 경로
        if path in self.EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        # Authorization 헤더 확인
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("utf-8")

        if not auth_header.startswith("Bearer "):
            response = JSONResponse({"error": "Authorization required"}, status_code=401)
            await response(scope, receive, send)
            return

        token = auth_header[7:]
        payload = verify_token(token)

        if payload is None:
            response = JSONResponse({"error": "Invalid or expired token"}, status_code=401)
            await response(scope, receive, send)
            return

        # 인증 정보를 scope에 저장
        scope["auth"] = payload
        await self.app(scope, receive, send)


# 로그인 라우트
auth_routes = [
    Route("/auth/login", login, methods=["POST"]),
]
