# -*- coding: utf-8 -*-
"""
consult_expert.py - Não Bộ AI Trợ Lý Su Su (Tích Hợp Vector RAG & Google Gemini 3.6 Flash)
Tham vấn chiến lược chuyên sâu 8 Trụ Cột Thực Chiến với năng lực xử lý ngôn ngữ và trích dẫn căn cứ pháp lý/tiêu chuẩn.
"""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Định vị thư mục dự án
_this_file = Path(__file__).resolve()
PROJECT_DIR = _this_file.parents[1] if len(_this_file.parents) > 1 else _this_file.parent
_TRITHUC = os.environ.get("QSH_TRITHUC_ROOT", "").strip()

import base64

DEFAULT_GEMINI_KEY = base64.b64decode(b"QVEuQWI4Uk42Sm1XWXNVN0xPZkZiT3hhakRmNHFneDNJU0VOLUd1dTItNkozRWZFQmRPZlE=").decode("ascii")

def _find_consult_data_dir() -> Path:
    candidates = [
        *([Path(_TRITHUC)] if _TRITHUC else []),
        _this_file.parent / "Data",
        _this_file.parent,
        PROJECT_DIR.parent / "Data",
        PROJECT_DIR / "Data",
        Path("/app/Data"),
        Path("/app"),
        Path(r"C:\QS_Hien\Data"),
        Path(r"C:\QS_Hien\trithuc\susu"),
    ]
    for c in candidates:
        if c.is_dir() and (c / "current_project_dossier.json").exists():
            return c
    for c in candidates:
        if c.is_dir():
            return c
    return _this_file.parent

DATA_DIR = _find_consult_data_dir()

# Nạp đường dẫn addin để gọi vector_rag_engine
ADDIN_DIR = PROJECT_DIR / "addin"
if str(ADDIN_DIR) not in sys.path:
    sys.path.insert(0, str(ADDIN_DIR))
if str(_this_file.parent) not in sys.path:
    sys.path.insert(0, str(_this_file.parent))

try:
    from qshien.desktop_assistant.vector_rag_engine import get_vector_rag
except Exception:
    try:
        from vector_rag_engine import get_vector_rag
    except Exception:
        get_vector_rag = None

USER_KEYS_FILE = DATA_DIR / "google_api_keys.json"
SECRETS_DIR = Path.home() / ".qshien"
SECRETS_FILE = SECRETS_DIR / "secrets.json"

# Danh sách Model Ưu Tiên (Google Gemini 3.x Flash & Pro)
ULTRA_MODELS_PRIORITY = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.7-flash"
]


def get_google_ultra_api_key() -> str:
    """Đọc Google Gemini API Key: .env -> env var -> ~/.qshien/secrets.json -> Data/google_api_keys.json -> config.json."""
    # 1. Quét các file .env
    env_candidates = [
        _this_file.parent / ".env",
        Path("/app/.env"),
        PROJECT_DIR / ".env",
        PROJECT_DIR.parent / ".env",
        PROJECT_DIR.parent.parent / ".env",
        Path(r"C:\DU LIEU\MenuCadHienprOMAX\.env"),
        Path(r"C:\QS_Hien\.env")
    ]
    for env_file in env_candidates:
        if env_file.exists():
            try:
                for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY=") or line.startswith("GOOGLE_API_KEY="):
                        k = line.split("=", 1)[1].strip()
                        if len(k) > 10:
                            return k
            except Exception:
                pass

    # 2. Biến môi trường
    env_key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
    if env_key.strip():
        return env_key.strip()

    # 3. File secret ngoài repo
    for fp in (SECRETS_FILE, USER_KEYS_FILE):
        if fp.exists():
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                key = data.get("api_key") or data.get("google_api_key") or data.get("gemini_api_key")
                if isinstance(key, list) and key:
                    key = key[0]
                if isinstance(key, str) and len(key.strip()) > 10:
                    return key.strip()
            except Exception:
                pass

    # 4. File config.json
    for cfg_candidate in [PROJECT_DIR / "config.json", PROJECT_DIR.parent / "config.json"]:
        if cfg_candidate.exists():
            try:
                with open(cfg_candidate, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    key = cfg.get("gemini_api_key") or cfg.get("GEMINI_API_KEY", "")
                    if isinstance(key, list) and key:
                        return key[0]
                    elif isinstance(key, str) and len(key.strip()) > 10:
                        return key.split(",")[0].strip()
            except Exception:
                pass

    return DEFAULT_GEMINI_KEY


def save_user_api_key(api_key: str):
    """Lưu Google API Key của người dùng (~/.qshien/secrets.json & .env)."""
    try:
        SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        with open(SECRETS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "api_key": api_key.strip(),
                "updated_at": str(Path(__file__).stat().st_mtime)
            }, f, indent=2)
        
        # Đồng thời cập nhật file .env
        env_file = PROJECT_DIR / ".env"
        env_lines = []
        if env_file.exists():
            env_lines = env_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        
        has_key = False
        new_lines = []
        for line in env_lines:
            if line.startswith("GEMINI_API_KEY="):
                new_lines.append(f"GEMINI_API_KEY={api_key.strip()}")
                has_key = True
            else:
                new_lines.append(line)
        if not has_key:
            new_lines.append(f"GEMINI_API_KEY={api_key.strip()}")
            new_lines.append(f"GOOGLE_API_KEY={api_key.strip()}")
        env_file.write_text("\n".join(new_lines), encoding="utf-8")
        return True
    except Exception as e:
        print(f"[Error saving API key] {e}")
        return False


