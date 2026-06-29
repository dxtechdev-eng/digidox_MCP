"""
프롬프트 자동생성
"""

LANG_CONFIG = {
    "ja": {
        "role": "あなたは産業文書専用のOCRエンジンです。",
        "instruction": "この画像は業務用文書です。手書きで記入された内容を正確に読み取ってください。",
        "rules": [
            "印刷されたラベル（項目名）と手書き文字を区別してください。ラベルは読み取り対象外です",
            "手書き文字のみ読み取り、そのまま正確に転記してください。内容の補正や修正は一切不要です",
            "読み取れない文字は「?」としてください",
            "空欄のフィールドは空文字\"\"としてください",
            "チェックボックス(□)にチェック(✓)が入っているものは\"✓\"、入っていないものは\"\"としてください",
        ],
        "row_label": "行",
        "output_instruction": "上記のフィールドIDをキーとして、JSON形式で結果を返してください。JSONのみ返してください。説明文やマークダウンは不要です。",
    },
    "ko": {
        "role": "당신은 산업 문서 전용 OCR 엔진입니다.",
        "instruction": "이 이미지는 업무용 문서입니다. 손글씨로 기입된 내용을 정확하게 읽어주세요.",
        "rules": [
            "인쇄된 라벨(항목명)과 손글씨를 구분하세요. 라벨은 읽기 대상이 아닙니다",
            "손글씨만 읽고 그대로 정확히 전사하세요. 내용의 보정이나 수정은 일절 불필요합니다",
            "읽을 수 없는 문자는 \"?\"로 표시하세요",
            "빈 필드는 빈 문자열 \"\"로 표시하세요",
            "체크박스(□)에 체크(✓)가 있으면 \"✓\", 없으면 \"\"로 표시하세요",
        ],
        "row_label": "행",
        "output_instruction": "위의 필드 ID를 키로 하여 JSON 형식으로 결과를 반환하세요. JSON만 반환하세요. 설명문이나 마크다운은 불필요합니다.",
    },
    "en": {
        "role": "You are an OCR engine specialized for industrial documents.",
        "instruction": "This image is a business document. Please accurately read all handwritten content.",
        "rules": [
            "Distinguish between printed labels (field names) and handwritten text. Labels are NOT reading targets",
            "Read only handwritten text and transcribe it exactly as-is. No corrections or modifications needed",
            "Use \"?\" for unreadable characters",
            "Use empty string \"\" for blank fields",
            "For checkboxes, use \"✓\" if checked, \"\" if not",
        ],
        "row_label": "Row",
        "output_instruction": "Return results in JSON format using the field IDs above as keys. Return JSON only. No explanations or markdown.",
    },
}


def extract_fields_by_page(form_info: dict) -> dict:
    result = {}
    for page in form_info.get("pages", []):
        page_no = page.get("pageNo") or page.get("idx", 0)
        fields = page.get("fields", {})
        if not fields:
            continue
        sorted_fields = sorted(
            fields.items(),
            key=lambda x: (x[1].get("top") or 0, x[1].get("left") or 0)
        )
        result[page_no] = sorted_fields
    return result


def build_auto_prompt(sorted_fields: list, lang: str, form_name: str = "") -> str:
    lc = LANG_CONFIG.get(lang, LANG_CONFIG["en"])
    ROW_THRESHOLD = 15
    rows, current_row, last_top = [], [], None

    for field_id, info in sorted_fields:
        top = info.get("top") or 0
        if last_top is None or abs(top - last_top) <= ROW_THRESHOLD:
            current_row.append((field_id, info))
        else:
            rows.append(current_row)
            current_row = [(field_id, info)]
        last_top = top
    if current_row:
        rows.append(current_row)

    layout_lines = []
    for i, row in enumerate(rows):
        parts = []
        for field_id, info in row:
            desc = info.get("description", "")
            left = info.get("left") or 0
            width = info.get("width") or 0
            height = info.get("height") or 0
            if desc:
                parts.append(f'"{field_id}" ({desc}, left={left}, width={width}, height={height})')
            else:
                parts.append(f'"{field_id}" (left={left}, width={width}, height={height})')
        layout_lines.append(f"{lc['row_label']}{i+1}: {' | '.join(parts)}")

    field_ids = [fid for fid, _ in sorted_fields]
    json_template = ",\n".join([f'  "{fid}": ""' for fid in field_ids])
    rules_text = "\n".join([f"- {r}" for r in lc["rules"]])

    return f"""{lc['role']}
{lc['instruction']}

■ Layout:
{chr(10).join(layout_lines)}

■ Rules:
{rules_text}

■ Output:
{lc['output_instruction']}

{{
{json_template}
}}
"""
