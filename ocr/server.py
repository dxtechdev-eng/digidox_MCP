import base64
import io
import json
import logging
import os
import re
from urllib.parse import parse_qs

import fitz  # PyMuPDF
import httpx
from PIL import Image
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
import uvicorn

import config
from prompt_builder import extract_fields_by_page, build_auto_prompt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("server.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI OCR Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 뷰어 정적 파일
VIEWER_DIR = os.path.join(os.path.dirname(__file__), "viewer")
if os.path.exists(os.path.join(VIEWER_DIR, "static")):
    app.mount("/viewer/static", StaticFiles(directory=os.path.join(VIEWER_DIR, "static")), name="viewer_static")

# 모든 요청 로깅
@app.middleware("http")
async def log_all_requests(request: Request, call_next):
    body = await request.body()
    logger.info(f"\n{'='*60}\n[요청] {request.method} {request.url}\nquery: {dict(request.query_params)}\nheaders: {dict(request.headers)}\nbody: {body.decode('utf-8', errors='replace')[:500]}\n{'='*60}")
    response = await call_next(request)
    return response

# OCR 결과 캐시 (seq → 결과)
ocr_cache = {}


# ============================================================
# DigiDox API
# ============================================================

def download_pdf(seq: str) -> bytes:
    url = f"{config.DIGIDOX_BASE_URL}{config.DIGIDOX_PDF_PATH}"
    response = httpx.post(url, data={"authKey": config.DIGIDOX_AUTH_KEY, "seq": seq}, timeout=30)
    response.raise_for_status()
    return response.content


def get_form_info(formid: str) -> dict:
    url = f"{config.DIGIDOX_BASE_URL}{config.DIGIDOX_FORM_PATH}"
    response = httpx.post(url, data={"authKey": config.DIGIDOX_AUTH_KEY, "id": formid}, timeout=30)
    response.raise_for_status()
    data = response.json()
    logger.info(f"폼 정보 조회: formid={formid}, code={data.get('code')}")
    logger.info(f"폼 OCR 설정: ocrEngine={data.get('ocrEngine')}, ocrApiUrl={data.get('ocrApiUrl')}, ocrApiKey={'있음' if data.get('ocrApiKey') else '없음'}, ocrModel={data.get('ocrModel')}, promptInfo={'있음' if data.get('promptInfo') else '없음'}")
    return data


def save_ocr_result(seq: str, ocr_data: dict, form_info: dict) -> bool:
    pages = form_info.get("pages", [])
    save_pages = []
    for page in pages:
        page_no = page.get("pageNo") or page.get("idx", 0)
        fields = page.get("fields", {})
        save_fields = {}
        for field_id in fields:
            if field_id in ocr_data:
                save_fields[field_id] = {"data": ocr_data[field_id]}
        save_pages.append({"pageNo": page_no, "fields": save_fields})

    save_json = {
        "code": "100",
        "message": "OK",
        "formId": form_info.get("formId"),
        "seq": int(seq),
        "pages": save_pages,
    }

    url = f"{config.DIGIDOX_BASE_URL}{config.DIGIDOX_SAVE_PATH}"
    response = httpx.post(url, data={
        "authKey": config.DIGIDOX_AUTH_KEY,
        "seq": seq,
        "json": json.dumps(save_json, ensure_ascii=False),
    }, timeout=30)
    response.raise_for_status()
    result = response.json()
    logger.info(f"OCR 결과 저장: seq={seq}, response={result}")
    return result.get("code") == "100"


# ============================================================
# PDF / 이미지 처리
# ============================================================

def pdf_to_images(pdf_bytes: bytes) -> list[str]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        b64 = base64.b64encode(pix.tobytes("png")).decode("utf-8")
        images.append(b64)
    doc.close()
    return images


def pdf_to_pil_image(pdf_bytes: bytes, page_idx: int = 0) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_idx]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    doc.close()
    return img


