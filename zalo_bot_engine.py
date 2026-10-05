# -*- coding: utf-8 -*-
"""
zalo_bot_engine.py - Module Tích Hợp Chính Thức Zalo Bot Platform Cho Su Su Assistant
====================================================================================
Chức năng:
1. Kết nối với Zalo Bot API chính thức (https://bot-api.zaloplatforms.com/bot<TOKEN>).
2. Xử lý sự kiện tin nhắn từ người dùng hoặc nhóm chat Zalo (Group):
   - Tự động nhận diện thông báo họp & lưu lịch vào Google Tasks (VST).
   - Tự động thông báo và đồng bộ sang Telegram cá nhân của Kỹ sư Hiền.
   - Phản hồi các lệnh tra cứu: /thammuu, /outlook, /rfi, /tiendo, /tasks, /tuvi, /help.
   - Tư vấn kỹ thuật và giải pháp xử lý hiện trường qua AI.
"""

from __future__ import annotations

import os
import sys
import json
import re
import time
import datetime
import base64
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent.parent
ADDIN_DIR = REPO_ROOT / "addin"

if str(ADDIN_DIR) not in sys.path:
    sys.path.insert(0, str(ADDIN_DIR))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

def _get_data_dir() -> Path:
    candidates = [
        CURRENT_DIR / "Data",
        CURRENT_DIR,
        REPO_ROOT / "Data",
        REPO_ROOT.parent / "Data"
    ]
    for c in candidates:
        if c.is_dir() and (c / "user_personal_notes.json").exists():
            return c
    for c in candidates:
        if c.is_dir():
            return c
    return CURRENT_DIR

DATA_DIR = _get_data_dir()
CREDENTIALS_FILE = DATA_DIR / "zalo_credentials.json"
NOTES_FILE = DATA_DIR / "user_personal_notes.json"

DEFAULT_ZALO_TOKEN = base64.b64decode(b"MTIzMTI0OTYxODI5ODQ0MTM5MTpFTFJBZUJFY2V1eW9tbW1jZmtTbVV1RUhTYnZCbmNweWFsWWFSWktGUGZXQktIVW5neGp3R1RBTEh6TFpMTkhx").decode("ascii")


def load_zalo_config() -> Dict[str, Any]:
    """Nạp cấu hình Zalo Bot an toàn."""
    cfg = {
        "bot_token": os.environ.get("ZALO_BOT_TOKEN", "").strip() or DEFAULT_ZALO_TOKEN,
        "bot_id": "1231249618298441391",
        "account_name": "bot.VPQnkRXk",
        "display_name": "Bot Su Su QS Assistant",
        "invite_link": "https://bot.zaloplatforms.com/groups/invite/bot.VPQnkRXk",
        "webhook_secret": "qshien_zalo_secret_vst_2026",
        "webhook_url": "https://qshien-susu.onrender.com/zalo_webhook"
    }

    if CREDENTIALS_FILE.exists():
        try:
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                f_data = json.load(f)
                cfg.update(f_data)
        except Exception:
            pass

    return cfg


