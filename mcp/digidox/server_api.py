"""
DigiDox MCP Server - API 기반
"""
import configparser
import json
import os
import httpx
from mcp.server.fastmcp import FastMCP

_ini_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.ini")
_cfg = configparser.ConfigParser()
_cfg.read(_ini_path, encoding="utf-8")

mcp = FastMCP("DigiDox")

# 로그인 세션 캐시 (추후 만료 처리 등 보완)
_session: dict = {"token": None}


def get_config():
    return {
        "api_url": _cfg.get("digidox", "base_url", fallback="https://new.digidox.co.kr"),
        "user_id": _cfg.get("mcp", "user_id", fallback=""),
        "password": _cfg.get("mcp", "password", fallback=""),
        "login_path": _cfg.get("mcp", "login_path", fallback="/service/api/login.do"),
    }


def login() -> bool:
    """DigiDox 로그인 — 성공 시 True, 실패 시 False"""
    cfg = get_config()
    url = cfg["api_url"].rstrip("/") + cfg["login_path"]
    try:
        response = httpx.get(url, params={
            "userId": cfg["user_id"],
            "password": cfg["password"],
        }, timeout=10)
        response.raise_for_status()
        data = response.json()
        # TODO: 실제 응답 구조 확인 후 토큰/세션 파싱 교체
        _session["token"] = data.get("token") or data.get("authKey")
        return _session["token"] is not None
    except Exception:
        return False


def get_auth() -> dict:
    """현재 세션 토큰 반환. 없으면 로그인 시도."""
    if not _session["token"]:
        login()
    return {"authKey": _session["token"]}


def api_call(path: str, params: dict = None) -> dict:
    """DigiDox API 호출"""
    cfg = get_config()
    url = cfg["api_url"].rstrip("/") + path
    data = get_auth()
    if params:
        data.update(params)
    response = httpx.post(url, data=data, timeout=120)
    response.raise_for_status()
    return response.json()


@mcp.tool()
def search_documents(date_from: str, date_to: str, keyword: str = "", date_type: str = "insDt") -> str:
    """DigiDox 문서 목록을 조회합니다.
    날짜 범위는 필수이며, keyword로 추가 검색이 가능합니다.

    Args:
        date_from: 시작일 (YYYY-MM-DD)
        date_to: 종료일 (YYYY-MM-DD)
        keyword: 검색어 (선택, 문서정보/메모/필드데이터/HashTag/POD Data에서 검색)
        date_type: 날짜 기준 (insDt=생성일, updDt=수정일, 기본: insDt)
    """
    try:
        params = {
            "dateType": date_type,
            "dateFrom": date_from,
            "dateTo": date_to,
        }
        if keyword:
            params["keyword"] = keyword
        result = api_call("/service/api/jsons.do", params)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def get_document_detail(seq: int) -> str:
    """문서 상세 정보를 조회합니다. 문서의 필드 데이터를 포함합니다.

    Args:
        seq: 문서 번호
    """
    try:
        result = api_call("/service/api/json.do", {"seq": str(seq)})
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def get_form_info(formid: str) -> str:
    """폼(양식) 정보를 조회합니다. 필드 정의, 좌표, 프롬프트 등을 포함합니다.

    Args:
        formid: 폼 ID (예: TM-3, YAMATO_TEST-1)
    """
    try:
        result = api_call("/service/api/jsonforform.do", {"id": formid})
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def download_pdf(seq: int) -> str:
    """문서의 PDF 정보를 조회합니다.

    Args:
        seq: 문서 번호
    """
    import base64
    try:
        cfg = get_config()
        url = cfg["api_url"].rstrip("/") + "/service/api/onlypdf.do"
        response = httpx.post(url, data={
            "authKey": cfg["auth_key"],  # 임시, 추후 token으로 교체
            "seq": str(seq),
        }, timeout=30)
        response.raise_for_status()

        if response.headers.get("content-type", "").startswith("application/json"):
            return json.dumps(response.json(), ensure_ascii=False)

        return json.dumps({
            "seq": seq,
            "size": len(response.content),
            "message": f"PDF 다운로드 완료 ({len(response.content)} bytes)"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
