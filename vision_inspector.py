# -*- coding: utf-8 -*-
"""
vision_inspector.py - Mắt Thần Công Trường Su Su (Vision AI)
============================================================
Chức năng:
1. Tiếp nhận và phân tích hình ảnh hiện trường, hồ sơ gửi qua Telegram / Zalo:
   - Phiếu cân vật tư / Hóa đơn bê tông thương phẩm (Bill of Lading).
   - Biên bản nghiệm thu công việc / Nhật ký thi công viết tay.
   - Bản vẽ kỹ thuật / Shopdrawing kết cấu, kiến trúc, MEP.
   - Ảnh chụp sự cố, lỗi thi công (Defect), vi phạm an toàn (HSE).
2. Ứng dụng mô hình Gemini Multimodal (Gemini Flash) phân tích độ chính xác cao.
3. Trích xuất dữ liệu có cấu trúc, cảnh báo rủi ro và sinh các nút bấm hành động 1 chạm.
4. Lưu trữ lịch sử giám định vào Data/field_inspections.json.
"""

from __future__ import annotations

import os
import sys
import json
import base64
import time
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import requests

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent.parent

if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

try:
    from consult_expert import get_google_ultra_api_key, is_valid_gemini_key, ULTRA_MODELS_PRIORITY
except ImportError:
    try:
        from qshien.desktop_assistant.consult_expert import get_google_ultra_api_key, is_valid_gemini_key, ULTRA_MODELS_PRIORITY
    except ImportError:
        def get_google_ultra_api_key(): return os.environ.get("GEMINI_API_KEY", "")
        def is_valid_gemini_key(k): return bool(k and len(k) > 20)
        ULTRA_MODELS_PRIORITY = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]