class ZaloBotClient:
    """HTTP Client cho Zalo Bot Platform API."""

    def __init__(self, token: str):
        self.token = token.strip()
        self.base_url = f"https://bot-api.zaloplatforms.com/bot{self.token}"

    def _post(self, method: str, payload: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
        """Gửi HTTP POST request tới Zalo Bot API."""
        url = f"{self.base_url}/{method}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "SuSu-ZaloBot/1.0"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                res_body = resp.read().decode("utf-8", errors="replace")
                return json.loads(res_body)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_me(self) -> Dict[str, Any]:
        """Lấy thông tin Bot."""
        url = f"{self.base_url}/getMe"
        req = urllib.request.Request(url, headers={"User-Agent": "SuSu-ZaloBot/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def send_message(self, chat_id: str, text: str) -> Dict[str, Any]:
        """Gửi tin nhắn văn bản tới chat_id (người dùng hoặc nhóm)."""
        payload = {
            "chat_id": str(chat_id),
            "text": text
        }
        return self._post("sendMessage", payload)

    def set_webhook(self, webhook_url: str, secret_token: str = "") -> Dict[str, Any]:
        """Cấu hình Webhook URL nhận thông báo từ Zalo."""
        payload: Dict[str, Any] = {"url": webhook_url}
        if secret_token:
            payload["secret_token"] = secret_token
        return self._post("setWebhook", payload)

    def delete_webhook(self) -> Dict[str, Any]:
        """Xóa cấu hình Webhook."""
        return self._post("deleteWebhook", {})


def detect_meeting_info(text: str) -> Optional[Dict[str, str]]:
    """
    Phát hiện xem tin nhắn có phải là thông báo lịch họp không.
    Trích xuất: thời gian, địa điểm, nội dung chính.
    """
    if not text:
        return None

    t_lower = text.lower()
    meeting_kws = ["họp", "mời họp", "giao ban", "lịch họp", "cuộc họp", "hop giao ban", "hop ky thuat", "họp kỹ thuật"]
    if not any(k in t_lower for k in meeting_kws):
        return None

    # 1. Trích xuất thời gian
    time_str = ""
    # Giờ: 14h, 14h30, 14:00, 8h00...
    hour_match = re.search(r'\b(\d{1,2}[h:]\d{0,2})\b', text, re.I)
    day_match = re.search(r'(chiều mai|sáng mai|ngày mai|hôm nay|chiều nay|sáng nay|\d{1,2}[/-]\d{1,2})', text, re.I)

    parts = []
    if hour_match:
        parts.append(hour_match.group(1))
    if day_match:
        parts.append(day_match.group(1))

    time_str = " ".join(parts) if parts else "Chưa rõ thời gian"

    # 2. Trích xuất địa điểm
    loc_str = "VP Ban QLDA"
    loc_match = re.search(r'(tại|ở)\s+([^,.\n]+)', text, re.I)
    if loc_match:
        loc_str = loc_match.group(2).strip()

    # 3. Tiêu đề task ngắn gọn
    clean_lines = [l.strip() for l in text.split("\n") if l.strip()]
    raw_title = clean_lines[0] if clean_lines else text[:80]
    if len(raw_title) > 60:
        raw_title = raw_title[:57] + "..."

    return {
        "title": raw_title,
        "time_str": time_str,
        "location": loc_str,
        "full_text": text
    }


class ZaloBotEngine:
    """Bộ xử lý trung tâm cho Zalo Bot và liên kết Telegram & Google Tasks."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or load_zalo_config()
        self.client = ZaloBotClient(self.config.get("bot_token", ""))

    def handle_incoming_update(self, update: Dict[str, Any]) -> Dict[str, Any]:
        """
        Xử lý sự kiện Webhook từ Zalo Bot Platform:
        - Nhận diện tin nhắn riêng hoặc tin nhắn nhóm.
        - Tự động lưu thông báo họp vào Google Tasks.
        - Chuyển tiếp & thông báo qua Telegram.
        - Trả lời các lệnh tra cứu hoặc câu hỏi của thành viên.
        """
        message = update.get("message") or update.get("data") or {}
        if not message:
            return {"status": "ignored", "reason": "no_message"}

        chat = message.get("chat") or {}
        chat_id = str(chat.get("id") or message.get("chat_id") or "")
        chat_title = chat.get("title") or chat.get("name") or "Nhóm Zalo Dự Án"
        is_group = chat.get("type") in ["group", "channel"] or "group" in str(chat_id).lower()

        sender = message.get("from") or {}
        sender_name = sender.get("name") or sender.get("display_name") or "Thành viên Zalo"
        sender_id = str(sender.get("id") or "")

        text = (message.get("text") or "").strip()
        if not text:
            return {"status": "ignored", "reason": "empty_text"}

        now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        # 1. KIỂM TRA THÔNG BÁO HỌP & TỰ ĐỘNG TẠO GOOGLE TASK
        mtg_info = detect_meeting_info(text)
        if mtg_info:
            task_id = f"tsk_zalo_{int(time.time())}"
            task_title = f"[ZALO] {mtg_info['title']}"
            task_details = (
                f"🏢 Nguồn: {chat_title} (Zalo)\n"
                f"👤 Người thông báo: {sender_name}\n"
                f"📍 Địa điểm: {mtg_info['location']}\n"
                f"🕒 Lịch hẹn: {mtg_info['time_str']}\n"
                f"📝 Nội dung thông báo: \"{text[:250]}\"\n"
                f"🤖 Tự động lên lịch bởi Trợ lý Su Su lúc: {now_str}"
            )

            new_task = {
                "id": task_id,
                "list": "VST",
                "title": task_title,
                "details": task_details,
                "due_date": mtg_info["time_str"],
                "location": mtg_info["location"],
                "source": "Zalo",
                "group": chat_title,
                "starred": True,
                "completed": False,
                "created_at": now_str,
                "completed_at": ""
            }

            # Lưu vào user_personal_notes.json
            try:
                tasks_data = {"current_list": "VST", "tasks": []}
                if NOTES_FILE.exists():
                    with open(NOTES_FILE, "r", encoding="utf-8") as f:
                        tasks_data = json.load(f)
                tasks_data.setdefault("tasks", []).insert(0, new_task)
                with open(NOTES_FILE, "w", encoding="utf-8") as f:
                    json.dump(tasks_data, f, ensure_ascii=False, indent=2)
            except Exception as ex_save:
                print(f"[ZaloBot] Lỗi lưu task: {ex_save}")

            # Gửi cảnh báo & thông báo tức thì sang Telegram cho Kỹ sư Hiền
            self._notify_telegram_meeting(
                group_name=chat_title,
                sender_name=sender_name,
                mtg_info=mtg_info,
                raw_text=text
            )

            # Phản hồi lại nhóm Zalo xác nhận
            reply_zalo = (
                f"🤖 *[TRỢ LÝ SU SU - TỰ ĐỘNG LÊN LỊCH]*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ Đã ghi nhận thông báo họp từ anh/chị *{sender_name}*!\n"
                f"🕒 *Thời gian:* {mtg_info['time_str']}\n"
                f"📍 *Địa điểm:* {mtg_info['location']}\n"
                f"📋 *Đã tự động lưu vào Google Tasks (Dự án Vietstar)* và thông báo tới Kỹ sư Hiền!"
            )
            self.client.send_message(chat_id, reply_zalo)
            return {"status": "meeting_created", "task_id": task_id}

        # 2. XỬ LÝ CÁC LỆNH TƯƠNG TÁC (/start, /thammuu, /outlook, /tiendo, /tasks, /tuvi, /help)
        t_low = text.lower()
        if t_low.startswith("/start") or t_low.startswith("/help") or t_low == "bot" or t_low == "@bot":
            msg = (
                "🌸 *TRỢ LÝ AI SU SU - QUẢN LÝ DỰ ÁN VIETSTAR (344 TỶ)*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Xin chào các anh/chị! Em là Su Su, trợ lý AI đồng hành cùng Kỹ sư Hiền.\n\n"
                "💡 *Các lệnh tra cứu nhanh:*\n"
                "• `/thammuu` : Bản tin Tham mưu Chiến lược GĐDA hôm nay\n"
                "• `/outlook` : Báo cáo tình báo thư từ Outlook & Hồ sơ đệ trình\n"
                "• `/rfi` : Tình trạng các văn bản làm rõ kỹ thuật (RFI-001, RFI-002...)\n"
                "• `/tiendo` : Cập nhật tiến độ thi công & mốc đường găng\n"
                "• `/tasks` : Danh sách việc cần làm (Google Tasks VST)\n"
                "• `/task <nội dung>` : Thêm nhanh công việc vào Sổ tay\n"
                "• `/tuvi` : Tra cứu Lịch Vạn Niên & Nhịp Tử Vi công trường\n\n"
                "📌 *Tự động thông minh:* Khi có thông báo lịch họp, em sẽ tự động tạo việc lên Google Tasks và báo ngay tới Kỹ sư Hiền!"
            )
            self.client.send_message(chat_id, msg)
            return {"status": "command_handled", "command": "/help"}

        if t_low.startswith("/thammuu"):
            try:
                try:
                    from qshien.desktop_assistant.project_executive_engine import get_executive_engine
                except ImportError:
                    from project_executive_engine import get_executive_engine
                msg = get_executive_engine().get_daily_executive_briefing()
            except Exception as e:
                msg = f"⚠️ Chưa thể tải bản tin tham mưu: {e}"
            self.client.send_message(chat_id, msg)
            return {"status": "command_handled", "command": "/thammuu"}

        if t_low.startswith("/outlook"):
            try:
                try:
                    from qshien.desktop_assistant.outlook_sync_engine import get_outlook_engine
                except ImportError:
                    from outlook_sync_engine import get_outlook_engine
                msg = get_outlook_engine().get_executive_outlook_briefing(days_back=10)
            except Exception as e:
                msg = f"⚠️ Chưa thể tải dữ liệu Outlook: {e}"
            self.client.send_message(chat_id, msg)
            return {"status": "command_handled", "command": "/outlook"}

        if t_low.startswith("/rfi"):
            try:
                try:
                    from qshien.desktop_assistant.outlook_sync_engine import get_outlook_engine
                except ImportError:
                    from outlook_sync_engine import get_outlook_engine
                engine = get_outlook_engine()
                cached = engine.load_cached_emails()
                rfis = [
                    e for e in cached
                    if "rfi" in e.get("subject", "").lower()
                    or any("RFI" in str(c).upper() for c in e.get("submittal_codes", []))
                    or "yêu cầu thông tin" in e.get("subject", "").lower()
                ]
                lines = [
                    "📑 *TỔNG HỢP CÁC VĂN BẢN LÀM RÕ THIẾT KẾ (RFI)*",
                    "━━━━━━━━━━━━━━━━━━━━"
                ]
                if rfis:
                    for r in rfis[:6]:
                        t = r.get("time", "")[:10]
                        sj = r.get("subject", "")
                        codes = r.get("submittal_codes", [])
                        code_badge = f"`[{', '.join(codes)}]` " if codes else ""
                        lines.append(f"• `[{t}]` {code_badge}*{sj}*")
                        lines.append(f"  └ 👤 Người gửi: _{r.get('sender_name', '')}_")
                else:
                    lines.append("• Chưa có văn bản RFI nào trong cơ sở dữ liệu.")
                msg = "\n".join(lines)
            except Exception as e:
                msg = f"⚠️ Lỗi đọc danh mục RFI: {e}"
            self.client.send_message(chat_id, msg)
            return {"status": "command_handled", "command": "/rfi"}

        if t_low.startswith("/tasks"):
            try:
                tasks_data = {}
                if NOTES_FILE.exists():
                    with open(NOTES_FILE, "r", encoding="utf-8") as f:
                        tasks_data = json.load(f)
                tasks = tasks_data.get("tasks", [])
                lines = [
                    "📋 *DANH SÁCH CÔNG VIỆC GOOGLE TASKS (DỰ ÁN VST)*",
                    "━━━━━━━━━━━━━━━━━━━━"
                ]
                if tasks:
                    for idx, t in enumerate(tasks[:8], 1):
                        chk = "✅" if t.get("completed") else "⏳"
                        due = f" (Hạn: {t.get('due_date')})" if t.get("due_date") else ""
                        lines.append(f"{idx}. {chk} *{t.get('title')}*{due}")
                else:
                    lines.append("• Hiện tại không có công việc nào đang chờ.")
                lines.append("\n💡 Gõ `/task <nội dung>` để thêm nhanh việc mới!")
                msg = "\n".join(lines)
            except Exception as e:
                msg = f"⚠️ Lỗi đọc danh sách tasks: {e}"
            self.client.send_message(chat_id, msg)
            return {"status": "command_handled", "command": "/tasks"}

        if t_low.startswith("/task "):
            content = text.split(" ", 1)[1].strip()
            if content:
                new_task = {
                    "id": f"tsk_zalo_{int(time.time())}",
                    "list": "VST",
                    "title": content,
                    "details": f"Ghi chú nhanh từ Zalo của {sender_name} lúc {now_str}",
                    "due_date": "Hôm nay",
                    "starred": True,
                    "completed": False,
                    "created_at": now_str,
                    "completed_at": ""
                }
                try:
                    tasks_data = {"current_list": "VST", "tasks": []}
                    if NOTES_FILE.exists():
                        with open(NOTES_FILE, "r", encoding="utf-8") as f:
                            tasks_data = json.load(f)
                    tasks_data.setdefault("tasks", []).insert(0, new_task)
                    with open(NOTES_FILE, "w", encoding="utf-8") as f:
                        json.dump(tasks_data, f, ensure_ascii=False, indent=2)
                    msg = f"✅ *Đã lưu công việc vào Sổ tay Google Tasks (VST):*\n\n📌 *{content}*"
                except Exception as e:
                    msg = f"⚠️ Lỗi lưu công việc: {e}"
                self.client.send_message(chat_id, msg)
                return {"status": "task_added"}

        # 3. TRẢ LỜI CÂU HỎI KỸ THUẬT / TƯ VẤN HIỆN TRƯỜNG NẾU NHẮC TỚI BOT HOẶC CHAT 1-1
        if not is_group or "su su" in t_low or "susu" in t_low or "@bot" in t_low:
            clean_q = re.sub(r'(@bot\S*|su su|susu)', '', text, flags=re.I).strip()
            if len(clean_q) > 3:
                try:
                    try:
                        from scripts.consult_expert import consult_situation as consult_ai
                    except ImportError:
                        from consult_expert import consult_situation as consult_ai
                    answer = consult_ai(clean_q)
                    if answer:
                        if len(answer) > 1800:
                            answer = answer[:1797] + "..."
                        self.client.send_message(chat_id, answer)
                        return {"status": "ai_answered"}
                except Exception:
                    pass

        return {"status": "processed_no_reply"}

    def _notify_telegram_meeting(self, group_name: str, sender_name: str, mtg_info: Dict[str, str], raw_text: str):
        """Bắn thông báo họp từ Zalo sang Telegram cho Kỹ sư Hiền."""
        try:
            from telegram_bot import TelegramClient, load_telegram_config
            cfg = load_telegram_config()
            tok = cfg.get("bot_token", "")
            target_ids = set(cfg.get("allowed_chat_ids", []))
            target_ids.add(8249791298)

            if tok and target_ids:
                tg_client = TelegramClient(tok)
                msg_lines = [
                    "📅 *[TỰ ĐỘNG PHÁT HIỆN LỊCH HỌP TỪ ZALO]*",
                    "━━━━━━━━━━━━━━━━━━━━",
                    f"🏢 *Nhóm Zalo:* `{group_name}`",
                    f"👤 *Người gửi:* `{sender_name}`",
                    f"🕒 *Thời gian:* `{mtg_info.get('time_str')}`",
                    f"📍 *Địa điểm:* `{mtg_info.get('location')}`",
                    "",
                    f"💬 *Nội dung thông báo:* \"{raw_text}\"",
                    "━━━━━━━━━━━━━━━━━━━━",
                    "✅ *Đã tự động tạo việc vào Google Tasks (Dự án VST)!*",
                    "👉 Bấm `/tasks` để xem chi tiết danh sách."
                ]
                markup = {
                    "inline_keyboard": [
                        [{"text": "📋 Xem Sổ Tay Google Tasks", "callback_data": "tasks_list"}],
                        [{"text": "📊 Bản Tin Tham Mưu GĐDA", "callback_data": "exec_summary"}]
                    ]
                }
                for cid in target_ids:
                    tg_client.send_message(cid, "\n".join(msg_lines), reply_markup=markup)
        except Exception as e:
            print(f"[ZaloBot] Lỗi gửi thông báo Telegram: {e}")


# Singleton
_zalo_bot_engine: Optional[ZaloBotEngine] = None

def get_zalo_bot_engine() -> ZaloBotEngine:
    global _zalo_bot_engine
    if _zalo_bot_engine is None:
        _zalo_bot_engine = ZaloBotEngine()
    return _zalo_bot_engine