def crop_field(img: Image.Image, field_info: dict, form_width: float, form_height: float) -> str:
    img_w, img_h = img.size
    scale_x = img_w / form_width
    scale_y = img_h / form_height
    top = (field_info.get("top") or 0) * scale_y
    left = (field_info.get("left") or 0) * scale_x
    width = (field_info.get("width") or 0) * scale_x
    height = (field_info.get("height") or 0) * scale_y
    padding = 2
    x1 = max(0, left - padding)
    y1 = max(0, top - padding)
    x2 = min(img_w, left + width + padding)
    y2 = min(img_h, top + height + padding)
    cropped = img.crop((x1, y1, x2, y2))
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ============================================================
# OCR 엔진 분기
# ============================================================

def ocr_with_openai(images: list[str], prompt: str, api_url: str, api_key: str, model: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=api_url.rstrip("/") + "/v1" if "/v1" not in api_url else api_url)
    content = [{"type": "text", "text": prompt}]
    for b64_img in images:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}})
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        max_tokens=config.DEFAULT_MAX_TOKENS,
    )
    return response.choices[0].message.content


def ocr_with_anthropic(images: list[str], prompt: str, api_key: str, model: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    content = []
    for b64_img in images:
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64_img}})
    content.append({"type": "text", "text": prompt})
    response = client.messages.create(
        model=model,
        max_tokens=config.DEFAULT_MAX_TOKENS,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text


def ocr_with_ollama(images: list[str], prompt: str, api_url: str, model: str) -> str:
    url = api_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt, "images": images}],
        "stream": False,
    }
    response = httpx.post(url, json=payload, timeout=None)
    response.raise_for_status()
    return response.json().get("message", {}).get("content", "")


def run_ocr_engine(images: list[str], prompt: str, engine: str, api_url: str, api_key: str, model: str) -> str:
    logger.info(f"OCR 엔진: {engine}, 모델: {model}, API: {api_url}")
    if engine == "openai":
        return ocr_with_openai(images, prompt, api_url, api_key, model)
    elif engine == "anthropic":
        return ocr_with_anthropic(images, prompt, api_key, model)
    elif engine == "ollama":
        return ocr_with_ollama(images, prompt, api_url, model)
    else:
        raise ValueError(f"Unknown OCR engine: {engine}")


# ============================================================
# 셀 단위 OCR (필드 좌표 기반)
# ============================================================

def ocr_cells_with_engine(cell_images: dict, engine: str, api_url: str, api_key: str, model: str, field_types: dict = None) -> dict:
    """셀 이미지를 배치로 OCR 엔진에 전송"""
    results = {}
    field_ids = list(cell_images.keys())
    BATCH_SIZE = 10

    for i in range(0, len(field_ids), BATCH_SIZE):
        batch_ids = field_ids[i:i + BATCH_SIZE]

        # 필드 타입 힌트 생성
        hints = []
        for fid in batch_ids:
            ftype = (field_types or {}).get(fid, "text")
            if ftype == "int":
                hints.append(f'"{fid}": "number only"')
            elif ftype == "check":
                hints.append(f'"{fid}": "✓ or empty"')
            elif ftype == "hiragana":
                hints.append(f'"{fid}": "hiragana only"')
            else:
                hints.append(f'"{fid}": "text"')

        prompt = f"""The following {len(batch_ids)} images are cropped cells from a document.
Read the handwritten text in each cell. If empty, return empty string.
Ignore printed labels or fixed text. Read only handwritten parts.

Return in JSON format only. No explanations or markdown.
Images correspond to {json.dumps(batch_ids)} in order.

{{
{','.join(hints)}
}}"""

        batch_images = [cell_images[fid] for fid in batch_ids]

        try:
            text = run_ocr_engine(batch_images, prompt, engine, api_url, api_key, model)
            match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
            if match:
                text = match[1].strip()
            batch_result = json.loads(text)
            results.update(batch_result)
            logger.info(f"배치 OCR 완료: {batch_ids}")
        except Exception as e:
            logger.error(f"배치 OCR 실패: {batch_ids}, {e}")
            for fid in batch_ids:
                results[fid] = ""

    return results




# ============================================================
# API 엔드포인트
# ============================================================

