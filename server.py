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

from fastapi import FastAPI, Request, Response, BackgroundTasks
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

        # Tự động đồng bộ và bảo đảm Webhook nhận đủ cả callback_query
        try:
            wh_url = f"{bot.client.api_url}/setWebhook"
            wh_payload = {
                "url": "https://qshien-susu.onrender.com/webhook",
                "allowed_updates": ["message", "edited_message", "callback_query", "channel_post", "edited_channel_post"]
            }
            requests.post(wh_url, json=wh_payload, timeout=5)
            print("[Startup] Webhook verified with callback_query.")
        except Exception as ex_wh:
            print(f"[Startup setWebhook Error] {ex_wh}")
    except Exception as e:
        print(f"[Startup setMyCommands Error] {e}")

    # Khởi động luồng chạy ngầm quét IMAP 24/7 trên Cloud (không phụ thuộc máy tính)
    def _cloud_imap_sync_worker():
        import time
        print("[Cloud IMAP Worker] Khởi động tiến trình ngầm giám sát hòm thư 24/7...", flush=True)
        time.sleep(15)
        loop_count = 0
        while True:
            loop_count += 1
            try:
                try:
                    from qshien.desktop_assistant.outlook_sync_engine import get_outlook_engine
                except ImportError:
                    from outlook_sync_engine import get_outlook_engine

                engine = get_outlook_engine()
                res = engine.sync_imap_data(limit=20)
                new_emails = res.get("new_records", []) if res.get("success") else []
                if res.get("success") and len(new_emails) > 0:
                    print(f"[Cloud IMAP] 📬 Phát hiện {len(new_emails)} email mới! Gửi cảnh báo Telegram...", flush=True)
                    engine.check_and_notify_telegram(new_emails=new_emails, admin_chat_id=8249791298)
                else:
                    print(f"[Cloud IMAP] Đã kiểm tra hộp thư, không có email mới ({res.get('total_cached', 0)} cached).", flush=True)
                    # Định kỳ mỗi 2 tiếng (8 chu kỳ 15 phút) gửi báo cáo định kỳ 1 lần để GĐDA yên tâm
                    if loop_count % 8 == 0:
                        engine.check_and_notify_telegram(notify_always=True, admin_chat_id=8249791298)
            except Exception as e:
                print(f"[Cloud IMAP Worker Error] {e}", flush=True)

            # Quét định kỳ mỗi 15 phút (900 giây)
            time.sleep(900)

    # Khởi động luồng Keep-Alive Self-Ping để chống ngủ đông (Render Free Tier Spin-Down)
    def _keep_alive_worker():
        import time
        import urllib.request
        print("[Keep-Alive Worker] Khởi động luồng giữ kết nối liên tục 24/7...", flush=True)
        time.sleep(60)
        while True:
            try:
                url = "https://qshien-susu.onrender.com/health"
                req = urllib.request.Request(url, headers={"User-Agent": "SuSu-Cloud-KeepAlive/1.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status == 200:
                        print("[Keep-Alive] Ping thành công, dịch vụ duy trì thức 24/7.", flush=True)
            except Exception as e:
                print(f"[Keep-Alive Ping Error] {e}", flush=True)

            # Ping mỗi 8 phút (480s < 900s timeout của Render Free Tier)
            time.sleep(480)

    t_imap = threading.Thread(target=_cloud_imap_sync_worker, daemon=True)
    t_imap.start()

    t_ping = threading.Thread(target=_keep_alive_worker, daemon=True)
    t_ping.start()


@app.get("/")
@app.get("/health")
def health_check():
    """Kiểm tra tình trạng hoạt động của bot."""
    return {
        "status": "healthy",
        "service": "Su Su QS Assistant - Cloud 24/7",
        "bot_username": "@Hienqs_susu_bot",
        "ecosystem": "Render Cloud + IMAP 24/7 Autonomous Daemon",
        "ai_engine": "Google Gemini Ultra + Vector RAG 5,589 chunks",
        "mailbox_monitored": "BCHVIETSTAR@novacons.com.vn"
    }


@app.get("/sync")
@app.get("/cron-trigger")
def manual_sync_trigger(background_tasks: BackgroundTasks):
    """Endpoint cho phép kích hoạt quét và đồng bộ hộp thư ngay lập tức (hỗ trợ external cron)."""
    import datetime

    def _do_sync():
        try:
            try:
                from qshien.desktop_assistant.outlook_sync_engine import get_outlook_engine
            except ImportError:
                from outlook_sync_engine import get_outlook_engine

            engine = get_outlook_engine()
            res = engine.sync_imap_data(limit=20, download_attachments=True)
            new_recs = res.get("new_records", []) if res.get("success") else []
            if len(new_recs) > 0:
                print(f"[ManualSync] Phát hiện {len(new_recs)} email mới, gửi alert...", flush=True)
                engine.check_and_notify_telegram(new_emails=new_recs, admin_chat_id=8249791298)
            else:
                print("[ManualSync] Không có email mới, gửi heartbeat...", flush=True)
                engine.check_and_notify_telegram(notify_always=True, admin_chat_id=8249791298)
        except Exception as e:
            print(f"[ManualSync Error] {e}", flush=True)

    background_tasks.add_task(_do_sync)
    return {
        "status": "triggered",
        "message": "Đã tiếp nhận yêu cầu đồng bộ hộp thư trong nền và gửi báo cáo Telegram.",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


@app.post("/api/telegram-proxy")
async def telegram_proxy(request: Request):
    """Proxy gửi tin nhắn Telegram an toàn từ Chrome extension (tránh bị chặn ISP)."""
    try:
        data = await request.json()
        token = data.get("bot_token") or bot.client.token
        chat_id = data.get("chat_id", 8249791298)
        text = data.get("text", "")
        parse_mode = data.get("parse_mode", "Markdown")
        markup = data.get("reply_markup")

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if markup:
            payload["reply_markup"] = markup

        import requests
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code != 200:
            payload.pop("parse_mode", None)
            r = requests.post(url, json=payload, timeout=15)
        return {"ok": r.status_code == 200, "result": r.json() if r.status_code == 200 else r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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