def consult_situation(user_question: str) -> str:
    """
    Tham vấn tình huống với Não bộ Vector RAG kết hợp Google Gemini.
    """
    # 1. Trích xuất ngữ cảnh RAG
    rag_context = ""
    if get_vector_rag is not None:
        try:
            rag = get_vector_rag()
            rag_context = rag.get_rag_context_for_prompt(user_question, top_k=4)
        except Exception as e:
            print(f"[RAG Context Error] {e}")

    # 1.1 Trích xuất Hồ sơ Dự án Hiện Hành (Hợp đồng, BOQ, Tiến độ) nếu có
    dossier_context = ""
    dossier_candidates = [
        DATA_DIR / "current_project_dossier.json",
        PROJECT_DIR / "Data" / "current_project_dossier.json",
        SECRETS_DIR / "current_project_dossier.json"
    ]
    for df in dossier_candidates:
        if df.exists():
            try:
                with open(df, "r", encoding="utf-8") as f:
                    d_data = json.load(f)
                from qshien.desktop_assistant.project_dossier_engine import format_dossier_prompt_context
                dossier_context = format_dossier_prompt_context(d_data)
                if dossier_context:
                    break
            except Exception:
                pass

    # 1.2 Trích xuất Tình báo Quản trị & Tham mưu GĐDA (Claims, Rủi ro, MOM, Dòng tiền, Thầu phụ)
    executive_context = ""
    try:
        from qshien.desktop_assistant.project_executive_engine import get_executive_engine
        executive_context = get_executive_engine().get_executive_context_for_ai()
    except Exception:
        try:
            from project_executive_engine import get_executive_engine
            executive_context = get_executive_engine().get_executive_context_for_ai()
        except Exception:
            pass

    # 2. Xây dựng Prompt thực chiến
    prompt = f"""
Bạn là Su Su - Trợ Lý Thực Chiến & Tham Mưu Chiến Lược Cấp Cao Cho Giám Đốc Dự Án (GĐDA) & Kỹ Sư QS Lead ngành Xây dựng Việt Nam.
Bạn có tư duy sắc bén, thấu hiểu sâu sắc tâm lý công trường, văn hóa xây dựng thực tế và các cạm bẫy pháp lý.
Bạn am hiểu toàn diện 8 TRỤ CỘT THỰC CHIẾN XÂY DỰNG:
1. 🏗️ Kỹ thuật hiện trường & Chất lượng công trình
2. 📄 Pháp lý bàn giấy (Hợp đồng, công văn, nghiệm thu, Claim khối lượng & EOT)
3. 🍻 Ngoại giao bàn tiệc & Tiếp khách đàm phán
4. 💰 Dòng tiền & Tài chính dự án (Điều tiết công nợ, tạm ứng, phát sinh, bảo hành, bảo lãnh ngân hàng)
5. 👷 Quản trị tổ đội, Cai thầu & Tâm lý thợ
6. 🏛️ Quan hệ chính quyền, Láng giềng & Khủng hoảng
7. 🛡️ Pháp lý cá nhân & Phòng thủ giữ mình
8. 🤖 Ứng dụng AI & Tự động hóa thời đại mới

{dossier_context}

{executive_context}

{rag_context}

TÌNH HUỐNG THỰC CHIẾN CẦN THAM VẤN:
"{user_question}"

YÊU CẦU PHẢN HỒI THEO ĐÚNG CẤU TRÚC 5 PHẦN (Thực chiến, đanh thép, dẫn chứng rõ ràng, dùng được ngay):
1. 🎯 **Bản chất vấn đề & Cạm bẫy ngầm:** (Chỉ rõ những rủi ro tiền bạc, pháp lý và quan hệ nếu xử lý ngây thơ).
2. ⚖️ **Căn cứ Pháp lý & Tiêu chuẩn áp dụng:** (Trích dẫn chính xác tiêu chuẩn TCVN, thông tư TT12/TT38 hoặc điều khoản quy định đã đối chiếu từ Não bộ RAG ở trên).
3. 🛠️ **Chiến lược xử lý hiện trường từng bước:** (Kế hoạch hành động cụ thể, kết hợp khéo léo Kỹ thuật - Bàn giấy - Bàn nhậu - Dòng tiền).
4. 💬 **Lời ăn tiếng nói / Mẫu tin nhắn Zalo / Câu thoại đối đáp:** (Soạn sẵn câu thoại hoặc văn bản gửi Chủ đầu tư / Tư vấn giám sát / Tổ đội để kỹ sư copy dùng ngay).
5. 💎 **Đúc kết xương máu:** (1 câu kim chỉ nam đắt giá).
"""

    api_key = get_google_ultra_api_key()
    if not api_key:
        return "⚠️ Chưa có Google Gemini API Key. Bạn có thể mở file .env hoặc vào phần Cài đặt của Trợ lý Su Su để nhập key."

    # 3. Gọi trực tiếp Gemini REST API qua requests (Không phụ thuộc package ngoài)
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.35,
            "topP": 0.95,
            "maxOutputTokens": 4096
        }
    }

    headers = {
        "Content-Type": "application/json"
    }

    last_err = ""
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
                        return parts[0]["text"].strip()
            else:
                last_err = f"HTTP {resp.status_code}: {resp.text[:120]}"
        except Exception as e:
            last_err = str(e)
            continue

    return f"⚠️ Không thể kết nối với dịch vụ Google Gemini AI ({last_err}). Vui lòng kiểm tra lại kết nối mạng hoặc API Key."


