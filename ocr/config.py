import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# DigiDox
DIGIDOX_AUTH_KEY = os.getenv("DIGIDOX_AUTH_KEY", "")
DIGIDOX_BASE_URL = os.getenv("DIGIDOX_BASE_URL", "https://cloud.digidox.co.kr")
# TODO: 운영 시 DIGIDOX_BASE_URL 통일
DIGIDOX_INTERNAL_URL = os.getenv("DIGIDOX_INTERNAL_URL", "http://192.168.10.4:8990")
DIGIDOX_PDF_PATH = "/service/api/onlypdf.do"
DIGIDOX_IMAGE_PATH = "/service/doc/call/bg.do"
DIGIDOX_FORM_PATH = "/service/api/jsonforform.do"
DIGIDOX_SAVE_PATH = "/service/api/savedata.do"

# Server
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "7000"))

# Default OCR settings (폼에서 지정 안 된 경우 fallback)
DEFAULT_MAX_TOKENS = 4096

# Local LLM (Ollama)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:26b")
