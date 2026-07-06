"""
MCP 인증 미들웨어 — JWT 기반 + 권한 캐싱
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

# 사용자별 권한 캐시: { user_id: { memberSeq, level, groupSeq, allowed_formSeqs, allowed_docSeqs } }
_permission_cache = {}

# 현재 요청의 사용자 ID (미들웨어에서 설정, 도구 함수에서 참조)
_current_user_id = None


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


def load_permissions(user_id: str) -> dict:
    """사용자의 권한 정보를 DB에서 조회하여 캐싱"""
    conn = _get_db()
    try:
        cursor = conn.cursor()

        # 1. memberSeq, level 조회
        cursor.execute("SELECT seq, level FROM member WHERE id = %s AND status = 1", (user_id,))
        member = cursor.fetchone()
        if not member:
            return {}

        member_seq = member["seq"]
        level = member["level"]

        # admin/master (level >= 100): 전체 접근
        if level >= 100:
            perm = {
                "memberSeq": member_seq,
                "level": level,
                "groupSeq": None,
                "allowed_formSeqs": None,  # None = 전체
                "allowed_docSeqs": None,   # None = 전체
            }
            _permission_cache[user_id] = perm
            return perm

        # 2. 소속 그룹 조회
        cursor.execute("SELECT groupSeq FROM ongroupmember WHERE memberSeq = %s", (member_seq,))
        group_row = cursor.fetchone()
        group_seq = group_row["groupSeq"] if group_row else None

        # 3. 허용 폼 목록
        allowed_form_seqs = set()
        if group_seq:
            cursor.execute("SELECT formSeq FROM ongroupform WHERE groupSeq = %s", (group_seq,))
            allowed_form_seqs = {r["formSeq"] for r in cursor.fetchall()}

        # 4. 허용 문서 목록
        allowed_doc_seqs = set()
        if group_seq:
            if level == 0:
                # 외부 사용자: doOpen=1인 문서만
                cursor.execute("""
                    SELECT d.seq FROM doc d
                    JOIN addondoc a ON a.docSeq = d.seq
                    JOIN ongroupmember gm ON a.memberSeq = gm.memberSeq
                    WHERE gm.groupSeq = %s AND a.doOpen = 1 AND d.status > 0
                """, (group_seq,))
            else:
                # 일반 사용자 (level 50): 그룹 내 모든 문서
                cursor.execute("""
                    SELECT d.seq FROM doc d
                    JOIN addondoc a ON a.docSeq = d.seq
                    JOIN ongroupmember gm ON a.memberSeq = gm.memberSeq
                    WHERE gm.groupSeq = %s AND d.status > 0
                """, (group_seq,))
            allowed_doc_seqs = {r["seq"] for r in cursor.fetchall()}

        perm = {
            "memberSeq": member_seq,
            "level": level,
            "groupSeq": group_seq,
            "allowed_formSeqs": allowed_form_seqs,
            "allowed_docSeqs": allowed_doc_seqs,
        }
        _permission_cache[user_id] = perm
        return perm

    finally:
        conn.close()


def get_current_user() -> str | None:
    """현재 요청의 사용자 ID 반환"""
    return _current_user_id


def get_permissions(user_id: str) -> dict:
    """캐시에서 권한 조회. 없으면 DB에서 로드."""
    if user_id not in _permission_cache:
        load_permissions(user_id)
    return _permission_cache.get(user_id, {})


def clear_permission_cache(user_id: str = None):
    """권한 캐시 초기화"""
    if user_id:
        _permission_cache.pop(user_id, None)
    else:
        _permission_cache.clear()


async def login(request: Request):
    """POST /auth/login — ID/PW 검증 후 JWT 발급 + 권한 캐싱"""
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

    # 권한 캐싱
    load_permissions(user_id)

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

    EXEMPT_PATHS = {"/auth/login"}

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        if path in self.EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

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

        scope["auth"] = payload

        # 전역 변수에 현재 사용자 설정 (MCP 도구에서 접근용)
        global _current_user_id
        _current_user_id = payload.get("sub")

        await self.app(scope, receive, send)