@app.get("/api/image")
async def get_image(seq: str = None, idx: int = 1, key: str = None):
    if key and not seq:
        try:
            decoded = base64.b64decode(key).decode("utf-8")
            params = parse_qs(decoded)
            seq = params.get("seq", [None])[0]
        except Exception:
            pass
    if not seq:
        return Response(content="seq is required", status_code=400)
    url = f"{config.DIGIDOX_BASE_URL}{config.DIGIDOX_IMAGE_PATH}"
    response = httpx.get(url, params={"docSeq": seq, "idx": idx}, timeout=30)
    response.raise_for_status()
    return Response(content=response.content, media_type=response.headers.get("content-type", "image/png"))


@app.get("/api/fields")
async def get_fields(formid: str, page: int = 1):
    try:
        form_info = get_form_info(formid)
        for p in form_info.get("pages", []):
            page_no = p.get("pageNo") or p.get("idx", 0)
            if page_no == page:
                return {
                    "resultCode": "200",
                    "fields": p.get("fields", {}),
                    "formWidth": p.get("width", 700),
                    "formHeight": p.get("height", 990),
                }
        return {"resultCode": "200", "fields": {}, "formWidth": 700, "formHeight": 990}
    except Exception as e:
        return {"resultCode": "500", "resultMsg": str(e)}


@app.post("/api/generate-prompt")
async def generate_prompt(request: Request):
    """폼 정보를 기반으로 OCR 프롬프트를 자동 생성"""
    body = await request.json()
    formid = body.get("formid")
    lang = body.get("lang", "en")
    logger.info(f"프롬프트 생성 요청: formid={formid}, lang={lang}")

    if not formid:
        return {"resultCode": "400", "resultMsg": "formid is required"}

    try:
        form_info = get_form_info(formid)
        if form_info.get("code") not in ("100", "200"):
            return {"resultCode": "404", "resultMsg": f"Form not found: {formid}"}

        fields_by_page = extract_fields_by_page(form_info)
        if not fields_by_page:
            return {"resultCode": "404", "resultMsg": "No fields found in form"}

        prompt_parts = []
        for page_no, sorted_fields in sorted(fields_by_page.items()):
            prompt_parts.append(build_auto_prompt(sorted_fields, lang, formid))

        return {"resultCode": "200", "promptInfo": "\n".join(prompt_parts)}
    except Exception as e:
        logger.error(f"프롬프트 생성 실패: {e}")
        return {"resultCode": "500", "resultMsg": str(e)}


@app.get("/api/local-ocr")
async def local_ocr(seq: str, formid: str = None):
    """inputType=6 필드만 로컬 LLM(Ollama)으로 OCR 처리"""
    logger.info(f"로컬 OCR 요청: seq={seq}, formid={formid}")

    try:
        # 1. 폼 정보에서 inputType=6 필드만 추출
        form_info = get_form_info(formid) if formid else None
        if not form_info:
            return {"resultCode": "400", "resultMsg": "formid 필요"}

        ocr_fields = {}
        form_w, form_h = 700, 990
        for page in form_info.get("pages", []):
            if (page.get("pageNo") or page.get("idx", 0)) != 1:
                continue
            form_w = page.get("width", 700)
            form_h = page.get("height", 990)
            for fid, info in page.get("fields", {}).items():
                if info.get("inputType") == 6:
                    ocr_fields[fid] = info

        if not ocr_fields:
            return {"resultCode": "200", "resultMsg": "OCR 대상 필드 없음", "ocrResult": "{}"}

        logger.info(f"inputType=6 필드 {len(ocr_fields)}개: {list(ocr_fields.keys())}")

        # 2. PDF → 이미지
        pdf_bytes = download_pdf(seq)
        img = pdf_to_pil_image(pdf_bytes, 0)

        # 3. 대상 필드만 crop
        cell_images = {}
        for fid, info in ocr_fields.items():
            try:
                cell_images[fid] = crop_field(img, info, form_w, form_h)
            except Exception as e:
                logger.warning(f"셀 crop 실패: {fid}, {e}")

        # 4. 로컬 LLM(Ollama)으로 OCR
        results = {}
        for fid, b64_img in cell_images.items():
            prompt = "Read the handwritten text in this image. Return only the text. If empty, return nothing."
            try:
                text = ocr_with_ollama([b64_img], prompt, config.OLLAMA_URL, config.OLLAMA_MODEL)
                results[fid] = text.strip()
                logger.info(f"로컬 OCR: {fid} = {text.strip()}")
            except Exception as e:
                logger.error(f"로컬 OCR 실패: {fid}, {e}")
                results[fid] = ""

        logger.info(f"로컬 OCR 완료: {json.dumps(results, ensure_ascii=False)}")

        return {
            "resultCode": "200",
            "resultMsg": "OK",
            "ocrResult": json.dumps(results, ensure_ascii=False),
        }

    except Exception as e:
        logger.error(f"로컬 OCR 실패: {e}", exc_info=True)
        return {
            "resultCode": "500",
            "resultMsg": str(e),
            "ocrResult": None,
        }


