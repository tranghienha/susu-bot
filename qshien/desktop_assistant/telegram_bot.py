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

import base64

DEFAULT_BOT_TOKEN = base64.b64decode(b"ODgzMDI5NTU3MTpBQUVsZm9hNVVxSUI1bEdfMktTWGZ2RzVja01Rak5GTDN5WQ==").decode("ascii")

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


PILLAR_TAGS = {
    "KY_THUAT_HIEN_TRUONG": "🏗️ KỸ THUẬT HIỆN TRƯỜNG",
    "PHAP_LY_BAN_GIAY": "📄 PHÁP LÝ & CLAIM",
    "NGOAI_GIAO_BAN_TIEC": "🍻 NGOẠI GIAO BÀN TIỆC",
    "DONG_TIEN_TAI_CHINH": "💰 DÒNG TIỀN & TÀI CHÍNH",
    "TO_DOI_CAI_THAU": "👷 QUẢN TRỊ TỔ ĐỘI",
    "CHINH_QUYEN_LANG_GIENG": "🏛️ CHÍNH QUYỀN & DÂN",
    "PHONG_THU_PHAP_LY": "🛡️ PHÒNG THỦ GIỮ MÌNH",
    "UNG_DUNG_AI_THOI_DAI_MOI": "🤖 SỐNG CÙNG AI"
}


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
        """Bàn phím tương tác nhanh (Reply Keyboard) chuẩn 5 tab Desktop + Tham Mưu GĐDA + Outlook."""
        return {
            "keyboard": [
                [{"text": "📊 THAM MƯU GĐDA"}, {"text": "📋 Giao Việc & Điều Phối"}],
                [{"text": "📧 Hộp Thư Outlook"}, {"text": "🏢 Hồ Sơ Dự Án Vietstar"}],
                [{"text": "🌟 14 Bài Học Hôm Nay"}, {"text": "📈 Lịch & Nhịp Tử Vi"}],
                [{"text": "🔍 Tra Cứu Tình Huống"}, {"text": "❓ Hướng Dẫn & Trợ Giúp"}]
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
                if not cases_file.exists():
                    cases_file = Path("/app/tinh_huong_thuc_chien.json")
                if not cases_file.exists():
                    cases_file = Path("/app/Data/tinh_huong_thuc_chien.json")
                if cases_file.exists():
                    with open(cases_file, "r", encoding="utf-8") as f:
                        self._all_scenarios = json.load(f)
                        self._search_engine = FastSearchEngine(self._all_scenarios)
            except Exception:
                pass

    # =========================================================================
    # XỬ LÝ CÁC LỆNH
    # =========================================================================

    def handle_start(self, chat_id: int, user_info: Optional[Dict[str, Any]] = None):
        """Xử lý lệnh /start."""
        if not user_info:
            user_info = {}
        first_name = user_info.get("first_name", "Hiền")
        msg = (
            f"🌸 *Xin chào {first_name}! Tôi là Su Su - Trợ lý Chiến Lược & Cố Vấn GĐDA.*\n"
            f"_(Phạm Hà Khánh Ngọc • 21/10/2019 • Đồng hành 24/7 trên mọi công trường)_\n\n"
            f"✨ *HỆ SINH THÁI NÃO BỘ ĐƯỢC KẾ THỪA TỪ DESKTOP:*\n"
            f"• 📊 *Tham Mưu Chiến Lược GĐDA:* Bản tin 1 trang, quản trị rủi ro hố sâu, hồ sơ Claim EOT, vũ khí đàm phán MOM & sức khỏe dòng tiền.\n"
            f"• 📋 *Phân Công Giao Việc & Điều Phối:* Theo dõi mốc khẩn cấp, tháo gỡ điểm nghẽn kỹ thuật & phân nhiệm vụ từng kỹ sư.\n"
            f"• 🌟 *14 Bài học thực chiến hôm nay:* Lật thẻ tình huống 8 Trụ Cột, kèm bối cảnh, rủi ro, chiến lược, thoại mẫu & đúc kết.\n"
            f"• 📈 *Lịch Vạn Niên & Tử Vi Hiện Trường:* Can Chi, Trực, Sao, Giờ Hoàng Đạo đổ bê tông/cất nóc, Hỷ Thần, Tài Thần & Nhịp sinh học Biorhythm.\n"
            f"• 📋 *Sổ tay G-Tasks:* Đồng bộ danh mục việc cần làm dự án VST, quản lý tiến độ thi công & nhắc việc.\n"
            f"• 🏢 *Hồ sơ dự án Vietstar 344,89 Tỷ:* Chi tiết HĐ, 222 việc BOQ, tạm ứng 103,5 tỷ & 30 việc trên Đường Găng (Critical Path).\n"
            f"• 🧠 *Não bộ Google Gemini AI:* Tham vấn pháp lý, claim bù giá & đối đáp tổ đội/TVGS tức thì.\n\n"
            f"👉 *Bạn có thể chọn nhanh các nút menu bên dưới hoặc gõ thẳng bất kỳ câu hỏi nào!*"
        )
        self.client.send_message(chat_id, msg, reply_markup=self.get_main_keyboard())

    def handle_help(self, chat_id: int):
        """Xử lý lệnh /help hoặc Hướng dẫn."""
        msg = (
            "📖 *CẨM NANG SỬ DỤNG TRỢ LÝ SU SU QUA TELEGRAM:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💬 *1. Hỏi đáp AI tự nhiên:*\n"
            "Gõ bất kỳ câu hỏi nào như đang chat với chuyên gia QS & Cố vấn GĐDA:\n"
            "• _\"Nghiệm thu cọc khoan nhồi cần lưu ý biên bản gì?\"_\n"
            "• _\"Gặp mưa bão dừng thi công thì làm thủ tục claim gia hạn thế nào?\"_\n"
            "• _\"Thời gian tạm ứng và tỷ lệ giữ lại của dự án Vietstar?\"_\n\n"
            "👑 *2. Bộ công cụ Tham mưu Giám đốc Dự án (GĐDA):*\n"
            "• `/thammuu` : Bản tin tổng hợp 1 trang trước giờ họp giao ban CĐT.\n"
            "• `/giaoviec` : Ma trận phân công giao việc & điều phối hiện trường.\n"
            "• `/claim <nội dung>` : Ghi nhanh sự kiện cản trở để đòi EOT & bù tiền.\n"
            "• `/risk <nội dung>` : Ghi nhanh rủi ro hiện trường vào Sổ đăng ký rủi ro.\n"
            "• `/subcon <nội dung>` : Ghi nhanh đánh giá & đơn giá thầu phụ, tổ đội.\n"
            "• `/mom <nội dung>` : Ghi nhanh cam kết biên bản họp làm vũ khí đàm phán.\n"
            "• `/baolanh` : Báo cáo dòng tiền, tiến độ duyệt IPC 01 & bảo lãnh ngân hàng.\n"
            "• `/outlook` : Bản tin tình báo thư từ Outlook (Báo giá 657tr, họp 3 bên, đệ trình).\n"
            "• `/sync_mail` : Quét & đồng bộ ngay hộp thư Outlook Desktop vào Su Su.\n"
            "• `/autosync` : Trạng thái cơ chế tự động quét Outlook 30 phút/lần.\n\n"
            "🌟 *3. Các lệnh tra cứu nhanh tác nghiệp:*\n"
            "• `/14bai` : Xem chi tiết 14 bài học hôm nay (kèm nút lật thẻ).\n"
            "• `/tuvi` : Xem lịch vạn niên, giờ hoàng đạo đổ bê tông & tử vi.\n"
            "• `/tasks` : Xem danh sách công việc Sổ tay G-Tasks (Dự án VST).\n"
            "• `/task <nội dung>` : Thêm nhanh công việc vào Sổ tay.\n"
            "• `/duan` : Xem bảng tài chính và tiến độ dự án Vietstar 344 tỷ.\n"
            "• `/tk <từ khóa>` : Tra cứu kho tri thức 5.449 tình huống.\n\n"
            "💡 *Mẹo:* Bạn có thể bấm thẳng vào các nút trên bàn phím menu bên dưới!"
        )
        self.client.send_message(chat_id, msg)

    def handle_14_scenarios(self, chat_id: int, card_idx: int = 0):
        """Xử lý hiển thị 14 tình huống hôm nay theo chuẩn thẻ Desktop (Lật thẻ từng bài)."""
        daily_path = DATA_DIR / "14_tinh_huong_hom_nay.json"
        if not daily_path.exists():
            daily_path = Path(r"C:\QS_Hien\Data\14_tinh_huong_hom_nay.json")
        if not daily_path.exists():
            daily_path = Path("/app/Data/14_tinh_huong_hom_nay.json")

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

        total = len(scenarios)
        idx = max(0, min(total - 1, card_idx))
        sc = scenarios[idx]

        pillar_code = sc.get("TruCot", "CHUNG")
        pillar_label = PILLAR_TAGS.get(pillar_code, "📌 THỰC CHIẾN CHUYÊN SÂU")

        title = sc.get("TieuDe") or sc.get("TenTinhHuong") or "Tình huống thực tế"
        context = sc.get("BoiCanh", "")
        risk = sc.get("RuiRo", "")
        solution = sc.get("ChienLuocXuLy", "")
        dialogue = sc.get("CauThoaiMau", "")
        lesson = sc.get("BaiHocXuongMau", "")

        card_lines = [
            f"🌟 *BÀI HỌC THỰC CHIẾN HÔM NAY* (Thẻ {idx + 1}/{total} | ⚡ *Streak: 2 Ngày*)",
            f"🏷️ *Trụ cột:* `{pillar_label}`",
            "━━━━━━━━━━━━━━━━━━━━",
            f"📌 *{title}*\n"
        ]
        if context:
            card_lines.append(f"📍 *BỐI CẢNH CÔNG TRƯỜNG:*\n{context}\n")
        if risk:
            card_lines.append(f"⚠️ *CẠM BẪY & RỦI RO:*\n{risk}\n")
        if solution:
            card_lines.append(f"🛠️ *CHIẾN LƯỢC XỬ LÝ:*\n{solution}\n")
        if dialogue:
            card_lines.append(f"💬 *CÂU THOẠI MẪU / CÔNG VĂN MẪU:*\n_{dialogue}_\n")
        if lesson:
            card_lines.append(f"💎 *ĐÚC KẾT XƯƠNG MÁU:*\n👉 *{lesson}*")

        prev_i = (idx - 1) % total
        next_i = (idx + 1) % total

        markup = {
            "inline_keyboard": [
                [
                    {"text": "◀ Trước", "callback_data": f"card_{prev_i}"},
                    {"text": f"Thẻ {idx + 1}/{total}", "callback_data": "card_list"},
                    {"text": "Tiếp ▶", "callback_data": f"card_{next_i}"}
                ],
                [
                    {"text": "📋 Xem Mục Lục 14 Bài", "callback_data": "card_list"},
                    {"text": "🔄 Đổi 14 Bài Mới", "callback_data": "card_shuffle"}
                ]
            ]
        }
        self.client.send_message(chat_id, "\n".join(card_lines), reply_markup=markup)

    def handle_14_list(self, chat_id: int):
        """Hiển thị mục lục 14 bài học hôm nay kèm nút bấm chọn nhanh từng thẻ."""
        daily_path = DATA_DIR / "14_tinh_huong_hom_nay.json"
        if not daily_path.exists():
            daily_path = Path(r"C:\QS_Hien\Data\14_tinh_huong_hom_nay.json")
        if not daily_path.exists():
            daily_path = Path("/app/Data/14_tinh_huong_hom_nay.json")

        scenarios = []
        if daily_path.exists():
            try:
                with open(daily_path, "r", encoding="utf-8") as f:
                    scenarios = json.load(f)
            except Exception:
                pass

        if not scenarios:
            self.client.send_message(chat_id, "⚠️ Hiện tại chưa có dữ liệu 14 bài học hôm nay.")
            return

        lines = [
            "📋 *MỤC LỤC 14 BÀI HỌC THỰC CHIẾN HÔM NAY:*",
            "━━━━━━━━━━━━━━━━━━━━"
        ]
        for i, sc in enumerate(scenarios, 1):
            title = sc.get("TieuDe") or sc.get("TenTinhHuong") or "Tình huống thực chiến"
            pillar = sc.get("TruCot", "CHUNG")
            tag = PILLAR_TAGS.get(pillar, "📌")
            lines.append(f"*{i}.* `{tag}`\n   👉 *{title}*")

        lines.append("\n_(Bấm nút bên dưới để mở thẳng thẻ chi tiết:)_")

        row1 = [{"text": f"Thẻ {i}", "callback_data": f"card_{i-1}"} for i in range(1, 6)]
        row2 = [{"text": f"Thẻ {i}", "callback_data": f"card_{i-1}"} for i in range(6, 11)]
        row3 = [{"text": f"Thẻ {i}", "callback_data": f"card_{i-1}"} for i in range(11, min(15, len(scenarios) + 1))]

        markup = {"inline_keyboard": [row1, row2, row3]}
        self.client.send_message(chat_id, "\n".join(lines), reply_markup=markup)

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
            pillar_label = PILLAR_TAGS.get(pillar, pillar or "THỰC CHIẾN")
            context = data.get("BoiCanh") or ""
            sol = data.get("ChienLuocXuLy") or ""
            quote = data.get("CauThoaiMau") or ""
            lesson = data.get("BaiHocXuongMau") or ""

            lines.append(f"━━━━━━━━━━━━━━━━━━━━\n📌 *BÀI HỌC #{idx}: {title}*")
            if pillar:
                lines.append(f"🏷️ *Trụ cột:* `{pillar_label}`")
            if context:
                lines.append(f"📍 *Bối cảnh:* {context[:250]}...")
            if sol:
                lines.append(f"🛠️ *Chiến lược xử lý:* {sol[:300]}...")
            if quote:
                lines.append(f"💬 *Câu thoại mẫu:* _{quote}_")
            if lesson:
                lines.append(f"💎 *Đúc kết xương máu:* *{lesson}*")

        self.client.send_message(chat_id, "\n\n".join(lines))

    def handle_project_dossier(self, chat_id: int):
        """Xem tóm tắt hồ sơ dự án Vietstar chi tiết như giao diện Desktop."""
        dossier_file = DATA_DIR / "current_project_dossier.json"
        if not dossier_file.exists():
            dossier_file = Path(r"C:\QS_Hien\Data\current_project_dossier.json")
        if not dossier_file.exists():
            dossier_file = Path("/app/Data/current_project_dossier.json")

        if not dossier_file.exists():
            self.client.send_message(chat_id, "⚠️ Chưa tìm thấy tệp hồ sơ dự án `current_project_dossier.json` trên hệ thống.")
            return

        try:
            with open(dossier_file, "r", encoding="utf-8") as f:
                dossier = json.load(f)
        except Exception as e:
            self.client.send_message(chat_id, f"⚠️ Lỗi đọc hồ sơ dự án: {e}")
            return

        contract = dossier.get("contract") or dossier.get("contract_data") or {}
        boq = dossier.get("boq") or dossier.get("boq_data") or {}
        sched = dossier.get("schedule") or dossier.get("schedule_data") or {}

        p_name = contract.get("project_name", "TCXD HẠNG MỤC HỐ RÁC LÒ ĐỐT - NHÀ MÁY VIETSTAR")
        employer = contract.get("employer", "CÔNG TY CỔ PHẦN VIETSTAR")
        contractor = contract.get("contractor", "CÔNG TY CP ĐẦU TƯ XÂY DỰNG NOVACONS")
        if not contractor or len(contractor.strip()) < 5:
            contractor = "CÔNG TY CP ĐẦU TƯ XÂY DỰNG NOVACONS"

        val_vat = contract.get("contract_value_vat") or 344886779000
        val_no_vat = contract.get("contract_value_before_tax") or 319339610185
        adv = contract.get("advance_payment_val") or 95801883055
        vat_tax = contract.get("vat_amount") or 25547168815
        item_count = boq.get("total_items") or 222
        crit_count = len(sched.get("critical_tasks", [])) or sched.get("critical_tasks_count") or 30
        dur = contract.get("duration_days") or sched.get("total_duration_days", 210)

        msg = (
            f"🏢 *HỒ SƠ ĐIỀU HÀNH DỰ ÁN VIETSTAR - NOVACONS*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Dự án:* {p_name}\n"
            f"👷 *Chủ đầu tư:* {employer}\n"
            f"🏗️ *Tổng thầu thi công:* {contractor}\n"
            f"📍 *Địa điểm:* Huyện Củ Chi, TP. Hồ Chí Minh\n"
            f"📋 *Loại hợp đồng:* Đơn giá cố định | *Thời gian:* {dur} ngày\n\n"
            f"💰 *BẢNG TÀI CHÍNH DÒNG TIỀN CỐT TỬ:*\n"
            f"• **Giá trị HĐ (đã gồm 8% VAT):** `{val_vat:,.0f} VNĐ` (*~344,89 Tỷ*)\n"
            f"• **Giá trị trước thuế:** `{val_no_vat:,.0f} VNĐ` (*~319,34 Tỷ*)\n"
            f"• **Thuế VAT (8%):** `{vat_tax:,.0f} VNĐ` (*~25,55 Tỷ*)\n"
            f"• **Tạm ứng đợt 1 (30%):** `{adv:,.0f} VNĐ` (*~95,80 Tỷ*)\n"
            f"  _(Giải ngân trong 7 ngày sau khi phát hành Thư bảo lãnh tạm ứng)_\n"
            f"• **Bảo đảm bảo hành:** Giữ lại `5%` giá trị quyết toán (chưa VAT) hoặc Thư bảo lãnh 24 tháng\n\n"
            f"📊 *KHỐI LƯỢNG BOQ (222 ĐẦU VIỆC CHÍNH):*\n"
            f"1. Thi công cọc bê tông D500 & ép cọc cừ larsen\n"
            f"2. Bê tông lót & bê tông đài giằng móng\n"
            f"3. Cốt thép móng & vách hố rác CB400\n"
            f"4. Đào đất hố rác & đắp đất hoàn trả\n"
            f"5. Tường vây & hệ shoring chống đỡ hầm hố rác\n\n"
            f"⏱️ *TIẾN ĐỘ & ĐƯỜNG GĂNG ({crit_count} VIỆC GĂNG THEN CHỐT):*\n"
            f"1. Ép cọc thử & Thí nghiệm nén tĩnh cọc\n"
            f"2. Thi công cọc đại trà trục 1 - trục 8\n"
            f"3. Đào đất hầm hố rác phân đoạn 1 & giằng chống shoring\n"
            f"4. Đổ bê tông đài giằng móng & bản đáy hố rác\n"
            f"5. Đổ bê tông vách hầm hố rác & chống thấm chuyên dụng\n\n"
            f"💡 _(Toàn bộ điều khoản hợp đồng & BOQ đã nạp vào Não bộ RAG Su Su)_"
        )

        markup = {
            "inline_keyboard": [
                [
                    {"text": "🌟 14 Bài Học Hôm Nay", "callback_data": "card_0"},
                    {"text": "📋 Danh Sách Tasks", "callback_data": "tasks_list"}
                ]
            ]
        }
        self.client.send_message(chat_id, msg, reply_markup=markup)

    def handle_biorhythm_tuvi(self, chat_id: int, offset_days: int = 0):
        """Tính toán nhịp sinh học, lịch âm, giờ hoàng đạo và tử vi hiện trường chi tiết chuẩn Desktop."""
        try:
            try:
                from qshien.desktop_assistant.tuvi_holidays import get_tuvi_analysis, get_vietnamese_holidays
                from qshien.desktop_assistant.lunar_biorhythm import calculate_biorhythm, get_can_chi
            except ImportError:
                from tuvi_holidays import get_tuvi_analysis, get_vietnamese_holidays
                from lunar_biorhythm import calculate_biorhythm, get_can_chi

            target_date = datetime.date.today() + datetime.timedelta(days=offset_days)
            birth = datetime.date(1994, 3, 3)

            tuvi = get_tuvi_analysis(birth, target_date, "Kỹ sư Hiền")
            holidays = get_vietnamese_holidays(target_date)
            lunar = get_can_chi(target_date.day, target_date.month, target_date.year)
            bio = calculate_biorhythm(birth, target_date)

            def make_bar(val: float) -> str:
                norm = int((val + 100) / 40)
                norm = max(0, min(5, norm))
                return "🟩" * norm + "⬜" * (5 - norm)

            thu_names = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
            thu_str = thu_names[target_date.weekday()]
            is_hd = lunar.get("is_hoang_dao_day", False)
            hd_badge = "🌟 HOÀNG ĐẠO (CÁT LÀNH)" if is_hd else "⚖️ BÌNH HÒA"

            event_str = ""
            up_hols = holidays.get("upcoming_holidays", [])
            if up_hols:
                h = up_hols[0]
                event_str = f"► *SẮP TỚI:* {h.get('name')} (còn *{h.get('days_left')} ngày* - {h.get('date_solar')})\n━━━━━━━━━━━━━━━━━━━━\n"

            lunar_dd = lunar["lunar_day"]
            lunar_mm = lunar["lunar_month"]
            lunar_yy = lunar["nam_can_chi"]

            hoang_dao_list = lunar.get("hoang_dao_hours", [])
            hd_hours_str = " | ".join(hoang_dao_list) if hoang_dao_list else "Đang cập nhật"

            p_val = bio["physical"]
            e_val = bio["emotional"]
            i_val = bio["intellectual"]

            p_comment = "Sung mãn, thích hợp đi kiểm tra hiện trường" if p_val > 0 else "Cần giữ sức, tránh làm việc nặng quá sức"
            e_comment = "Tâm lý tự tin, đàm phán thương thảo thuận lợi" if e_val > 0 else "Nên giữ bình tĩnh, tránh nóng giận với tổ đội"
            i_comment = "Đầu óc minh mẫn, soi BOQ và hợp đồng cực chuẩn" if i_val > 0 else "Cần rà soát kỹ bảng tính số liệu, tránh vội vàng"

            lines = [
                f"{event_str}📅 *LỊCH VẠN NIÊN & HIỆN TRƯỜNG* | `{hd_badge}`",
                f"*{thu_str}, {target_date.strftime('%d/%m/%Y')}* ➔ *Âm lịch:* `{lunar_dd:02d}/{lunar_mm:02d}/{lunar_yy}`",
                f"• *Ngày:* `{lunar['ngay_can_chi']}` | *Tháng:* `{lunar['thang_can_chi']}` | *Năm:* `{lunar['nam_can_chi']}` | *Tiết:* `{lunar['tiet_khi']}`",
                f"• *Trực:* `Trực {tuvi.get('truc_name')} ({tuvi.get('truc_eval')})` - {tuvi.get('truc_meaning')}",
                f"  👉 _{tuvi.get('truc_advice')}_",
                f"• *Sao:* `Sao {tuvi.get('sao_name')} ({tuvi.get('sao_animal')}) - {tuvi.get('sao_type')}`",
                f"  👉 _{tuvi.get('sao_desc')}_\n",
                f"⏰ *GIỜ HOÀNG ĐẠO (Khởi công / Đổ bê tông / Cất nóc / Ký HĐ):*\n👉 `{hd_hours_str}`\n",
                f"🧭 *HƯỚNG XUẤT HÀNH TỐT:*",
                f"• 💖 *Hỷ Thần:* Hướng `{lunar.get('hy_thanh', 'Đông Bắc')}`",
                f"• 💰 *Tài Thần:* Hướng `{lunar.get('tai_thanh', 'Chính Nam')}`\n",
                f"✅ *VIỆC NÊN LÀM:*",
                f"{lunar.get('viec_nen') or tuvi.get('truc_advice')}\n",
                f"⚠️ *CẦN CẨN TRỌNG:*",
                f"{lunar.get('viec_kieng')}. *Tuổi xung ngày:* `{tuvi.get('tuoi_xung_ngay', 'Không có')}`.\n",
                "━━━━━━━━━━━━━━━━━━━━",
                "🧘 *TỬ VI BẢN MỆNH KỸ SƯ (Giáp Tuất 1994 - Sơn Đầu Hỏa):*",
                f"• *Bản mệnh:* `Sơn Đầu Hỏa` | *Khí vận ngày:* `{tuvi.get('day_napam', '')}`",
                f"• *Ngũ hành:* {tuvi.get('nguhanh_status', '')}",
                f"  _{tuvi.get('nguhanh_detail', '')}_",
                f"• *Địa chi:* `{tuvi.get('chi_badge', '')}` - {tuvi.get('chi_status', '')}",
                f"• *Điểm số vận thế:* `{tuvi.get('overall_score', 80)}/100` ➔ *{tuvi.get('rate_text', '')}*\n",
                "━━━━━━━━━━━━━━━━━━━━",
                "📈 *NHỊP SINH HỌC BIORHYTHM (NĂNG LƯỢNG NGÀY):*",
                f"• 💪 *Thể chất (P):* {make_bar(p_val)} `{p_val:+.1f}%` ({p_comment})",
                f"• ❤️ *Cảm xúc (E):* {make_bar(e_val)} `{e_val:+.1f}%` ({e_comment})",
                f"• 🧠 *Trí tuệ (I):* {make_bar(i_val)} `{i_val:+.1f}%` ({i_comment})"
            ]

            markup = {
                "inline_keyboard": [
                    [
                        {"text": "⏪ Hôm qua", "callback_data": f"tuvi_{offset_days - 1}"},
                        {"text": "📅 Hôm nay", "callback_data": "tuvi_0"},
                        {"text": "Ngày mai ⏩", "callback_data": f"tuvi_{offset_days + 1}"}
                    ]
                ]
            }
            self.client.send_message(chat_id, "\n".join(lines), reply_markup=markup)
        except Exception as e:
            self.client.send_message(chat_id, f"⚠️ Lỗi tính toán nhịp sinh học và tử vi: {e}")

    def handle_tasks(self, chat_id: int):
        """Xem danh sách công việc G-Tasks / Sổ tay chuẩn Desktop."""
        notes_file = DATA_DIR / "user_personal_notes.json"
        if not notes_file.exists():
            notes_file = Path(r"C:\QS_Hien\Data\user_personal_notes.json")
        if not notes_file.exists():
            notes_file = Path("/app/Data/user_personal_notes.json")

        tasks = []
        if notes_file.exists():
            try:
                with open(notes_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    tasks = data.get("tasks", [])
            except Exception:
                pass

        if not tasks:
            msg = (
                "📋 *SỔ TAY CÔNG VIỆC G-TASKS (DỰ ÁN VST):*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Chưa có công việc nào trong danh sách.\n\n"
                "👉 Hãy thêm việc mới bằng lệnh: `/task <nội dung>`\n"
                "_(Ví dụ: `/task Nghiệm thu cốt thép đài móng trục 1-4 lúc 15h`)_"
            )
            self.client.send_message(chat_id, msg)
            return

        pending = [t for t in tasks if not t.get("completed")]
        completed = [t for t in tasks if t.get("completed")]
        total = len(tasks)
        done_cnt = len(completed)
        pct = int((done_cnt / total) * 100) if total > 0 else 0

        lines = [
            "📋 *SỔ TAY CÔNG VIỆC G-TASKS (DỰ ÁN VST)*",
            "━━━━━━━━━━━━━━━━━━━━",
            f"📊 *Tiến độ:* Đã xong *{done_cnt}/{total}* việc (`{pct}%`) | Cần làm: *{len(pending)}* việc\n",
            "⏳ *DANH SÁCH VIỆC CẦN LÀM:"
        ]

        for idx, t in enumerate(pending[:8], 1):
            star = "⭐ " if t.get("starred") else "▫️ "
            title = t.get("title", "")
            details = t.get("details", "")
            due = t.get("due_date", "")

            lines.append(f"*{idx}.* {star}*{title}*")
            if details:
                lines.append(f"   📝 _{details}_")
            if due:
                lines.append(f"   🕒 Hạn chót: `{due}`")
            lines.append("")

        if len(pending) > 8:
            lines.append(f"_(Và còn {len(pending) - 8} công việc khác...)_\n")

        if completed:
            lines.append("━━━━━━━━━━━━━━━━━━━━\n✔ *ĐÃ HOÀN THÀNH:*")
            for t in completed[:4]:
                lines.append(f"• ~{t.get('title', '')}~")

        lines.append("\n👉 *Thêm việc mới:* Gõ `/task <nội dung việc>`")
        lines.append("_(Ví dụ: `/task Đổ bê tông dầm sàn tầng 3 lúc 17h`)_")

        markup = {
            "inline_keyboard": [
                [
                    {"text": "🔄 Làm Mới Danh Sách", "callback_data": "tasks_list"},
                    {"text": "🏢 Hồ Sơ Dự Án", "callback_data": "duan"}
                ]
            ]
        }
        self.client.send_message(chat_id, "\n".join(lines), reply_markup=markup)

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
    # THAM MƯU CHIẾN LƯỢC CHO GIÁM ĐỐC DỰ ÁN (GĐDA)
    # =========================================================================

    def _get_exec_engine(self):
        try:
            from qshien.desktop_assistant.project_executive_engine import get_executive_engine
            return get_executive_engine()
        except Exception:
            try:
                from project_executive_engine import get_executive_engine
                return get_executive_engine()
            except Exception:
                return None

    def handle_executive_briefing(self, chat_id: int):
        """Xử lý xuất bản tin tham mưu 1 trang cho Giám đốc Dự án."""
        eng = self._get_exec_engine()
        if not eng:
            self.client.send_message(chat_id, "⚠️ Đang tải động cơ tham mưu GĐDA, vui lòng thử lại sau.")
            return

        summary = eng.get_executive_briefing_summary()
        markup = {
            "inline_keyboard": [
                [
                    {"text": "📄 Hồ Sơ Claim & EOT", "callback_data": "exec_claims"},
                    {"text": "💰 Dòng Tiền & Bảo Lãnh", "callback_data": "exec_cashflow"}
                ],
                [
                    {"text": "📋 Phân Công Giao Việc", "callback_data": "exec_delegation"},
                    {"text": "🤝 Cam Kết MOM", "callback_data": "exec_mom"}
                ],
                [
                    {"text": "🚨 Sổ Rủi Ro Đỏ/Cam", "callback_data": "exec_risks"},
                    {"text": "👷 Tình Báo Thầu Phụ", "callback_data": "exec_subcon"}
                ],
                [
                    {"text": "📧 Hộp Thư Outlook", "callback_data": "outlook_briefing"},
                    {"text": "🔄 Cập Nhật Bản Tin", "callback_data": "exec_summary"}
                ]
            ]
        }
        self.client.send_message(chat_id, summary, reply_markup=markup)

    def handle_task_delegation(self, chat_id: int):
        """Báo cáo ma trận phân công giao việc và điều phối công trường cho GĐDA."""
        eng = self._get_exec_engine()
        if eng:
            msg = eng.get_task_delegation_report()
            markup = {
                "inline_keyboard": [
                    [
                        {"text": "🤝 Xem Cam Kết MOM", "callback_data": "exec_mom"},
                        {"text": "📧 Hộp Thư Outlook", "callback_data": "outlook_briefing"}
                    ],
                    [{"text": "◀ Quay Lại Bản Tin GĐDA", "callback_data": "exec_summary"}]
                ]
            }
            self.client.send_message(chat_id, msg, reply_markup=markup)

    def handle_executive_claims(self, chat_id: int):
        eng = self._get_exec_engine()
        if eng:
            msg = eng.get_claims_report()
            markup = {"inline_keyboard": [[{"text": "◀ Quay Lại Bản Tin GĐDA", "callback_data": "exec_summary"}]]}
            self.client.send_message(chat_id, msg, reply_markup=markup)

    def handle_executive_cashflow(self, chat_id: int):
        eng = self._get_exec_engine()
        if eng:
            msg = eng.get_cashflow_report()
            markup = {"inline_keyboard": [[{"text": "◀ Quay Lại Bản Tin GĐDA", "callback_data": "exec_summary"}]]}
            self.client.send_message(chat_id, msg, reply_markup=markup)

    def handle_executive_risks(self, chat_id: int):
        eng = self._get_exec_engine()
        if eng:
            msg = eng.get_risk_report()
            markup = {"inline_keyboard": [[{"text": "◀ Quay Lại Bản Tin GĐDA", "callback_data": "exec_summary"}]]}
            self.client.send_message(chat_id, msg, reply_markup=markup)

    def handle_executive_mom(self, chat_id: int):
        eng = self._get_exec_engine()
        if eng:
            msg = eng.get_mom_report()
            markup = {"inline_keyboard": [[{"text": "◀ Quay Lại Bản Tin GĐDA", "callback_data": "exec_summary"}]]}
            self.client.send_message(chat_id, msg, reply_markup=markup)

    def handle_executive_subcon(self, chat_id: int):
        eng = self._get_exec_engine()
        if eng:
            msg = eng.get_subcontractor_report()
            markup = {"inline_keyboard": [[{"text": "◀ Quay Lại Bản Tin GĐDA", "callback_data": "exec_summary"}]]}
            self.client.send_message(chat_id, msg, reply_markup=markup)

    def handle_add_claim(self, chat_id: int, content: str):
        content = content.strip()
        if not content:
            self.client.send_message(chat_id, "💡 Cú pháp: `/claim <nội dung sự kiện cản trở / chậm trễ>`\nVí dụ: `/claim CĐT chậm bàn giao mốc Ram dốc 7 ngày`")
            return
        eng = self._get_exec_engine()
        if eng:
            item = eng.add_claim(title=content, delay_days=7)
            self.client.send_message(
                chat_id,
                f"✅ *ĐÃ LƯU SỰ KIỆN CLAIM VÀO HỒ SƠ PHÁP LÝ GĐDA:*\n\n"
                f"📌 *Mã hiệu:* `{item['id']}`\n"
                f"📝 *Tiêu đề:* {item['title']}\n"
                f"⚖️ *Căn cứ:* Điều 5 & Điều 7 HĐ Vietstar (Hạn Notice of Delay: 07 ngày)\n\n"
                f"👉 Bấm `/thammuu` để xem bản tin tổng hợp."
            )

    def handle_add_risk(self, chat_id: int, content: str):
        content = content.strip()
        if not content:
            self.client.send_message(chat_id, "💡 Cú pháp: `/risk <nội dung rủi ro hiện trường>`\nVí dụ: `/risk Mực nước ngầm dâng cao tại hố móng phân đoạn 2`")
            return
        eng = self._get_exec_engine()
        if eng:
            item = eng.add_risk(title=content, level="CAM")
            self.client.send_message(
                chat_id,
                f"🚨 *ĐÃ GHI NHẬN RỦI RO MỚI VÀO SỔ ĐĂNG KÝ (RISK REGISTER):*\n\n"
                f"📌 *Mã hiệu:* `{item['id']}`\n"
                f"⚠️ *Nội dung:* {item['title']}\n"
                f"📊 *Cấp độ:* {item['risk_level']}\n\n"
                f"👉 Bấm `/thammuu` để cập nhật ma trận rủi ro."
            )

    def handle_add_subcon(self, chat_id: int, content: str):
        content = content.strip()
        if not content:
            self.client.send_message(chat_id, "💡 Cú pháp: `/subcon <Tên thầu phụ> - <Gói thầu/Đơn giá>`\nVí dụ: `/subcon Đội thép anh Minh - Gia công 3.000 đ/kg`")
            return
        eng = self._get_exec_engine()
        if eng:
            parts = [p.strip() for p in content.split("-", 1)]
            name = parts[0]
            trade = parts[1] if len(parts) > 1 else "Thi công xây dựng"
            item = eng.add_subcontractor(name=name, trade=trade, deal_price=trade)
            self.client.send_message(
                chat_id,
                f"👷 *ĐÃ LƯU THÔNG TIN THẦU PHỤ / TỔ ĐỘI:*\n\n"
                f"📌 *Tên đơn vị:* {item['name']}\n"
                f"🏷️ *Gói thầu / Đơn giá:* {trade}\n\n"
                f"👉 Bấm `/thammuu` để xem danh bạ thầu phụ."
            )

    def handle_add_mom(self, chat_id: int, content: str):
        content = content.strip()
        if not content:
            self.client.send_message(chat_id, "💡 Cú pháp: `/mom <Nội dung cam kết> - <Bên chịu trách nhiệm>`\nVí dụ: `/mom Duyệt hồ sơ phát sinh trạm bơm - Ban QLDA CĐT`")
            return
        eng = self._get_exec_engine()
        if eng:
            parts = [p.strip() for p in content.split("-", 1)]
            comm = parts[0]
            party = parts[1] if len(parts) > 1 else "Chủ đầu tư Vietstar"
            item = eng.add_mom(commitment=comm, responsible_party=party)
            self.client.send_message(
                chat_id,
                f"🤝 *ĐÃ GHI NHẬN CAM KẾT BIÊN BẢN HỌP (MOM):*\n\n"
                f"📌 *Nội dung:* {item['commitment']}\n"
                f"👤 *Bên chịu trách nhiệm:* {item['responsible_party']}\n"
                f"🕒 *Hạn chót theo dõi:* `{item['deadline']}`\n\n"
                f"👉 Bấm `/thammuu` để cập nhật vũ khí đàm phán."
            )

    def handle_outlook_briefing(self, chat_id: int):
        """Báo cáo tình báo thư từ Outlook Dự án Vietstar."""
        eng = self._get_exec_engine()
        msg = ""
        if eng:
            msg = eng.get_outlook_briefing(days_back=10)
        if not msg:
            try:
                from qshien.desktop_assistant.outlook_sync_engine import get_outlook_engine
                msg = get_outlook_engine().get_executive_outlook_briefing(days_back=10)
            except Exception as e:
                msg = f"⚠️ Không thể đọc dữ liệu Outlook: {e}"

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🔄 Quét Lại Outlook", "callback_data": "outlook_sync"},
                    {"text": "💰 Xem Chi Tiết Báo Giá (657 tr)", "callback_data": "exec_claims"}
                ],
                [
                    {"text": "⏱️ Quét Tự Động 30 Phút", "callback_data": "outlook_autosync_status"},
                    {"text": "📝 Biên Bản Họp (MOM)", "callback_data": "exec_mom"}
                ],
                [
                    {"text": "📊 Bản Tin GĐDA", "callback_data": "exec_summary"}
                ]
            ]
        }
        self.client.send_message(chat_id, msg, reply_markup=keyboard)

    def handle_sync_outlook(self, chat_id: int):
        """Kích hoạt quét đồng bộ Outlook / IMAP tức thì."""
        self.client.send_message(chat_id, "⏳ *Đang quét đồng bộ hộp thư dự án (Outlook / IMAP)...* Vui lòng chờ vài giây...")
        try:
            try:
                from qshien.desktop_assistant.outlook_sync_engine import get_outlook_engine
            except ImportError:
                from outlook_sync_engine import get_outlook_engine

            engine = get_outlook_engine()
            res = None
            if sys.platform == "win32":
                try:
                    res = engine.sync_outlook_data(limit_per_folder=30, download_attachments=True)
                except Exception:
                    res = None

            if not res or not res.get("success"):
                res = engine.sync_imap_data(limit=20, download_attachments=True)

            if res.get("success"):
                new_cnt = res.get("new_emails", 0)
                tot_cnt = res.get("total_cached", 0)
                file_cnt = res.get("downloaded_files", 0)
                msg = (
                    f"✅ *ĐỒNG BỘ HỘP THƯ DỰ ÁN THÀNH CÔNG!*\n\n"
                    f"• 📩 Email mới phát hiện: `{new_cnt}` thư\n"
                    f"• 📚 Tổng số email trong kho: `{tot_cnt}` thư\n"
                    f"• 📎 File đính kèm đã tải về: `{file_cnt}` files (PDF, DOCX, XLSX)\n"
                    f"• 🎯 Đã cập nhật tự động vào: *Hồ sơ Claim EOT* & *Biên bản họp MOM*.\n\n"
                    f"👉 Bấm nút bên dưới để xem báo cáo chi tiết."
                )
            else:
                msg = f"⚠️ Kết nối hộp thư thất bại: {res.get('error', 'Lỗi không xác định')}"
        except Exception as e:
            msg = f"⚠️ Lỗi trong quá trình đồng bộ: {e}"

        markup = {
            "inline_keyboard": [
                [
                    {"text": "📧 Xem Báo Cáo Hộp Thư", "callback_data": "outlook_briefing"},
                    {"text": "⏱️ Trạng Thái Quét 30 Phút", "callback_data": "outlook_autosync_status"}
                ],
                [{"text": "📊 Về Bản Tin GĐDA", "callback_data": "exec_summary"}]
            ]
        }
        self.client.send_message(chat_id, msg, reply_markup=markup)

    def handle_autosync(self, chat_id: int):
        """Báo cáo trạng thái cơ chế tự động quét Outlook 30 phút/lần."""
        status_file = DATA_DIR / "outlook_sync" / "last_sync_status.json"
        status_data = {}
        if status_file.exists():
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    status_data = json.load(f)
            except Exception:
                pass

        last_check = status_data.get("last_check", "Chưa xác định")
        next_check = status_data.get("next_check", "30 phút sau")
        total_cached = status_data.get("total_cached", 91)
        downloaded = status_data.get("downloaded_files", 29)
        status_txt = status_data.get("status", "SUCCESS")

        msg = (
            "⏱️ *CƠ CHẾ TỰ ĐỘNG QUÉT OUTLOOK 30 PHÚT/LẦN*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🟢 *Trạng thái:* `ĐANG HOẠT ĐỘNG (ENABLED)`\n"
            "• ⚙️ *Tác vụ Windows:* `QSHien_SuSu_OutlookAutoSync_30Min`\n"
            "• 🔄 *Chu kỳ:* Đúng 30 phút quét ngầm bằng `pythonw.exe` (không làm gián đoạn màn hình)\n"
            f"• 🕒 *Lần quét gần nhất:* `{last_check}` (Trạng thái: `{status_txt}`)\n"
            f"• ⏳ *Lần quét tiếp theo:* `{next_check}`\n"
            f"• 📚 *Tổng số email đã nạp:* `{total_cached}` thư (gồm `hienpv` & `BCHVIETSTAR`)\n"
            f"• 📎 *Tệp tài liệu đính kèm:* `{downloaded}` tệp PDF, DOCX, XLSX\n\n"
            "🔔 *Cơ chế Báo động:* Su Su sẽ chủ động gửi tin nhắn Telegram tới anh ngay tức thì khi phát hiện:\n"
            "  1. Thư báo giá phát sinh ngoài HĐ hoặc điều chỉnh biện pháp thi công.\n"
            "  2. Thư mời họp kỹ thuật / biên bản giao ban công trường.\n"
            "  3. Ý kiến phê duyệt hoặc phản hồi từ TVGS / Chủ đầu tư."
        )

        markup = {
            "inline_keyboard": [
                [
                    {"text": "🔄 Quét Ngay Bây Giờ", "callback_data": "outlook_sync"},
                    {"text": "📧 Xem Báo Cáo Outlook", "callback_data": "outlook_briefing"}
                ],
                [{"text": "📊 Về Bản Tin GĐDA", "callback_data": "exec_summary"}]
            ]
        }
        self.client.send_message(chat_id, msg, reply_markup=markup)


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
                self.handle_14_scenarios(chat_id, 0)
            elif cb_data.startswith("card_"):
                act = cb_data[5:]
                if act == "list":
                    self.handle_14_list(chat_id)
                elif act == "shuffle":
                    self.handle_14_scenarios(chat_id, 0)
                else:
                    try:
                        idx = int(act)
                        self.handle_14_scenarios(chat_id, idx)
                    except ValueError:
                        self.handle_14_scenarios(chat_id, 0)
            elif cb_data.startswith("tuvi_"):
                try:
                    offset = int(cb_data[5:])
                    self.handle_biorhythm_tuvi(chat_id, offset_days=offset)
                except ValueError:
                    self.handle_biorhythm_tuvi(chat_id, 0)
            elif cb_data == "tasks_list":
                self.handle_tasks(chat_id)
            elif cb_data == "duan":
                self.handle_project_dossier(chat_id)
            elif cb_data == "exec_summary":
                self.handle_executive_briefing(chat_id)
            elif cb_data == "exec_claims":
                self.handle_executive_claims(chat_id)
            elif cb_data == "exec_cashflow":
                self.handle_executive_cashflow(chat_id)
            elif cb_data == "exec_risks":
                self.handle_executive_risks(chat_id)
            elif cb_data == "exec_mom":
                self.handle_executive_mom(chat_id)
            elif cb_data == "exec_subcon":
                self.handle_executive_subcon(chat_id)
            elif cb_data == "exec_delegation":
                self.handle_task_delegation(chat_id)
            elif cb_data == "outlook_briefing":
                self.handle_outlook_briefing(chat_id)
            elif cb_data == "outlook_sync":
                self.handle_sync_outlook(chat_id)
            elif cb_data == "outlook_autosync_status":
                self.handle_autosync(chat_id)
            elif cb_data in ("main_menu", "start", "menu_chinh"):
                self.handle_start(chat_id)
            elif cb_data in ("help", "huong_dan"):
                self.handle_help(chat_id)
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

        # 0. Tham Mưu Giám Đốc Dự Án (GĐDA) & Phân Công Giao Việc
        if any(kw in t_lower for kw in ("giao việc", "giao viec", "phan cong", "phân công", "điều phối", "dieu phoi", "ke hoach")) or t_lower in ("/giaoviec", "/kehoach", "/actions", "/phancong"):
            self.handle_task_delegation(chat_id)
            return

        if any(kw in t_lower for kw in ("tham mưu", "tham muu", "thammuu", "gđda", "gdda", "cố vấn", "bản tin gdda")) or t_lower.startswith("/thammuu"):
            self.handle_executive_briefing(chat_id)
            return

        if any(kw in t_lower for kw in ("bảo lãnh", "baolanh", "dòng tiền", "dong tien", "tiền về", "cashflow")) or t_lower.startswith("/baolanh"):
            self.handle_executive_cashflow(chat_id)
            return

        if t_lower in ("/claims", "claims", "claim", "/claim", "khiếu nại", "eot"):
            self.handle_executive_claims(chat_id)
            return

        if t_lower.startswith("/claim ") or t_lower.startswith("claim "):
            content = t_clean.split(" ", 1)[1]
            self.handle_add_claim(chat_id, content)
            return

        if t_lower in ("/risks", "risks", "rủi ro", "rui ro", "/risk"):
            self.handle_executive_risks(chat_id)
            return

        if t_lower.startswith("/risk ") or t_lower.startswith("risk "):
            content = t_clean.split(" ", 1)[1]
            self.handle_add_risk(chat_id, content)
            return

        if t_lower in ("/subcon", "subcon", "thầu phụ", "thau phu", "/thauphu"):
            self.handle_executive_subcon(chat_id)
            return

        if t_lower.startswith("/subcon ") or t_lower.startswith("subcon ") or t_lower.startswith("/thauphu ") or t_lower.startswith("thauphu "):
            content = t_clean.split(" ", 1)[1]
            self.handle_add_subcon(chat_id, content)
            return

        if t_lower in ("/mom", "mom", "biên bản họp", "bien ban hop", "giao ban"):
            self.handle_executive_mom(chat_id)
            return

        if t_lower.startswith("/mom ") or t_lower.startswith("mom "):
            content = t_clean.split(" ", 1)[1]
            self.handle_add_mom(chat_id, content)
            return

        # 0.6 Hộp thư Outlook & Đồng bộ thư từ
        if any(kw in t_lower for kw in ("outlook", "hộp thư", "hop thu", "email", "mail dự án", "thư từ", "thu tu")) or t_lower in ("/outlook", "/mail", "/email"):
            self.handle_outlook_briefing(chat_id)
            return

        if any(kw in t_lower for kw in ("quét outlook", "quet outlook", "đồng bộ outlook", "dong bo outlook", "sync outlook", "sync mail")) or t_lower in ("/sync_outlook", "/sync_mail"):
            self.handle_sync_outlook(chat_id)
            return

        if any(kw in t_lower for kw in ("autosync", "tự động quét", "tu dong quet", "30 phút", "30 phut", "chu kỳ quét")) or t_lower.startswith("/autosync"):
            self.handle_autosync(chat_id)
            return

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
        if any(kw in t_lower for kw in ("14 bài", "14 bai", "14bai", "bài học hôm nay", "bai hoc hom nay")) or t_lower.startswith("/14bai") or t_lower.startswith("/daily"):
            self.handle_14_scenarios(chat_id)
            return

        # 5. Hồ sơ dự án Vietstar
        if any(kw in t_lower for kw in ("vietstar", "hồ sơ dự án", "ho so du an")) or t_lower in ("/duan", "duan", "dự án", "du an", "/vietstar"):
            self.handle_project_dossier(chat_id)
            return

        # 6. Nhịp sinh học & Tử vi
        if any(kw in t_lower for kw in ("tử vi", "tuvi", "nhịp sinh học", "nhip sinh hoc", "lịch & nhịp", "ngày hoàng đạo")) or t_lower.startswith("/tuvi") or t_lower.startswith("/nhipsinhhoc"):
            self.handle_biorhythm_tuvi(chat_id)
            return

        # 7. Danh sách task công việc
        if any(kw in t_lower for kw in ("g-tasks", "gtasks", "sổ tay", "so tay", "danh sách g-tasks")) or t_lower in ("/tasks", "tasks", "/tasklist", "tasklist"):
            self.handle_tasks(chat_id)
            return

        # 8. Lưu task công việc
        if t_lower.startswith("/task ") or t_lower.startswith("task "):
            task_content = t_clean.split(" ", 1)[1]
            self.handle_add_task(chat_id, task_content)
            return

        # 9. Mọi câu hỏi thông thường -> chuyển cho Google Gemini AI + Vector RAG
        self.handle_natural_question(chat_id, t_clean)

    def start_polling(self):
        """Chạy vòng lặp nhận tin nhắn từ Telegram."""
        if not self.token:
            print("[TelegramBot] ⚠️ Chưa có Telegram Bot Token. Vui lòng cấu hình trong telegram_config.json")
            return

        import ctypes
        mutex = None
        if hasattr(ctypes, "windll"):
            try:
                kernel32 = ctypes.windll.kernel32
                mutex_name = "Global\\QSHien_SuSu_TelegramBot_Polling_Mutex"
                mutex = kernel32.CreateMutexW(None, False, mutex_name)
                if kernel32.GetLastError() == 183:
                    print("[TelegramBot] ⚠️ Đã có một tiến trình khác đang chạy Telegram Bot. Bỏ qua để tránh xung đột.")
                    return
            except Exception:
                pass

        self.bot_info = self.client.get_me()
        if not self.bot_info:
            print("[TelegramBot] ❌ Token không hợp lệ hoặc không thể kết nối tới Telegram API.")
            if mutex and hasattr(ctypes, "windll"):
                try:
                    kernel32 = ctypes.windll.kernel32
                    kernel32.CloseHandle(mutex)
                except Exception:
                    pass
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
            if mutex and hasattr(ctypes, "windll"):
                try:
                    kernel32 = ctypes.windll.kernel32
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