def _get_data_dir() -> Path:
    candidates = [
        CURRENT_DIR / "Data",
        CURRENT_DIR,
        REPO_ROOT / "Data",
        REPO_ROOT.parent / "Data",
        Path(r"C:\QS_Hien\Data")
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return CURRENT_DIR

DATA_DIR = _get_data_dir()
INSPECTIONS_LOG = DATA_DIR / "field_inspections.json"


PROMPT_VISION_ANALYSIS = """
Bạn là "Su Su" - Trợ lý Kỹ thuật & Cố vấn Trưởng cho Giám đốc Dự án Xây dựng (Dự án Vietstar 344 Tỷ và các công trình dân dụng/công nghiệp).
Hãy phân tích bức ảnh công trường/hồ sơ này với con mắt của một Kỹ sư Trưởng kiêm Chuyên gia Quản lý Chất lượng (QA/QC) và Giám sát Hiện trường dày dạn kinh nghiệm.

Ảnh có thể là một trong 4 loại sau:
1. [PHIEU_CAN] Phiếu cân vật tư (thép, cát, đá, xi măng) hoặc Phiếu giao nhận bê tông thương phẩm (Delivery Ticket).
2. [BIEN_BAN] Biên bản kiểm tra cốt thép/cốp pha/nghiệm thu công việc xây dựng hoặc trang nhật ký thi công viết tay/đánh máy.
3. [BAN_VE] Bản vẽ thiết kế kỹ thuật, shopdrawing, mặt bằng kết cấu, chi tiết thép, sơ đồ MEP.
4. [HIEN_TRUONG] Ảnh chụp sự cố, lỗi kỹ thuật thi công (rỗ bê tông, nứt sàn, cốt thép sai khoảng cách, cốp pha phình bụng, vi phạm an toàn lao động HSE).
5. [KHAC] Văn bản hoặc tài liệu công trường khác.

YÊU CẦU ĐẶC BIỆT:
Hãy trả lời dưới dạng JSON thuần túy (không bọc trong thẻ ```json ... ``` nếu có thể, hoặc bọc chuẩn) với cấu trúc sau:
{
  "category": "PHIEU_CAN" | "BIEN_BAN" | "BAN_VE" | "HIEN_TRUONG" | "KHAC",
  "category_name": "Tên loại ảnh tiếng Việt",
  "summary": "Tóm tắt ngắn gọn 1-2 câu về nội dung cốt lõi của ảnh",
  "structured_data": {
    // Nếu là Phiếu cân/Giao nhận:
    "supplier": "Tên nhà cung cấp (nếu đọc được)",
    "ticket_number": "Số phiếu",
    "vehicle_plate": "Biển số xe",
    "material": "Tên vật tư / Mác bê tông / Độ sụt",
    "net_weight": "Khối lượng tịnh / Khối lượng giao (tấn hoặc m3)",
    "dispatch_time": "Giờ xuất trạm / Giờ đến công trường",
    "slump": "Độ sụt thiết kế / thực tế",
    // Nếu là Biên bản:
    "work_name": "Tên hạng mục nghiệm thu",
    "location": "Vị trí / Trục / Tầng / Phân đoạn",
    "inspection_date": "Ngày nghiệm thu",
    "participants": "Thành phần tham gia (TVGS, Nhà thầu, CĐT)",
    "result": "ĐẠT | KHÔNG ĐẠT | YÊU CẦU SỬA CHỮA",
    // Nếu là Lỗi hiện trường:
    "defect_type": "Loại lỗi (Nứt, Rỗ, Lệch thép, HSE...)",
    "location_hint": "Vị trí suy đoán hoặc trục nhận diện được",
    "severity": "CAO | TRUNG BINH | THAP"
  },
  "risk_assessment": "Đánh giá rủi ro về chất lượng, tiến độ hoặc pháp lý nghiệm thu",
  "expert_action": "Hành động khuyến nghị cụ thể cho Kỹ sư / GĐDA xử lý ngay",
  "suggested_task_title": "Tên công việc đề xuất nếu cần tạo Task VST (ngắn gọn, dưới 60 ký tự)"
}
"""


def analyze_construction_image(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    caption: str = "",
    context: str = ""
) -> Dict[str, Any]:
    """
    Phân tích ảnh công trường bằng Gemini Vision API.
    """
    if not image_bytes or len(image_bytes) < 100:
        return {
            "success": False,
            "error": "Dữ liệu ảnh rỗng hoặc không hợp lệ.",
            "category": "KHAC"
        }

    api_key = get_google_ultra_api_key()
    if not is_valid_gemini_key(api_key):
        return {
            "success": False,
            "error": "Chưa cấu hình Google Gemini API Key hợp lệ.",
            "category": "KHAC"
        }

    # Chuyển ảnh sang base64
    b64_img = base64.b64encode(image_bytes).decode("ascii")

    full_prompt = PROMPT_VISION_ANALYSIS
    if caption:
        full_prompt += f"\n\nChú thích của người gửi: \"{caption}\""
    if context:
        full_prompt += f"\nBối cảnh trao đổi trước đó: \"{context}\""

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": full_prompt},
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": b64_img
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.95,
            "maxOutputTokens": 3000
        }
    }

    headers = {"Content-Type": "application/json"}
    raw_response_text = ""
    last_err = ""

    # Thử qua danh sách model ưu tiên
    for model_name in ULTRA_MODELS_PRIORITY:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=40)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        raw_response_text = parts[0]["text"].strip()
                        break
            else:
                last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            last_err = str(e)
            continue

    if not raw_response_text:
        return {
            "success": False,
            "error": f"Không nhận được phản hồi từ AI ({last_err})",
            "category": "KHAC"
        }

    # Bóc tách JSON từ raw_response_text
    clean_json_str = raw_response_text.strip()
    if clean_json_str.startswith("```json"):
        clean_json_str = clean_json_str[7:]
    elif clean_json_str.startswith("```"):
        clean_json_str = clean_json_str[3:]
    if clean_json_str.endswith("```"):
        clean_json_str = clean_json_str[:-3]
    clean_json_str = clean_json_str.strip()

    parsed_result: Dict[str, Any] = {}
    try:
        parsed_result = json.loads(clean_json_str)
    except Exception:
        # Nếu AI trả về text kèm giải thích, thử tìm khối JSON
        import re
        m = re.search(r"\{[\s\S]*\}", clean_json_str)
        if m:
            try:
                parsed_result = json.loads(m.group(0))
            except Exception:
                pass

    if not parsed_result:
        # Fallback text thuần nếu parse JSON lỗi
        parsed_result = {
            "category": "HIEN_TRUONG",
            "category_name": "Hiện trường / Hồ sơ Công trường",
            "summary": raw_response_text[:300],
            "risk_assessment": "Cần kiểm tra trực tiếp hiện trường.",
            "expert_action": raw_response_text,
            "structured_data": {}
        }

    parsed_result["success"] = True
    parsed_result["raw_text"] = raw_response_text

    # Tạo định dạng Markdown đẹp cho Telegram/Zalo
    parsed_result["telegram_message"] = format_vision_telegram_message(parsed_result)
    parsed_result["inline_keyboard"] = build_vision_action_keyboard(parsed_result)

    # Ghi nhận vào file log giám định
    _log_inspection_record(parsed_result, caption)

    return parsed_result


