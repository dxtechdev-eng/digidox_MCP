import configparser
import os

_ini_path = os.path.join(os.path.dirname(__file__), "..", "config.ini")
_cfg = configparser.ConfigParser()
_cfg.read(_ini_path, encoding="utf-8")

# DigiDox
DIGIDOX_BASE_URL = _cfg.get("digidox", "base_url", fallback="https://new.digidox.co.kr")
DIGIDOX_AUTH_KEY = _cfg.get("digidox", "auth_key", fallback="")
DIGIDOX_PDF_PATH = _cfg.get("digidox", "pdf_path", fallback="/service/api/onlypdf.do")
DIGIDOX_IMAGE_PATH = _cfg.get("digidox", "image_path", fallback="/service/doc/call/bg.do")
DIGIDOX_FORM_PATH = _cfg.get("digidox", "form_path", fallback="/service/api/jsonforform.do")
DIGIDOX_SAVE_PATH = _cfg.get("digidox", "save_path", fallback="/service/api/savedata.do")

# Server
SERVER_HOST = _cfg.get("server", "host", fallback="0.0.0.0")
SERVER_PORT = _cfg.getint("server", "port", fallback=7001)

# OCR
DEFAULT_MAX_TOKENS = _cfg.getint("ocr", "default_max_tokens", fallback=4096)

# Ollama (로컬)
OLLAMA_URL = _cfg.get("ollama", "url", fallback="http://127.0.0.1:11434")
OLLAMA_MODEL = _cfg.get("ollama", "model", fallback="gemma4:26b")
# Ollama (원격 — spark 서버, Vision API 프록시용)
OLLAMA_REMOTE_URL = _cfg.get("ollama", "remote_url", fallback="http://192.168.10.104:11435")
OLLAMA_REMOTE_MODEL = _cfg.get("ollama", "remote_model", fallback="qwen3.6:35b-a3b")

# OpenAI
OPENAI_API_KEY = _cfg.get("openai", "api_key", fallback="")