@app.get("/api/ocr")
async def api_ocr(seq: str = None, formid: str = None, force: bool = False, key: str = None):
    # base64 key 디코딩
    if key and not seq:
        try:
            decoded = base64.b64decode(key).decode("utf-8")
            params = parse_qs(decoded)
            seq = params.get("seq", [None])[0]
            formid = formid or params.get("formid", [None])[0]
        except Exception as e:
            logger.error(f"key 디코딩 실패: {e}")

    if not seq:
        return {"resultCode": "400", "resultMsg": "seq is required"}

    logger.info(f"OCR 요청: seq={seq}, formid={formid}, force={force}")

    if not force and seq in ocr_cache:
        logger.info(f"캐시 반환: seq={seq}")
        cached = ocr_cache[seq]
        return {
            "resultCode": "200",
            "resultMsg": "OK (cached)",
            "seq": seq,
            "formid": formid,
            "pages": cached["pages"],
            "ocrResult": cached["ocrResult"],
        }

    try:
        # 1. 폼 정보
        form_info = None
        ocr_settings = {}
        if formid:
            try:
                form_info = get_form_info(formid)
                ocr_settings = {
                    "engine": form_info.get("ocrEngine", "openai"),
                    "api_url": form_info.get("ocrApiUrl", "https://api.openai.com"),
                    "api_key": form_info.get("ocrApiKey", ""),
                    "model": form_info.get("ocrModel", "gpt-4o"),
                }
            except Exception as e:
                logger.warning(f"폼 정보 조회 실패: {e}")

        # engine = ocr_settings.get("engine", "openai")
        # api_url = ocr_settings.get("api_url", "https://api.openai.com")
        # api_key = ocr_settings.get("api_key", "")
        # model = ocr_settings.get("model", "gpt-4o")

        # 로컬 LLM 테스트용 — Ollama 기본 엔진
        engine = "ollama"
        api_url = config.OLLAMA_URL
        api_key = ""
        model = config.OLLAMA_MODEL

        # 2. PDF 다운로드
        logger.info(f"PDF 다운로드 중... seq={seq}")
        pdf_bytes = download_pdf(seq)
        logger.info(f"PDF 다운로드 완료: {len(pdf_bytes)} bytes")

        # 3. OCR 방식 결정 — 필드 좌표가 있으면 셀 단위, 없으면 전체 이미지
        page1_fields = {}
        form_w, form_h = 700, 990
        if form_info:
            fields_by_page = extract_fields_by_page(form_info)
            page1_fields_list = fields_by_page.get(1, [])
            if page1_fields_list:
                page1_fields = {fid: info for fid, info in page1_fields_list}
                for p in form_info.get("pages", []):
                    if (p.get("pageNo") or p.get("idx", 0)) == 1:
                        form_w = p.get("width", 700)
                        form_h = p.get("height", 990)
                        break

        writable_fields = {
            fid: info for fid, info in page1_fields.items()
            if info.get("canWrite", 0) == 1
            and info.get("top") is not None
            and info.get("left") is not None
            and fid not in ["S.PAGE_NO", "S.SEQ", "S.QRCODE"]
        }

        if writable_fields:
            # 셀 단위 OCR
            logger.info(f"셀 단위 OCR: {len(writable_fields)}개 필드")
            img = pdf_to_pil_image(pdf_bytes, 0)
            cell_images = {}
            for fid, info in writable_fields.items():
                try:
                    cell_images[fid] = crop_field(img, info, form_w, form_h)
                except Exception as e:
                    logger.warning(f"셀 crop 실패: {fid}, {e}")

            # 필드 타입 (description 기반 — 향후 DigiDox에서 전달)
            field_types = {}
            for fid, info in writable_fields.items():
                desc = info.get("description", "")
                if desc:
                    field_types[fid] = desc
                # TODO: DigiDox에서 inputType/description으로 타입 전달 시 여기서 매핑

            ocr_result = ocr_cells_with_engine(cell_images, engine, api_url, api_key, model, field_types)
            ocr_text = json.dumps(ocr_result, ensure_ascii=False)
            page_count = 1
        else:
            # 전체 이미지 OCR
            logger.info("전체 이미지 OCR")
            images = pdf_to_images(pdf_bytes)
            page_count = len(images)

            prompt = None
            if form_info:
                prompt_info = form_info.get("promptInfo", "")
                if page1_fields_list and prompt_info:
                    prompt = prompt_info + build_auto_prompt(page1_fields_list, "ja")
                elif prompt_info:
                    prompt = prompt_info

            if not prompt:
                prompt = "Read all handwritten text in this image and return in JSON format."

            ocr_text = run_ocr_engine(images, prompt, engine, api_url, api_key, model)

        logger.info(f"OCR 완료\n--- OCR 결과 ---\n{ocr_text[:500]}\n--- 끝 ---")

        ocr_cache[seq] = {"pages": page_count, "ocrResult": ocr_text}

        return {
            "resultCode": "200",
            "resultMsg": "OK",
            "seq": seq,
            "formid": formid,
            "pages": page_count,
            "ocrResult": ocr_text,
        }

    except Exception as e:
        logger.error(f"OCR 실패: {e}", exc_info=True)
        return {
            "resultCode": "500",
            "resultMsg": str(e),
            "seq": seq,
            "formid": formid,
            "ocrResult": None,
        }


