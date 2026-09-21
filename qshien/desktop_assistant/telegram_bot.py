# -*- coding: utf-8 -*-
"""
telegram_bot.py - Trợ Lý Cá Nhân Su Su Trên Telegram Cho Kỹ Sư QS
=============================================================================
Hỗ trợ:
1. Kết nối an toàn trực tiếp qua Telegram Bot HTTP API (Long Polling qua requests).
   - KHÔNG cần mở port mạng (No NAT/Port Forwarding).
   - Hoạt động mượt mà sau Wi-Fi văn phòng, mạng gia đình, 4G/5G Hotspot.
2. Kiểm soát truy cập bảo mật cá nhân (Private Access Control):
   - Auto-pair với Admin trong lần đầu tiên /start.
   - Chặn người ngoài truy cập dữ liệu dự án mật.
3. Tích hợp toàn diện Não Bộ Su Su:
   - 🌟 14 Bài học thực chiến hôm nay (kèm lật thẻ, đổi bài).
   - 🔍 Tra cứu tức thì trong kho 5.449 tình huống 8 Trụ Cột (Hybrid BM25 + Vector RAG).
   - 💬 Trò chuyện & Tham vấn AI trực tiếp (Google Gemini AI + Hồ sơ Vietstar 344 tỷ).
   - 🏢 Tra cứu số liệu Hồ sơ dự án Vietstar (Hợp đồng, BOQ, Tiến độ găng).
   - 📈 Nhịp sinh học Biorhythm, Lịch âm & Tử vi khởi công hôm nay.
   - 📝 Tạo nhanh Task công việc vào Sổ tay / Google Tasks.
=============================================================================
"""

from __future__ import annotations

import os
import sys
import json
import time
import datetime
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import requests

# Định vị thư mục package và dữ liệu
CURRENT_DIR = Path(__file__).resolve().parent
ADDIN_DIR = CURRENT_DIR.parent.parent if len(CURRENT_DIR.parents) >= 2 else CURRENT_DIR
REPO_ROOT = ADDIN_DIR.parent if len(ADDIN_DIR.parents) >= 1 else CURRENT_DIR

DEFAULT_BOT_TOKEN = "8830295571:AAElfoa5UqIB5lG_2KSXfvG5ckMQjNFL3yY"

