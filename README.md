# DigiDox MCP Server

DigiDox API 기반 MCP(Model Context Protocol) 서버입니다.
Claude Code에서 자연어로 DigiDox 문서/폼 데이터를 조회할 수 있습니다.

## 설치

```bash
pip install git+https://<TOKEN>@github.com/dxtechdev-eng/digidox_MCP.git
```

> `<TOKEN>` 부분은 GitHub Personal Access Token으로 교체하세요.

## 환경변수 설정

| 환경변수 | 설명 | 기본값 |
|---------|------|--------|
| DIGIDOX_API_URL | DigiDox API 서버 주소 | https://cloud.digidox.co.kr |
| DIGIDOX_USER_ID | DigiDox 로그인 ID | (필수) |
| DIGIDOX_PASSWORD | DigiDox 로그인 비밀번호 | (필수) |

## Claude Code 등록

프로젝트 루트 또는 `~/.claude/` 에 `.mcp.json` 파일을 생성합니다.

```json
{
  "mcpServers": {
    "digidox": {
      "command": "digidox-mcp",
      "env": {
        "DIGIDOX_API_URL": "https://cloud.digidox.co.kr",
        "DIGIDOX_USER_ID": "your_id",
        "DIGIDOX_PASSWORD": "your_password"
      }
    }
  }
}
```

등록 후 Claude Code를 재시작(VS Code: `Ctrl+Shift+P` → `Reload Window`)하면 적용됩니다.

## 사용 가능한 도구

### search_documents
문서 목록을 검색합니다. keyword로 문서정보, 메모, 필드 데이터 등에서 검색합니다.

### get_document_detail
문서 상세 정보를 조회합니다. 필드 데이터를 포함합니다.

### get_form_info
폼(양식) 정보를 조회합니다. 필드 정의, 좌표, 프롬프트 등을 포함합니다.

### download_pdf
문서의 PDF를 다운로드합니다.

**사용 예시 (Claude Code에서):**

- "최신 문서 목록 보여줘"
- "YAMATO 키워드로 문서 검색해줘"
- "12345번 문서 상세 정보 확인해줘"
- "TM-3 폼 정보 조회해줘"

## 보안

- DigiDox 계정 인증 기반 (API 서버를 통한 간접 조회)
- DB 직접 연결 없음
- 비밀번호는 환경변수로 관리