def format_vision_telegram_message(result: Dict[str, Any]) -> str:
    """Định dạng bản tin Telegram phong cách Kỹ sư Trưởng."""
    cat = result.get("category", "KHAC")
    cat_name = result.get("category_name") or "Ảnh Công Trường"
    summary = result.get("summary", "")
    struct = result.get("structured_data", {})
    risk = result.get("risk_assessment", "")
    action = result.get("expert_action", "")

    header_icon = {
        "PHIEU_CAN": "⚖️ 📋",
        "BIEN_BAN": "📝 📑",
        "BAN_VE": "📐 🏛️",
        "HIEN_TRUONG": "🚨 📸",
        "KHAC": "🔍 📄"
    }.get(cat, "🔍 📄")

    lines = [
        f"{header_icon} *MẮT THẦN SU SU — GIÁM ĐỊNH HÌNH ẢNH*",
        f"🏷️ *Phân loại:* `{cat_name}`\n",
        f"📌 *Tóm tắt:* {summary}\n"
    ]

    # Chi tiết theo từng loại
    if cat == "PHIEU_CAN":
        lines.append("📊 *THÔNG TIN GIAO NHẬN / PHIẾU CÂN:*")
        if struct.get("supplier"): lines.append(f"• *Nhà cung cấp:* {struct['supplier']}")
        if struct.get("ticket_number"): lines.append(f"• *Số phiếu:* `{struct['ticket_number']}`")
        if struct.get("vehicle_plate"): lines.append(f"• *Biển số xe:* `{struct['vehicle_plate']}`")
        if struct.get("material"): lines.append(f"• *Chủng loại:* {struct['material']}")
        if struct.get("net_weight"): lines.append(f"• *Khối lượng:* *{struct['net_weight']}*")
        if struct.get("slump"): lines.append(f"• *Độ sụt:* {struct['slump']}")
        if struct.get("dispatch_time"): lines.append(f"• *Thời gian:* {struct['dispatch_time']}")
        lines.append("")

    elif cat == "BIEN_BAN":
        lines.append("📑 *THÔNG TIN BIÊN BẢN / NGHIỆM THU:*")
        if struct.get("work_name"): lines.append(f"• *Công việc:* {struct['work_name']}")
        if struct.get("location"): lines.append(f"• *Vị trí:* `{struct['location']}`")
        if struct.get("inspection_date"): lines.append(f"• *Ngày kiểm tra:* {struct['inspection_date']}")
        if struct.get("participants"): lines.append(f"• *Thành phần:* {struct['participants']}")
        if struct.get("result"):
            res_str = struct['result']
            icon = "✅" if "ĐẠT" in res_str.upper() else "⚠️"
            lines.append(f"• *Kết luận:* {icon} *{res_str}*")
        lines.append("")

    elif cat == "HIEN_TRUONG":
        lines.append("🚨 *ĐÁNH GIÁ SỰ VỤ HIỆN TRƯỜNG:*")
        if struct.get("defect_type"): lines.append(f"• *Khiếm khuyết:* {struct['defect_type']}")
        if struct.get("location_hint"): lines.append(f"• *Vị trí nhận diện:* `{struct['location_hint']}`")
        if struct.get("severity"):
            sev = struct['severity']
            sev_icon = "🔴" if "CAO" in sev.upper() else ("🟡" if "TRUNG" in sev.upper() else "🟢")
            lines.append(f"• *Mức độ nghiêm trọng:* {sev_icon} *{sev}*")
        lines.append("")

    if risk:
        lines.append(f"⚠️ *ĐÁNH GIÁ RỦI RO:*\n_{risk}_\n")

    if action:
        lines.append(f"🛠️ *HÀNH ĐỘNG KHUYẾN NGHỊ:*\n{action}\n")

    lines.append("💡 _Chọn các nút bấm bên dưới để tự động ghi sổ hoặc giao việc:_")
    return "\n".join(lines)