if str(ADDIN_DIR) not in sys.path:
    sys.path.insert(0, str(ADDIN_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Tìm thư mục Data
def _get_data_dir() -> Path:
    candidates = [
        CURRENT_DIR / "Data",
        CURRENT_DIR,
        REPO_ROOT.parent / "Data",
        REPO_ROOT / "Data",
        Path("/app/Data"),
        Path("/app"),
        Path(r"C:\QS_Hien\Data"),
        Path(r"C:\QS_Hien\trithuc\susu"),
    ]
    # Ưu tiên thư mục chứa file dữ liệu thực
    for c in candidates:
        if c.is_dir() and ((c / "tinh_huong_thuc_chien.json").exists() or (c / "susu_vector_kb.db").exists()):
            return c
    for c in candidates:
        if c.is_dir():
            return c
    return CURRENT_DIR

DATA_DIR = _get_data_dir()
CONFIG_FILE = DATA_DIR / "telegram_config.json"


def load_telegram_config() -> Dict[str, Any]:
    """Nạp cấu hình Telegram Bot từ Data/telegram_config.json hoặc biến môi trường."""
    config: Dict[str, Any] = {
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or DEFAULT_BOT_TOKEN,
        "allowed_chat_ids": [8249791298],
        "auto_bind_first_user": True,
        "bot_name": "🌸 Su Su - Trợ Lý Chiến Lược QS Hiền",
        "poll_timeout": 30,
        "is_active": True
    }

    # Quét tất cả các vị trí khả dĩ của telegram_config.json
    cfg_candidates = [
        CONFIG_FILE,
        CURRENT_DIR / "telegram_config.json",
        CURRENT_DIR / "Data" / "telegram_config.json",
        Path("/app/telegram_config.json"),
        Path("/app/Data/telegram_config.json"),
    ]
    for cfg_path in cfg_candidates:
        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        config.update(saved)
                        break
            except Exception:
                pass

    if not config.get("bot_token"):
        config["bot_token"] = DEFAULT_BOT_TOKEN

    # Kiểm tra thêm các file .env
    for env_path in [REPO_ROOT / ".env", REPO_ROOT.parent / ".env", Path(r"C:\QS_Hien\.env"), CURRENT_DIR / ".env", Path("/app/.env")]:
            if env_path.exists():
                try:
                    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                        line = line.strip()
                        if line.startswith("TELEGRAM_BOT_TOKEN="):
                            tok = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if tok:
                                config["bot_token"] = tok
                                break
                except Exception:
                    pass

    return config


def save_telegram_config(config: Dict[str, Any]) -> bool:
    """Lưu cấu hình Telegram Bot."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


class TelegramClient:
    """HTTP Client giao tiếp với Telegram Bot API qua requests."""
    BASE_URL = "https://api.telegram.org/bot"

    def __init__(self, token: str, timeout: int = 35):
        self.token = token.strip()
        self.timeout = timeout
        self.api_url = f"{self.BASE_URL}{self.token}"

    def get_me(self) -> Optional[Dict[str, Any]]:
        """Kiểm tra bot token hợp lệ và lấy thông tin bot."""
        if not self.token:
            return None
        url = f"{self.api_url}/getMe"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("result")
        except Exception:
            pass
        return None

    def get_updates(self, offset: Optional[int] = None, timeout: int = 30) -> List[Dict[str, Any]]:
        """Nhận các tin nhắn mới từ Telegram (Long Polling)."""
        if not self.token:
            return []
        url = f"{self.api_url}/getUpdates"
        params: Dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        try:
            resp = requests.get(url, params=params, timeout=timeout + 10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("result", [])
        except requests.exceptions.Timeout:
            return []
        except Exception:
            time.sleep(2)
        return []

    def send_chat_action(self, chat_id: int | str, action: str = "typing") -> bool:
        """Gửi trạng thái 'đang soạn tin...' (typing)."""
        if not self.token:
            return False
        url = f"{self.api_url}/sendChatAction"
        try:
            requests.post(url, json={"chat_id": chat_id, "action": action}, timeout=5)
            return True
        except Exception:
            return False

    def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: Optional[str] = "Markdown",
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Gửi tin nhắn đến người dùng.
        Tự động chia nhỏ tin nhắn nếu dài hơn 4.000 ký tự (giới hạn của Telegram).
        Tự động fallback về plain text nếu định dạng Markdown lỗi.
        """
        if not self.token or not text:
            return False

        url = f"{self.api_url}/sendMessage"
        max_len = 3900

        chunks: List[str] = []
        if len(text) <= max_len:
            chunks.append(text)
        else:
            # Tách theo dòng để tránh cắt đôi chữ
            curr = ""
            for line in text.splitlines(keepends=True):
                if len(curr) + len(line) > max_len:
                    chunks.append(curr)
                    curr = line
                else:
                    curr += line
            if curr:
                chunks.append(curr)

        success = True
        for i, chunk in enumerate(chunks):
            # Chỉ gửi reply_markup ở chunk cuối cùng
            markup = reply_markup if i == len(chunks) - 1 else None
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if markup:
                payload["reply_markup"] = markup

            try:
                resp = requests.post(url, json=payload, timeout=15)
                if resp.status_code != 200:
                    # Fallback plain text nếu Telegram báo lỗi parse markdown
                    payload.pop("parse_mode", None)
                    resp_retry = requests.post(url, json=payload, timeout=15)
                    if resp_retry.status_code != 200:
                        success = False
            except Exception:
                success = False

        return success

    def answer_callback_query(self, callback_query_id: str, text: Optional[str] = None) -> bool:
        """Xác nhận người dùng đã bấm nút Inline Keyboard."""
        if not self.token:
            return False
        url = f"{self.api_url}/answerCallbackQuery"
        payload: Dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        try:
            requests.post(url, json=payload, timeout=5)
            return True
        except Exception:
            return False


class SuSuTelegramBot:
    """Bộ Điều Khiển Não Bộ Su Su Cho Telegram Chatbot."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or load_telegram_config()
        self.token = self.config.get("bot_token", "").strip()
        self.allowed_chat_ids: List[int] = [int(x) for x in self.config.get("allowed_chat_ids", [])]
        self.auto_bind_first_user = self.config.get("auto_bind_first_user", True)
        self.client = TelegramClient(self.token)
        self.is_running = False
        self.bot_thread: Optional[threading.Thread] = None
        self.bot_info: Optional[Dict[str, Any]] = None

        # Nạp các động cơ phụ trợ
        self._search_engine = None
        self._all_scenarios = None

    def get_main_keyboard(self) -> Dict[str, Any]:
        """Bàn phím tương tác nhanh (Reply Keyboard)."""
        return {
            "keyboard": [
                [{"text": "🌟 14 Bài Học Hôm Nay"}, {"text": "🔍 Tra Cứu Tình Huống"}],
                [{"text": "🏢 Hồ Sơ Dự Án Vietstar"}, {"text": "📈 Nhịp Sinh Học & Tử Vi"}],
                [{"text": "❓ Hướng Dẫn & Trợ Giúp"}]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }

    def check_authorization(self, chat_id: int, user_info: Dict[str, Any]) -> bool:
        """Kiểm tra quyền truy cập của người dùng."""
        if not self.allowed_chat_ids:
            if self.auto_bind_first_user:
                # Tự động gán quyền Admin cho người nhắn đầu tiên
                self.allowed_chat_ids.append(chat_id)
                self.config["allowed_chat_ids"] = self.allowed_chat_ids
                save_telegram_config(self.config)
                return True
            return False
        return chat_id in self.allowed_chat_ids

    def _ensure_search_engine(self):
        """Khởi tạo nhanh công cụ tìm kiếm trong bộ nhớ nếu cần."""
        if self._search_engine is None:
            try:
                from qshien.desktop_assistant.search_engine import FastSearchEngine
                cases_file = DATA_DIR / "tinh_huong_thuc_chien.json"
                if not cases_file.exists():
                    cases_file = Path(r"C:\QS_Hien\Data\tinh_huong_thuc_chien.json")
                if cases_file.exists():
                    with open(cases_file, "r", encoding="utf-8") as f:
                        self._all_scenarios = json.load(f)
                        self._search_engine = FastSearchEngine(self._all_scenarios)
            except Exception:
                pass

    # =========================================================================
    # XỬ LÝ CÁC LỆNH
    # =========================================================================

    def handle_start(self, chat_id: int, user_info: Dict[str, Any]):
        """Xử lý lệnh /start."""
        first_name = user_info.get("first_name", "Kỹ sư")
        msg = (
            f"🌸 *Xin chào {first_name}! Tôi là Su Su - Trợ lý Chiến Lược QS Hiền Pro.*\n\n"
            f"✨ *Tôi đã được trang bị:*\n"
            f"• 📚 Kho tri thức *5.449 tình huống thực chiến* chuẩn 8 Trụ Cột.\n"
            f"• 🏢 Toàn bộ *Hồ sơ dự án Vietstar 344,89 Tỷ* (Hợp đồng, BOQ 222 việc, 30 việc găng).\n"
            f"• 🧠 Não bộ *Google Gemini Ultra AI* tham vấn pháp lý & chiến lược đàm phán.\n"
            f"• 📈 Nhịp sinh học Biorhythm & Lịch hoàng đạo phục vụ khởi công, cất nóc.\n\n"
            f"👉 *Bạn có thể chọn nhanh các nút bên dưới hoặc gõ thẳng bất kỳ câu hỏi nào!*"
        )
        self.client.send_message(chat_id, msg, reply_markup=self.get_main_keyboard())

    def handle_help(self, chat_id: int):
        """Xử lý lệnh /help hoặc Hướng dẫn."""
        msg = (
            "📖 *CẨM NANG SỬ DỤNG TRỢ LÝ SU SU QUA TELEGRAM:*\n\n"
            "💬 *1. Hỏi đáp AI tự nhiên:*\n"
            "Gõ bất kỳ câu hỏi nào như đang chat với chuyên gia QS:\n"
            "• _\"Nghiệm thu cọc khoan nhồi cần lưu ý biên bản gì?\"_\n"
            "• _\"Gặp mưa bão dừng thi công thì làm thủ tục claim gia hạn thế nào?\"_\n"
            "• _\"Thời gian tạm ứng và tỷ lệ giữ lại của dự án Vietstar?\"_\n\n"
            "🌟 *2. Các lệnh tra cứu nhanh:*\n"
            "• `/14bai` : Xem 14 bài học kinh nghiệm chọn lọc hôm nay.\n"
            "• `/tk <từ khóa>` : Tra cứu tình huống (Ví dụ: `/tk bê tông móng`).\n"
            "• `/duan` : Xem bảng tóm tắt hồ sơ dự án Vietstar.\n"
            "• `/tuvi` : Xem nhịp sinh học và ngày hoàng đạo hôm nay.\n"
            "• `/task <nội dung>` : Thêm nhanh công việc vào Sổ tay trên máy tính."
        )
        self.client.send_message(chat_id, msg)

    def handle_14_scenarios(self, chat_id: int):
        """Xử lý hiển thị 14 tình huống hôm nay."""
        daily_path = DATA_DIR / "14_tinh_huong_hom_nay.json"
        if not daily_path.exists():
            daily_path = Path(r"C:\QS_Hien\Data\14_tinh_huong_hom_nay.json")

        scenarios = []
        if daily_path.exists():
            try:
                with open(daily_path, "r", encoding="utf-8") as f:
                    scenarios = json.load(f)
            except Exception:
                pass

        if not scenarios:
            self._ensure_search_engine()
            if self._all_scenarios and len(self._all_scenarios) >= 14:
                import random
                scenarios = random.sample(self._all_scenarios, 14)

        if not scenarios:
            self.client.send_message(chat_id, "⚠️ Hiện tại chưa có dữ liệu 14 bài học hôm nay.")
            return

        header = "🌟 *14 BÀI HỌC THỰC CHIẾN HÔM NAY (8 TRỤ CỘT):*\n\n"
        lines = []
        for i, sc in enumerate(scenarios[:7], 1):
            title = sc.get("TieuDe") or sc.get("TenTinhHuong") or "Tình huống"
            pillar = sc.get("TruCot", "CHUNG")
            lines.append(f"*{i}.* [{pillar}] *{title}*")

        lines.append("\n_(Hiển thị 7/14 bài đầu tiên. Gõ `/tk <từ khóa>` để đọc chi tiết bất kỳ bài nào)_")
        msg = header + "\n".join(lines)
        self.client.send_message(chat_id, msg)

    def handle_search(self, chat_id: int, query: str):
        """Tra cứu tình huống thực chiến."""
        q = query.strip()
        if not q:
            self.client.send_message(chat_id, "💡 Vui lòng gõ kèm từ khóa tra cứu, ví dụ: `/tk cọc khoan nhồi` hoặc `/tk đàm phán hợp đồng`")
            return

        self.client.send_chat_action(chat_id, "typing")
        self._ensure_search_engine()

        if not self._search_engine:
            self.client.send_message(chat_id, "⚠️ Bộ máy tra cứu đang khởi tạo, vui lòng thử lại sau giây lát.")
            return

        results = self._search_engine.search(q)
        if not results:
            self.client.send_message(chat_id, f"🔍 Không tìm thấy tình huống nào khớp với từ khóa: *\"{q}\"*. Bạn hãy thử từ khóa ngắn hơn nhé!")
            return

        top = results[:3]
        lines = [f"🔍 *KẾT QUẢ TRA CỨU: \"{q}\"* (Khớp {len(results)} bài học):\n"]
        for idx, item in enumerate(top, 1):
            data = item.get("data", {})
            title = data.get("TieuDe") or item.get("title", "Tình huống")
            pillar = data.get("TruCot") or item.get("pillar", "")
            context = data.get("BoiCanh") or ""
            sol = data.get("ChienLuocXuLy") or ""
            quote = data.get("CauThoaiMau") or ""
            lesson = data.get("BaiHocXuongMau") or ""

            lines.append(f"━━━━━━━━━━━━━━━━━━━━\n📌 *BÀI HỌC #{idx}: {title}*")
            if pillar:
                lines.append(f"🏷️ *Trụ cột:* `{pillar}`")
            if context:
                lines.append(f"⚡ *Bối cảnh/Rủi ro:* {context[:250]}...")
            if sol:
                lines.append(f"🛡️ *Chiến lược xử lý:* {sol[:300]}...")
            if quote:
                lines.append(f"💬 *Câu thoại mẫu:* _{quote}_")
            if lesson:
                lines.append(f"💎 *Đúc kết xương máu:* *{lesson}*")

        self.client.send_message(chat_id, "\n\n".join(lines))

    def handle_project_dossier(self, chat_id: int):
        """Xem tóm tắt hồ sơ dự án Vietstar."""
        dossier_file = DATA_DIR / "current_project_dossier.json"
        if not dossier_file.exists():
            dossier_file = Path(r"C:\QS_Hien\Data\current_project_dossier.json")

        if not dossier_file.exists():
            self.client.send_message(chat_id, "⚠️ Chưa tìm thấy tệp hồ sơ dự án `current_project_dossier.json` trên máy tính.")
            return

        try:
            with open(dossier_file, "r", encoding="utf-8") as f:
                dossier = json.load(f)
        except Exception as e:
            self.client.send_message(chat_id, f"⚠️ Lỗi đọc hồ sơ dự án: {e}")
            return

        p_info = dossier.get("project_info", {})
        contract = dossier.get("contract_data", {})
        boq = dossier.get("boq_data", {})
        sched = dossier.get("schedule_data", {})

        p_name = p_info.get("project_name", "TCXD HẠNG MỤC HỐ RÁC LÒ ĐỐT - NHÀ MÁY VIETSTAR")
        contractor = p_info.get("contractor", "CÔNG TY CP ĐẦU TƯ XÂY DỰNG NOVACONS")

        # Số liệu tài chính
        val_vat = contract.get("contract_value_vat", 344886779000)
        val_no_vat = contract.get("contract_value_before_tax", 319339610185)
        adv = contract.get("advance_payment_val", 95801883055)
        vat_tax = contract.get("vat_amount", 25547168815)
        item_count = boq.get("total_items", 222)
        crit_count = sched.get("critical_tasks_count", 30)
        dur = sched.get("total_duration_days", 210)

        msg = (
            f"🏢 *HỒ SƠ DỰ ÁN VIETSTAR - NOVACONS:*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Dự án:* {p_name}\n"
            f"👷 *Nhà thầu:* {contractor}\n\n"
            f"💰 *CÁC MỐC TÀI CHÍNH CỐT TỬ:*\n"
            f"• **Giá trị HĐ (có VAT 8%):** `{val_vat:,.0f} VNĐ` (~{val_vat/1e9:.2f} Tỷ)\n"
            f"• **Giá trị trước thuế:** `{val_no_vat:,.0f} VNĐ`\n"
            f"• **Thuế VAT (8%):** `{vat_tax:,.0f} VNĐ`\n"
            f"• **Tạm ứng (30%):** `{adv:,.0f} VNĐ` (~{adv/1e9:.2f} Tỷ)\n\n"
            f"📊 *KHỐI LƯỢNG & TIẾN ĐỘ THỰC TẾ:*\n"
            f"• Số đầu việc BOQ thực tế: *{item_count} đầu việc*\n"
            f"• Thời gian thi công: *{dur} ngày*\n"
            f"• Số công việc trên Đường Găng (Critical): *{crit_count} đầu việc*\n\n"
            f"💡 _(Dữ liệu đã được nạp trọn vẹn vào Não bộ RAG của Su Su)_"
        )
        self.client.send_message(chat_id, msg)

    def handle_biorhythm_tuvi(self, chat_id: int):
        """Tính toán nhịp sinh học và tử vi hôm nay."""
        try:
            from qshien.desktop_assistant.lunar_biorhythm import calculate_biorhythm, get_can_chi
            today = datetime.date.today()
            birth = datetime.date(1994, 3, 3)  # Mặc định theo profile người dùng

            bio = calculate_biorhythm(birth, today)
            lunar = get_can_chi(today.day, today.month, today.year)

            def make_bar(val: float) -> str:
                # Chuyển từ -100..100 sang 0..5 vạch
                norm = int((val + 100) / 40)
                norm = max(0, min(5, norm))
                return "🟩" * norm + "⬜" * (5 - norm)

            p_val = bio["physical"]
            e_val = bio["emotional"]
            i_val = bio["intellectual"]

            msg = (
                f"📈 *NHỊP SINH HỌC & LỊCH ÂM HÔM NAY ({today.strftime('%d/%m/%Y')}):*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🌙 *Âm lịch:* Ngày {lunar['lunar_day']}/{lunar['lunar_month']} năm {lunar['nam_can_chi']}\n"
                f"☀️ *Can Chi Ngày:* {lunar['ngay_can_chi']} ({'🌟 Ngày Hoàng Đạo' if lunar['is_hoang_dao_day'] else 'Cần cẩn trọng'})\n"
                f"🍃 *Tiết khí:* {lunar['tiet_khi']}\n\n"
                f"💪 *CHỈ SỐ NHỊP SINH HỌC CỦA BẠN:*\n"
                f"• **Thể chất (P):** {make_bar(p_val)} `{p_val:+.1f}%`\n"
                f"• **Cảm xúc (E):** {make_bar(e_val)} `{e_val:+.1f}%`\n"
                f"• **Trí tuệ (I):** {make_bar(i_val)} `{i_val:+.1f}%`\n\n"
                f"💡 *LỜI KHUYÊN THỰC CHIẾN HÔM NAY:*\n"
                f"{lunar.get('khuyen_nghi', '')}\n\n"
                f"👉 *Việc nên làm:* {lunar.get('viec_nen', '')}\n"
                f"👉 *Việc nên kiêng:* {lunar.get('viec_kieng', '')}"
            )
            self.client.send_message(chat_id, msg)
        except Exception as e:
            self.client.send_message(chat_id, f"⚠️ Lỗi tính toán nhịp sinh học: {e}")

    def handle_add_task(self, chat_id: int, task_content: str):
        """Thêm nhanh task công việc."""
        content = task_content.strip()
        if not content:
            self.client.send_message(chat_id, "💡 Vui lòng gõ nội dung công việc, ví dụ: `/task Nghiệm thu cốt thép đài móng trục 1-4 lúc 15h`")
            return

        notes_file = DATA_DIR / "user_personal_notes.json"

        new_task = {
            "id": f"tsk_tele_{int(time.time())}",
            "list": "VST",
            "title": content,
            "details": f"Ghi chú nhanh từ Telegram lúc {datetime.datetime.now().strftime('%H:%M %d/%m/%Y')}",
            "due_date": "Hôm nay",
            "starred": True,
            "completed": False,
            "created_at": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
            "completed_at": ""
        }

        try:
            tasks_data = {"current_list": "VST", "tasks": []}
            if notes_file.exists():
                with open(notes_file, "r", encoding="utf-8") as f:
                    tasks_data = json.load(f)
            tasks_data.setdefault("tasks", []).insert(0, new_task)
            with open(notes_file, "w", encoding="utf-8") as f:
                json.dump(tasks_data, f, ensure_ascii=False, indent=2)

            self.client.send_message(chat_id, f"✅ *Đã lưu công việc vào Sổ tay Su Su (Danh sách VST):*\n\n📌 *{content}*")
        except Exception as e:
            self.client.send_message(chat_id, f"⚠️ Không thể lưu task: {e}")

    def handle_natural_question(self, chat_id: int, question: str):
        """Hỏi đáp AI tự nhiên qua consult_situation / consult_su_su_ultra."""
        self.client.send_chat_action(chat_id, "typing")
        try:
            try:
                from scripts.consult_expert import consult_situation as consult_ai
            except ImportError:
                from consult_expert import consult_situation as consult_ai
            answer = consult_ai(question)
            if not answer:
                answer = "Su Su đã tiếp nhận câu hỏi nhưng chưa thể tạo câu trả lời. Bạn vui lòng thử lại nhé!"
            self.client.send_message(chat_id, answer)
        except Exception as e:
            self.client.send_message(chat_id, f"⚠️ Lỗi kết nối Não bộ AI Su Su: {e}")

    # =========================================================================
    # VÒNG LẶP POLLING CHÍNH
    # =========================================================================

    def process_update(self, update: Dict[str, Any]):
        """Xử lý một update từ Telegram."""
        # 1. Xử lý Callback Query (khi bấm nút inline)
        if "callback_query" in update:
            cb = update["callback_query"]
            cb_id = cb.get("id")
            cb_data = cb.get("data", "")
            from_user = cb.get("from", {})
            chat_id = from_user.get("id")
            self.client.answer_callback_query(cb_id, "Đang xử lý...")
            if cb_data == "14bai":
                self.handle_14_scenarios(chat_id)
            elif cb_data == "duan":
                self.handle_project_dossier(chat_id)
            return

        # 2. Xử lý tin nhắn văn bản thông thường
        message = update.get("message")
        if not message:
            return

        chat = message.get("chat", {})
        chat_id = chat.get("id")
        user_info = message.get("from", {})
        text = (message.get("text") or "").strip()

        if not text:
            return

        # Kiểm tra bảo mật cá nhân
        if not self.check_authorization(chat_id, user_info):
            refuse_msg = (
                "⛔ *Truy cập bị từ chối!*\n\n"
                "Trợ lý Su Su là hệ thống trí tuệ và hồ sơ dự án mật của Kỹ sư QS Hiền.\n"
                f"Telegram Chat ID của bạn: `{chat_id}`.\n"
                "Vui lòng liên hệ Admin để được cấp quyền."
            )
            self.client.send_message(chat_id, refuse_msg)
            return

        t_clean = text.strip()
        t_lower = t_clean.lower()

        # 1. Lệnh tra cứu tình huống: /tk, tk, Tk, tim, tìm, tra cứu (không phân biệt hoa/thường)
        tk_prefixes = ("/tk ", "tk ", "/tk:", "tk:", "/timkiem ", "/tim ", "tim ", "tìm ", "tra cứu ")
        matched_tk = False
        for pref in tk_prefixes:
            if t_lower.startswith(pref):
                query = t_clean[len(pref):].strip()
                if query:
                    self.handle_search(chat_id, query)
                else:
                    self.client.send_message(chat_id, "🔍 Bạn muốn tra cứu chủ đề gì? Hãy gõ theo cú pháp: `tk <từ khóa>` (Ví dụ: `tk bê tông`, `tk tạm ứng`, `tk đàm phán`)")
                matched_tk = True
                break
        if matched_tk:
            return

        if t_lower in ("/tk", "tk", "tìm", "tra cứu", "🔍 tra cứu tình huống"):
            self.client.send_message(chat_id, "🔍 Bạn muốn tra cứu chủ đề gì? Hãy gõ theo cú pháp: `tk <từ khóa>` (Ví dụ: `tk bê tông`, `tk tạm ứng`, `tk đàm phán`)")
            return

        # 2. Khởi động
        if t_lower.startswith("/start"):
            self.handle_start(chat_id, user_info)
            return

        # 3. Trợ giúp
        if t_lower in ("/help", "help", "trợ giúp", "hướng dẫn", "❓ hướng dẫn & trợ giúp"):
            self.handle_help(chat_id)
            return

        # 4. 14 bài học hôm nay
        if t_lower in ("/14bai", "14bai", "/daily", "daily", "14 bài", "14 bai", "🌟 14 bài học hôm nay"):
            self.handle_14_scenarios(chat_id)
            return

        # 5. Hồ sơ dự án Vietstar
        if t_lower in ("/duan", "duan", "dự án", "du an", "/vietstar", "vietstar", "🏢 hồ sơ dự án vietstar"):
            self.handle_project_dossier(chat_id)
            return

        # 6. Nhịp sinh học & Tử vi
        if t_lower in ("/tuvi", "tuvi", "tử vi", "/nhipsinhhoc", "nhip sinh hoc", "nhịp sinh học", "📈 nhịp sinh học & tử vi"):
            self.handle_biorhythm_tuvi(chat_id)
            return

        # 7. Lưu task công việc
        if t_lower.startswith("/task ") or t_lower.startswith("task "):
            task_content = t_clean.split(" ", 1)[1]
            self.handle_add_task(chat_id, task_content)
            return

        # 8. Mọi câu hỏi thông thường -> chuyển cho Google Gemini AI + Vector RAG
        self.handle_natural_question(chat_id, t_clean)

    def start_polling(self):
        """Chạy vòng lặp nhận tin nhắn từ Telegram."""
        if not self.token:
            print("[TelegramBot] ⚠️ Chưa có Telegram Bot Token. Vui lòng cấu hình trong telegram_config.json")
            return

        import ctypes
        kernel32 = ctypes.windll.kernel32
        mutex_name = "Global\\QSHien_SuSu_TelegramBot_Polling_Mutex"
        mutex = kernel32.CreateMutexW(None, False, mutex_name)
        if kernel32.GetLastError() == 183:
            print("[TelegramBot] ⚠️ Đã có một tiến trình khác đang chạy Telegram Bot. Bỏ qua để tránh xung đột.")
            return

        self.bot_info = self.client.get_me()
        if not self.bot_info:
            print("[TelegramBot] ❌ Token không hợp lệ hoặc không thể kết nối tới Telegram API.")
            if mutex:
                kernel32.CloseHandle(mutex)
            return

        username = self.bot_info.get("username", "UnknownBot")
        print(f"[TelegramBot] ✅ Đã kết nối thành công với Telegram Bot: @{username}")
        print(f"[TelegramBot] 📡 Bắt đầu lắng nghe tin nhắn (Long Polling)...")

        self.is_running = True
        offset = None

        try:
            while self.is_running:
                try:
                    updates = self.client.get_updates(offset=offset, timeout=self.config.get("poll_timeout", 30))
                    for upd in updates:
                        upd_id = upd.get("update_id")
                        if upd_id is not None:
                            offset = upd_id + 1
                        self.process_update(upd)
                except Exception as e:
                    time.sleep(3)
        finally:
            if mutex:
                try:
                    kernel32.ReleaseMutex(mutex)
                    kernel32.CloseHandle(mutex)
                except Exception:
                    pass

    def start_background(self):
        """Chạy bot trong một luồng nền."""
        if self.bot_thread and self.bot_thread.is_alive():
            return
        self.bot_thread = threading.Thread(target=self.start_polling, daemon=True)
        self.bot_thread.start()

    def stop(self):
        """Dừng bot an toàn."""
        self.is_running = False


def create_sample_config_if_missing():
    """Tạo file cấu hình mẫu nếu chưa có."""
    if not CONFIG_FILE.exists():
        initial = {
            "bot_token": "",
            "allowed_chat_ids": [],
            "auto_bind_first_user": True,
            "bot_name": "🌸 Su Su - Trợ Lý Chiến Lược QS Hiền",
            "poll_timeout": 30,
            "is_active": False
        }
        save_telegram_config(initial)


if __name__ == "__main__":
    create_sample_config_if_missing()
    cfg = load_telegram_config()
    bot = SuSuTelegramBot(cfg)
    bot.start_polling()
