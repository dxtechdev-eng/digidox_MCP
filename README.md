# DigiDox MCP Server

DigiDox DB 조회용 MCP(Model Context Protocol) 서버입니다.
Claude Code에서 자연어로 DigiDox 문서/폼 데이터를 조회할 수 있습니다.

## 설치

```bash
pip install git+https://dxtechdev-eng:<TOKEN>@github.com/dxtechdev-eng/digidox_MCP.git
```

> `<TOKEN>` 부분은 GitHub Personal Access Token으로 교체하세요.

## 환경변수 설정

DB 접속 정보를 환경변수로 설정해야 합니다.

| 환경변수 | 설명 | 기본값 |
|---------|------|--------|
| DIGIDOX_DB_HOST | DB 호스트 | 127.0.0.1 |
| DIGIDOX_DB_PORT | DB 포트 | 3306 |
| DIGIDOX_DB_USER | DB 사용자 | (필수) |
| DIGIDOX_DB_PASSWORD | DB 비밀번호 | (필수) |
| DIGIDOX_DB_NAME | DB 이름 | (필수) |

### Windows 환경변수 설정 방법

시스템 환경변수에 추가하거나, `.mcp.json`의 `env`에 설정:

```json
{
  "mcpServers": {
    "digidox": {
      "command": "digidox-mcp",
      "env": {
        "DIGIDOX_DB_HOST": "192.168.10.4",
        "DIGIDOX_DB_PORT": "3306",
        "DIGIDOX_DB_USER": "digidox",
        "DIGIDOX_DB_PASSWORD": "your_password",
        "DIGIDOX_DB_NAME": "digidox_cloud_prod"
      }
    }
  }
}
```

## Claude Code 등록

프로젝트 루트 또는 `~/.claude/` 에 `.mcp.json` 파일을 생성합니다.

### 방법 1: pip 설치 후 (권장)

```json
{
  "mcpServers": {
    "digidox": {
      "command": "digidox-mcp",
      "env": {
        "DIGIDOX_DB_HOST": "192.168.10.4",
        "DIGIDOX_DB_PORT": "3306",
        "DIGIDOX_DB_USER": "digidox",
        "DIGIDOX_DB_PASSWORD": "your_password",
        "DIGIDOX_DB_NAME": "digidox_cloud_prod"
      }
    }
  }
}
```

### 방법 2: Python 경로 직접 지정

```json
{
  "mcpServers": {
    "digidox": {
      "command": "python",
      "args": ["-m", "digidox.server"],
      "env": {
        "DIGIDOX_DB_HOST": "192.168.10.4",
        "DIGIDOX_DB_PORT": "3306",
        "DIGIDOX_DB_USER": "digidox",
        "DIGIDOX_DB_PASSWORD": "your_password",
        "DIGIDOX_DB_NAME": "digidox_cloud_prod"
      }
    }
  }
}
```

등록 후 Claude Code를 재시작(VS Code: `Ctrl+Shift+P` → `Reload Window`)하면 적용됩니다.

## 사용 가능한 도구

### query

DigiDox DB에 SELECT 쿼리를 실행합니다.

**주요 테이블:**

| 테이블 | 설명 | 주요 컬럼 |
|--------|------|----------|
| doc | 문서 | seq, formSeq, pageCnt, status, memo, insDt, updDt |
| form | 폼/양식 | seq, id, name, class, version, isOcr, promptInfo |
| docfield | 문서 필드 데이터 | docSeq, id, data, writeData, podData, editData |
| formfield | 폼 필드 정의 | formSeq, id, description, top, left, width, height |
| docpage | 문서 페이지 | |
| formpage | 폼 페이지 | |
| member | 사용자 | |
| stroke | 필기 데이터 | |
| apikeymgr | API 키 관리 | |

**사용 예시 (Claude Code에서):**

- "최근 7일간 올라온 문서 보여줘"
- "TM-3 폼의 필드 목록 조회해줘"
- "12345번 문서 상세 정보 확인해줘"
- "YAMATO 키워드로 문서 검색해줘"

## 보안

- **SELECT 쿼리만 허용** — INSERT, UPDATE, DELETE, DROP 등 차단
- DB 비밀번호는 환경변수로 관리 (코드에 하드코딩 금지)