def build_vision_action_keyboard(result: Dict[str, Any]) -> Dict[str, Any]:
    """Tạo bàn phím Inline Buttons tương ứng với kết quả giám định ảnh."""
    cat = result.get("category", "KHAC")
    task_title = result.get("suggested_task_title") or result.get("summary") or "Kiểm tra hiện trường"
    # Giới hạn độ dài callback_data (Telegram giới hạn 64 bytes)
    short_task = task_title[:30].replace(":", "-").replace("|", "-")
    now_ts = int(time.time())

    keyboard = []

    if cat == "PHIEU_CAN":
        keyboard.append([
            {"text": "📊 Lưu Khối Lượng Vật Tư", "callback_data": f"vis_mat:{now_ts}"},
            {"text": "⚡ Tính Hao Hụt Bê Tông", "callback_data": f"vis_calc:{now_ts}"}
        ])
    elif cat == "BIEN_BAN":
        keyboard.append([
            {"text": "✅ Ghi Nhận Đạt Nghiệm Thu", "callback_data": f"vis_ok:{now_ts}"},
            {"text": "📁 Lưu Hồ Sơ Chất Lượng", "callback_data": f"vis_arch:{now_ts}"}
        ])
    elif cat == "HIEN_TRUONG":
        keyboard.append([
            {"text": "🚨 Tạo Task Sửa Chữa (VST)", "callback_data": f"vis_task:{now_ts}"},
            {"text": "📍 Định Vị Trục Trên CAD", "callback_data": f"vis_cad:{now_ts}"}
        ])
    else:
        keyboard.append([
            {"text": "📝 Tạo Việc Cần Làm (VST)", "callback_data": f"vis_task:{now_ts}"},
            {"text": "🔍 Hỏi Thêm Về Bức Ảnh", "callback_data": f"vis_ask:{now_ts}"}
        ])

    keyboard.append([
        {"text": "🌸 Menu Chính", "callback_data": "main_menu"},
        {"text": "⚡ Báo Cáo 17h30", "callback_data": "digest_now"}
    ])

    return {"inline_keyboard": keyboard}


def _log_inspection_record(record: Dict[str, Any], caption: str = ""):
    """Lưu lịch sử giám định vào JSON."""
    try:
        INSPECTIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
        items = []
        if INSPECTIONS_LOG.exists():
            try:
                with open(INSPECTIONS_LOG, "r", encoding="utf-8") as f:
                    items = json.load(f)
                    if not isinstance(items, list): items = []
            except Exception:
                items = []

        entry = {
            "id": f"INSP-{int(time.time())}",
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "caption": caption,
            "category": record.get("category"),
            "summary": record.get("summary"),
            "structured_data": record.get("structured_data"),
            "risk_assessment": record.get("risk_assessment"),
            "expert_action": record.get("expert_action")
        }
        items.insert(0, entry)
        items = items[:100]  # Giữ tối đa 100 lần giám định gần nhất

        with open(INSPECTIONS_LOG, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Vision Log Error] {e}")
