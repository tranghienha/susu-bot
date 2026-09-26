# -*- coding: utf-8 -*-
"""
server.py - Google Cloud Run Serverless Webhook Cho Su Su Telegram Bot
=============================================================================
Triển khai trên Google Cloud Run:
- Tiếp nhận Webhook từ Telegram tại POST /webhook.
- Phản hồi HTTP 200 ngay lập tức (< 5ms) và xử lý AI ngầm.
- Hoàn toàn miễn phí trên Cloud Run Free Tier (2 triệu lượt gọi/tháng).
"""

import os
import sys
import json
import threading
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, Request, Response
import uvicorn

# Định vị thư mục
CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent.parent
ADDIN_DIR = REPO_ROOT / "addin"

if str(ADDIN_DIR) not in sys.path:
    sys.path.insert(0, str(ADDIN_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from qshien.desktop_assistant.telegram_bot import SuSuTelegramBot, load_telegram_config
except ImportError:
    # Trường hợp chạy độc lập trong Docker container
    from telegram_bot import SuSuTelegramBot, load_telegram_config

app = FastAPI(title="Su Su Telegram Bot - Google Cloud Run", version="1.0.0")

# Khởi tạo Bot instance
bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
cfg = load_telegram_config()
if bot_token:
    cfg["bot_token"] = bot_token
bot = SuSuTelegramBot(cfg)


@app.on_event("startup")
def on_startup():
    """Tự động đăng ký danh mục lệnh Menu với Telegram API khi khởi động."""
    try:
        commands = [
            {"command": "start", "description": "🌸 Khởi động & Menu chính"},
            {"command": "thammuu", "description": "📊 Bản tin Tham mưu GĐDA"},
            {"command": "duan", "description": "🏢 Hồ sơ dự án Vietstar (344 Tỷ)"},
            {"command": "14bai", "description": "🌟 14 bài học hôm nay (Lật thẻ)"},
            {"command": "tuvi", "description": "📈 Lịch vạn niên & Nhịp Tử Vi"},
            {"command": "tasks", "description": "📋 Danh sách G-Tasks VST"},
            {"command": "tk", "description": "🔍 Tra cứu 5.449 tình huống"},
            {"command": "claim", "description": "📄 Ghi nhanh Claim & EOT"},
            {"command": "risk", "description": "🚨 Ghi nhanh rủi ro hiện trường"},
            {"command": "help", "description": "❓ Hướng dẫn sử dụng"}
        ]
        import requests
        url = f"{bot.client.api_url}/setMyCommands"
        requests.post(url, json={"commands": commands}, timeout=5)
        print("[Startup] setMyCommands updated successfully.")
    except Exception as e:
        print(f"[Startup setMyCommands Error] {e}")

    # Khởi động luồng chạy ngầm quét IMAP 24/7 trên Cloud (không phụ thuộc máy tính)
    def _cloud_imap_sync_worker():
        import time
        print("[Cloud IMAP Worker] Khởi động tiến trình ngầm giám sát hòm thư Novacons 24/7...", flush=True)
        time.sleep(10)
        while True:
            try:
                mail_pass = os.environ.get("NOVACONS_MAIL_PASSWORD", "") or os.environ.get("IMAP_PASSWORD", "")
                if mail_pass:
                    try:
                        from qshien.desktop_assistant.outlook_sync_engine import get_outlook_engine
                    except ImportError:
                        from outlook_sync_engine import get_outlook_engine

                    engine = get_outlook_engine()
                    res = engine.sync_imap_data(password=mail_pass, limit=20)
                    if res.get("success") and res.get("new_emails", 0) > 0:
                        print(f"[Cloud IMAP] 📬 Phát hiện {res['new_emails']} email mới! Gửi cảnh báo Telegram...", flush=True)
                        engine.check_and_notify_telegram(new_emails=res.get("new_records", []))
            except Exception as e:
                print(f"[Cloud IMAP Worker Error] {e}", flush=True)

            # Quét định kỳ mỗi 15 phút (900 giây)
            time.sleep(900)

    t = threading.Thread(target=_cloud_imap_sync_worker, daemon=True)
    t.start()


@app.get("/")
@app.get("/health")
def health_check():
    """Kiểm tra tình trạng hoạt động của bot."""
    return {
        "status": "healthy",
        "service": "Su Su QS Assistant - Google Cloud Run",
        "bot_username": "@Hienqs_susu_bot",
        "ecosystem": "Google Cloud",
        "ai_engine": "Google Gemini Ultra + Vector RAG 5,449 cases"
    }


def _safe_process_update(update_data: Dict[str, Any]):
    try:
        msg = update_data.get("message", {})
        txt = msg.get("text", "")
        sender = msg.get("from", {}).get("username") or msg.get("from", {}).get("id")
        print(f"[Webhook Process] From: {sender} | Text: {txt}", flush=True)
        bot.process_update(update_data)
        print(f"[Webhook Success] Handled message: {txt}", flush=True)
    except Exception as e:
        import traceback
        print(f"[Webhook Process Error] {e}", flush=True)
        traceback.print_exc()


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Tiếp nhận sự kiện tin nhắn từ Telegram Webhook.
    Xử lý bất đồng bộ để tránh bị Telegram timeout (yêu cầu < 3s).
    """
    try:
        update_data = await request.json()
        if update_data:
            threading.Thread(target=_safe_process_update, args=(update_data,), daemon=True).start()
    except Exception as e:
        print(f"[Webhook Error] {e}", flush=True)

    return {"ok": True}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