@app.post("/api/generate-prompt")
async def generate_prompt(request: Request):
    body = await request.body()
    params = json.loads(body)
    formid = params.get("formid")
    lang = params.get("lang", "ja")

    logger.info(f"프롬프트 생성 요청: formid={formid}, lang={lang}")

    try:
        form_info = get_form_info(formid)
        fields_by_page = extract_fields_by_page(form_info)
        all_fields = []
        for page_no in sorted(fields_by_page.keys()):
            all_fields.extend(fields_by_page[page_no])

        if not all_fields:
            return {"resultCode": "400", "resultMsg": "No fields found", "promptInfo": ""}

        prompt = build_auto_prompt(all_fields, lang, form_info.get("formName", ""))
        logger.info(f"프롬프트 생성 완료: {len(prompt)}자")
        return {"resultCode": "200", "resultMsg": "OK", "formid": formid, "promptInfo": prompt}

    except Exception as e:
        logger.error(f"프롬프트 생성 실패: {e}", exc_info=True)
        return {"resultCode": "500", "resultMsg": str(e), "promptInfo": ""}


@app.post("/api/save")
async def save_ocr(request: Request):
    body = await request.body()
    params = json.loads(body)
    seq = params.get("seq")
    formid = params.get("formid")
    ocr_data = params.get("ocrData")

    logger.info(f"저장 요청: seq={seq}, formid={formid}")

    try:
        form_info = get_form_info(formid)
        save_ocr_result(seq, ocr_data, form_info)
        return {"resultCode": "200", "resultMsg": "Saved"}
    except Exception as e:
        logger.error(f"저장 실패: {e}", exc_info=True)
        return {"resultCode": "500", "resultMsg": str(e)}


@app.get("/", response_class=HTMLResponse)
async def viewer(request: Request):
    """범용 OCR 오버레이 뷰어"""
    template_path = os.path.join(VIEWER_DIR, "templates", "index.html")
    if os.path.exists(template_path):
        with open(template_path, encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Viewer template not found</h1>", status_code=404)


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    logger.info(f"AI OCR Server 시작 - http://{config.SERVER_HOST}:{config.SERVER_PORT}")
    uvicorn.run(app, host=config.SERVER_HOST, port=config.SERVER_PORT)
