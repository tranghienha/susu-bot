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


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Tiếp nhận sự kiện tin nhắn từ Telegram Webhook.
    Xử lý bất đồng bộ để tránh bị Telegram timeout (yêu cầu < 3s).
    """
    try:
        update_data = await request.json()
        if update_data:
            # Xử lý trong luồng riêng để phản hồi ngay HTTP 200 cho Telegram
            threading.Thread(target=bot.process_update, args=(update_data,), daemon=True).start()
    except Exception as e:
        print(f"[Webhook Error] {e}")

    return {"ok": True}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