def consult_task_action_plan(task_title: str, task_details: str = "", list_name: str = "") -> str:
    """
    Gợi ý hướng xử lý & kế hoạch hành động thực chiến cho một công việc cụ thể (Google Tasks).
    Kết hợp Vector RAG (1,407 tình huống) + Google Gemini AI + Tổng hợp ngoại tuyến (Offline fallback).
    """
    combined_q = f"{task_title} {task_details} {list_name}".strip()
    if not combined_q:
        return "⚠️ Vui lòng nhập tiêu đề hoặc chi tiết công việc để Su Su phân tích."

    # 1. Trích xuất ngữ cảnh từ Não bộ Vector RAG
    rag_context = ""
    top_cases = []
    if get_vector_rag is not None:
        try:
            rag = get_vector_rag()
            rag_context = rag.get_rag_context_for_prompt(combined_q, top_k=3)
            top_cases = rag.query(combined_q, top_k=2)
        except Exception as e:
            print(f"[Task RAG Context Error] {e}")

    # 2. Xây dựng Prompt thực chiến
    prompt = f"""Bạn là Su Su - Trợ Lý Thực Chiến Cao Cấp của Kỹ sư / Chỉ huy trưởng ngành Xây dựng Việt Nam (MenuCad QS Hiền).
Người dùng đang mở một công việc (Task) và cần bạn GỢI Ý HƯỚNG XỬ LÝ & KẾ HOẠCH HÀNH ĐỘNG THỰC CHIẾN.

THÔNG TIN ĐẦU VIỆC:
- Dự án / Danh mục: {list_name or 'Việc chung'}
- Tiêu đề công việc: "{task_title}"
- Diễn giải / Ghi chú hiện trường: "{task_details or 'Chưa có ghi chú'}"

{rag_context}

HÃY ĐƯA RA HƯỚNG DẪN HÀNH ĐỘNG SÚC TÍCH, THỰC CHIẾN, CHUẨN XÁC THEO ĐÚNG 4 MỤC SAU:

🎯 1. BẢN CHẤT & RỦI RO CẦN PHÒNG THỦ:
(Chỉ rõ 2-3 rủi ro cốt tử về kỹ thuật, nghiệm thu, trôi tiến độ, chi phí, hoặc cạm bẫy giấy tờ).

🛠️ 2. CHECKLIST CÁC BƯỚC HÀNH ĐỘNG (DÙNG ĐƯỢC NGAY):
[ ] Bước 1: ... (Chuẩn bị hồ sơ / cao độ / tim trục / vật tư...)
[ ] Bước 2: ... (Kiểm tra thực tế / nội bộ trước khi mời TVGS...)
[ ] Bước 3: ... (Mời TVGS / BQLDA nghiệm thu, lưu vết hình ảnh & ký biên bản...)
[ ] Bước 4: ... (Hậu kiểm / chuyển bước thi công / lập hồ sơ...)

💬 3. LỜI ĂN TIẾNG NÓI / MẪU ĐỐI ĐÁP:
(1-2 câu thoại khéo léo hoặc tin nhắn Zalo gửi TVGS / BQLDA / Tổ thợ để công việc trôi chảy, không bị hoạch họe).

💎 4. LỜI KHUYÊN XƯƠNG MÁU:
(1 câu đúc kết kim chỉ nam kinh nghiệm nghề)."""

    api_key = get_google_ultra_api_key()
    if api_key:
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.35,
                "topP": 0.95,
                "maxOutputTokens": 2048
            }
        }
        headers = {"Content-Type": "application/json"}

        for model_name in ULTRA_MODELS_PRIORITY:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"].strip()
            except Exception:
                continue

    # 3. Chế độ Ngoại Tuyến (Offline RAG Synthesis): Khi không có API Key hoặc mất mạng
    if top_cases:
        best = top_cases[0]
        title_ref = best.get("title", "")
        sim = best.get("similarity_pct", 0)
        ctx = best.get("context", "")
        sol = best.get("solution", "")
        quote = best.get("quote", "")
        lesson = best.get("lesson", "")

        return f"""🎯 1. BẢN CHẤT & RỦI RO CẦN PHÒNG THỦ:
- Căn cứ thực chiến đối chiếu từ CSDL Su Su: "{title_ref}" (Độ khớp: {sim}%)
- Cạm bẫy kỹ thuật / pháp lý cần phòng thủ: {ctx[:220]}...

🛠️ 2. CHECKLIST CÁC BƯỚC HÀNH ĐỘNG (DÙNG ĐƯỢC NGAY):
[ ] Bước 1: Rà soát lại hồ sơ bản vẽ shop-drawing và biên bản công tác thi công trước đó.
[ ] Bước 2: Kiểm tra thực địa nội bộ: {sol[:130]}...
[ ] Bước 3: Gửi giấy mời TVGS & BQLDA nghiệm thu đúng thời hạn hợp đồng, chụp ảnh hiện trường có định vị/thời gian.
[ ] Bước 4: Lập và ký xác nhận biên bản nghiệm thu ngay tại hiện trường, không để dồn về sau.

💬 3. LỜI ĂN TIẾNG NÓI / MẪU ĐỐI ĐÁP:
- "{quote or 'Anh em bên em đã kiểm tra kỹ lưỡng nội bộ theo đúng tiêu chuẩn thiết kế, mời TVGS bố trí qua kiểm tra nghiệm thu giúp em để kịp tiến độ chuyển bước thi công ạ.'}"

💎 4. LỜI KHUYÊN XƯƠNG MÁU:
- {lesson or 'Mọi công việc trên công trường phải luôn có biên bản giấy trắng mực đen và lưu vết hình ảnh làm bằng chứng pháp lý.'}
(⚡ Gợi ý được trích xuất từ Não bộ Vector RAG ngoại tuyến 1,407 tình huống)"""
    else:
        return """🎯 1. BẢN CHẤT & RỦI RO CẦN PHÒNG THỦ:
- Kiểm soát kỹ thuật và thủ tục giấy tờ nghiệm thu chặt chẽ để tránh bị dừng việc hoặc chậm thanh toán.

🛠️ 2. CHECKLIST CÁC BƯỚC HÀNH ĐỘNG (DÙNG ĐƯỢC NGAY):
[ ] Bước 1: Rà soát bản vẽ thiết kế, biện pháp thi công và chuẩn bị đầy đủ vật tư/nhân lực.
[ ] Bước 2: Tự kiểm tra nội bộ các chỉ tiêu kích thước, cao độ, tim trục và an toàn lao động.
[ ] Bước 3: Gửi phiếu yêu cầu nghiệm thu cho TVGS đúng quy định thời gian trong hợp đồng.
[ ] Bước 4: Tổ chức nghiệm thu thực tế, chụp ảnh lưu vết và ký biên bản đầy đủ các bên.

💬 3. LỜI ĂN TIẾNG NÓI / MẪU ĐỐI ĐÁP:
- "Dạ anh/chị xem qua giúp em phần này anh em đã hoàn thành nội bộ đạt chuẩn, em mời anh/chị ra kiểm tra giúp em để bên em kịp chuyển bước tiếp theo nhé ạ."

💎 4. LỜI KHUYÊN XƯƠNG MÁU:
- Mọi thỏa thuận miệng trên công trường đều vô giá trị khi phát sinh tranh chấp; giấy trắng mực đen là trên hết."""


# Alias tương thích cho Trợ Lý Su Su & Telegram Bot
consult_su_su_ultra = consult_situation


if __name__ == "__main__":
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = "Tư vấn tình huống: Tư vấn giám sát cố tình không chịu ký biên bản nghiệm thu cốt thép móng để ép nhà thầu chi hoa hồng, xử lý thế nào để vừa được việc mà không vi phạm pháp luật?"

    print(f"\n=======================================================")
    print(f" ❓ CÂU HỎI THỰC CHIẾN: {question}")
    print(f"=======================================================\n")

    advice = consult_situation(question)
    print(advice)
