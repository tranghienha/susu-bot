# -*- coding: utf-8 -*-
"""
daily_digest_engine.py - Báo Cáo Tiêu Điểm Công Trường Cuối Ngày (Daily Construction Digest 17h30)
================================================================================================
Chức năng:
1. Tự động tổng hợp toàn bộ sự vụ trong ngày vào lúc 17h30 hàng ngày cho Giám đốc Dự án:
   - Thống kê Hòm thư Dự án BCH Vietstar (Email mới, RFI, Đệ trình vật tư, Thông báo đối tác).
   - Thống kê Tiến độ Xử lý Việc & Lịch họp (Google Tasks VST, các việc đã xong, việc tồn đọng).
   - Dự báo & Tử vi Phong thủy Ngày mai (Can chi, giờ hoàng đạo đổ bê tông/khởi công, việc nên làm).
   - 3 Chỉ đạo Chiến lược cho buổi giao ban sáng hôm sau.
2. Cung cấp Thẻ Tương Tác 1 Chạm (Inline Action Buttons):
   - [📋 Chi tiết Tasks VST] [📩 Quét Thư Ngay] [🔮 Xem Tử Vi Mai] [🌟 Lật Thẻ Bài Học]
3. Hỗ trợ kích hoạt tự động theo scheduler hoặc gọi thủ công qua lệnh /digest, /baocao.
"""

from __future__ import annotations

import os
import sys
import json
import time
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import requests

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent.parent

if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

# Import các engine bổ trợ
try:
    from outlook_sync_engine import get_outlook_engine
except ImportError:
    get_outlook_engine = None

try:
    from meeting_scheduler import _find_data_file
except ImportError:
    def _find_data_file(fn="user_personal_notes.json"):
        candidates = [
            CURRENT_DIR / "Data" / fn,
            CURRENT_DIR / fn,
            Path(r"C:\QS_Hien\Data") / fn
        ]
        for c in candidates:
            if c.exists(): return c
        return CURRENT_DIR / fn

try:
    from tuvi_holidays import get_tuvi_day_info
except ImportError:
    try:
        from qshien.desktop_assistant.tuvi_holidays import get_tuvi_day_info
    except ImportError:
        get_tuvi_day_info = None


def generate_daily_digest(target_date: Optional[datetime.date] = None) -> Dict[str, Any]:
    """Tổng hợp dữ liệu toàn diện cho Báo cáo Tiêu điểm 17h30."""
    now = datetime.datetime.now()
    if target_date is None:
        target_date = now.date()

    date_str = target_date.strftime("%d/%m/%Y")
    tomorrow = target_date + datetime.timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%d/%m/%Y")

    # 1. Thống kê Hòm thư Outlook BCH Vietstar
    mail_stats = {
        "total_today": 0,
        "rfis": [],
        "submittals": [],
        "meetings": [],
        "important_senders": set(),
        "recent_subjects": []
    }

    if get_outlook_engine:
        try:
            eng = get_outlook_engine()
            cached_emails = eng.load_cached_emails()
            for em in cached_emails:
                dt_str = em.get("date", "")
                subj = em.get("subject", "")
                sender = em.get("sender", "")

                # Kiểm tra xem email có thuộc ngày target_date không
                is_today = False
                if dt_str:
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
                        try:
                            ed = datetime.datetime.strptime(dt_str.split()[0], fmt).date()
                            if ed == target_date:
                                is_today = True
                                break
                        except Exception:
                            pass

                # Nếu là hôm nay hoặc trong 10 email mới nhất nếu chưa có email đúng ngày
                if is_today:
                    mail_stats["total_today"] += 1
                    s_lower = subj.lower()
                    if "rfi" in s_lower:
                        mail_stats["rfis"].append(subj)
                    elif any(k in s_lower for k in ("mas", "submittal", "đệ trình", "mẫu vật tư", "nghiệm thu")):
                        mail_stats["submittals"].append(subj)
                    elif any(k in s_lower for k in ("họp", "moi hop", "lịch họp", "meeting")):
                        mail_stats["meetings"].append(subj)

                    if sender:
                        mail_stats["important_senders"].add(sender.split("<")[0].strip())

                if len(mail_stats["recent_subjects"]) < 5 and subj:
                    mail_stats["recent_subjects"].append(subj)

        except Exception as ex_mail:
            print(f"[Digest Mail Error] {ex_mail}")

    # 2. Thống kê Sổ việc Google Tasks (VST)
    task_stats = {
        "total_active": 0,
        "completed_today": 0,
        "high_priority": [],
        "upcoming_meetings": []
    }

    try:
        tasks_file = _find_data_file("user_personal_notes.json")
        if tasks_file.exists():
            with open(tasks_file, "r", encoding="utf-8") as f:
                tdata = json.load(f)
                tasks_list = tdata.get("tasks", []) if isinstance(tdata, dict) else tdata
                if isinstance(tasks_list, list):
                    for t in tasks_list:
                        status = str(t.get("status", "")).lower()
                        title = t.get("title", "")
                        created = t.get("created_at") or t.get("date", "")

                        if status in ("done", "completed", "đã xong"):
                            if date_str in str(created):
                                task_stats["completed_today"] += 1
                        else:
                            task_stats["total_active"] += 1
                            if t.get("starred") or any(k in title.lower() for k in ("khẩn", "gấp", "quan trọng", "cđt", "tvgs")):
                                task_stats["high_priority"].append(title)
                            if any(k in title.lower() for k in ("họp", "meeting", "giao ban")):
                                task_stats["upcoming_meetings"].append(title)
    except Exception as ex_task:
        print(f"[Digest Task Error] {ex_task}")

    # 3. Tử vi & Phong thủy Ngày mai
    tuvi_tomorrow = {}
    if get_tuvi_day_info:
        try:
            tuvi_tomorrow = get_tuvi_day_info(offset_days=1)
        except Exception as ex_tv:
            print(f"[Digest Tuvi Error] {ex_tv}")

    digest_data = {
        "date_str": date_str,
        "tomorrow_str": tomorrow_str,
        "generated_at": now.strftime("%H:%M %d/%m/%Y"),
        "mail_stats": mail_stats,
        "task_stats": task_stats,
        "tuvi_tomorrow": tuvi_tomorrow
    }

    digest_data["formatted_markdown"] = format_daily_digest_telegram(digest_data)
    digest_data["inline_keyboard"] = build_daily_digest_keyboard()
    return digest_data


def format_daily_digest_telegram(d: Dict[str, Any]) -> str:
    """Định dạng bản tin Daily Digest phong cách Giám đốc Điều hành Dự án."""
    date_str = d.get("date_str")
    tomorrow_str = d.get("tomorrow_str")
    gen_time = d.get("generated_at")
    m = d.get("mail_stats", {})
    t = d.get("task_stats", {})
    tv = d.get("tuvi_tomorrow", {})

    lines = [
        "🏢 *BÁO CÁO TIÊU ĐIỂM CÔNG TRƯỜNG CUỐI NGÀY (DAILY DIGEST)*",
        f"📅 *Dự án Vietstar (344 Tỷ)* — Ngày {date_str}",
        f"⏱️ _Thời điểm chốt số liệu: {gen_time}_\n",
        "━━━━━━━━━━━━━━━━━━━━━━━━━"
    ]

    # KHỐI 1: THƯ TỪ & PHÁP LÝ HỢP ĐỒNG (OUTLOOK)
    lines.append("📬 *1. HÒM THƯ DỰ ÁN & VĂN BẢN ĐẾN:*")
    total_mail = m.get("total_today", 0)
    rfis = m.get("rfis", [])
    submittals = m.get("submittals", [])
    meetings = m.get("meetings", [])

    if total_mail > 0:
        lines.append(f"• Tổng số email nhận hôm nay: *{total_mail} thư*")
    else:
        lines.append("• Hòm thư hôm nay không phát sinh văn bản khẩn mới.")

    if rfis:
        lines.append(f"• 🚨 *RFI yêu cầu làm rõ ({len(rfis)}):*")
        for r in rfis[:3]:
            lines.append(f"  - _{r[:65]}..._" if len(r) > 65 else f"  - _{r}_")
    else:
        lines.append("• 📑 *RFI:* Không có RFI mới phát sinh đang treo.")

    if submittals:
        lines.append(f"• 📦 *Đệ trình vật tư/nghiệm thu:* {len(submittals)} hồ sơ đang luân chuyển.")
    if meetings:
        lines.append(f"• 🤝 *Thư mời họp mới:* {len(meetings)} thông báo.")

    lines.append("")

    # KHỐI 2: ĐIỀU PHỐI CÔNG VIỆC & SỰ VỤ (GOOGLE TASKS VST)
    lines.append("📋 *2. ĐIỀU PHỐI CÔNG VIỆC & TIẾN ĐỘ SỰ VỤ (VST):*")
    active_cnt = t.get("total_active", 0)
    done_cnt = t.get("completed_today", 0)
    high_pri = t.get("high_priority", [])
    upcoming_m = t.get("upcoming_meetings", [])

    lines.append(f"• Việc hoàn thành hôm nay: *{done_cnt} việc* ✅")
    lines.append(f"• Đầu việc còn đang mở: *{active_cnt} việc* ⏳")

    if high_pri:
        lines.append("• ⚠️ *Việc trọng tâm cần giám sát:*")
        for hp in high_pri[:3]:
            lines.append(f"  - *{hp}*")

    if upcoming_m:
        lines.append("• 📅 *Lịch họp ghi nhận:*")
        for um in upcoming_m[:2]:
            lines.append(f"  - _{um}_")

    lines.append("")

    # KHỐI 3: DỰ BÁO TỬ VI & PHONG THỦY NGÀY MAI
    lines.append(f"🔮 *3. DỰ BÁO NGÀY MAI ({tomorrow_str}):*")
    if tv:
        can_chi = tv.get("can_chi") or tv.get("ngay_am") or "Ngày tốt lành"
        hoang_dao = tv.get("gio_hoang_dao") or "Tý, Dần, Mão, Ngọ, Mùi, Dậu"
        loi_khuyen = tv.get("loi_khuyen") or tv.get("viec_nen_lam") or "Thích hợp ký tá hợp đồng, kiểm tra hiện trường, giao việc quyết liệt."
        lines.append(f"• *Lịch tiết:* {can_chi}")
        lines.append(f"• *Giờ hoàng đạo thuận lợi:* `{hoang_dao}`")
        lines.append(f"• *Định hướng:* _{loi_khuyen}_")
    else:
        lines.append("• Khuyến nghị: Giữ vững tinh thần quyết liệt, ưu tiên an toàn và tiến độ.")

    lines.append("")

    # KHỐI 4: 3 TIÊU ĐIỂM CHỈ ĐẠO CHO GĐDA SÁNG MAI
    lines.append("🎯 *4. BA TIÊU ĐIỂM CHỈ ĐẠO ĐẦU GIỜ SÁNG MAI:*")
    lines.append("1. **Kiểm tra tiến độ RFI & Đệ trình:** Đôn đốc TVGS duyệt dứt điểm mẫu vật tư để không chậm đường găng.")
    lines.append("2. **Hiện trường & An toàn (HSE):** Rà soát biện pháp giàn giáo và cốp pha trước khi cấp phép đổ bê tông.")
    lines.append("3. **Hồ sơ Pháp lý & Thanh toán:** Bám sát hồ sơ IPC đợt tới, giữ nhịp dòng tiền dự án.")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 _Bấm các nút dưới đây để tra cứu nhanh hoặc điều hành 1 chạm:_")

    return "\n".join(lines)


def build_daily_digest_keyboard() -> Dict[str, Any]:
    """Tạo bàn phím Inline Buttons tương tác cho bản tin Daily Digest."""
    return {
        "inline_keyboard": [
            [
                {"text": "📋 Xem Sổ Việc G-Tasks", "callback_data": "tasks_list"},
                {"text": "📩 Quét Thư Mới Ngay", "callback_data": "outlook_sync"}
            ],
            [
                {"text": "🏢 Hồ Sơ Vietstar 344 Tỷ", "callback_data": "duan"},
                {"text": "🔮 Tử Vi & Giờ Đẹp Mai", "callback_data": "tuvi_1"}
            ],
            [
                {"text": "🌟 14 Bài Học Hôm Nay", "callback_data": "14bai"},
                {"text": "🌸 Menu Chính Su Su", "callback_data": "main_menu"}
            ]
        ]
    }


def send_daily_digest_to_admin(bot_token: str, admin_chat_id: int = 8249791298) -> bool:
    """Gửi bản tin Daily Digest trực tiếp đến Telegram Admin."""
    try:
        digest = generate_daily_digest()
        text = digest.get("formatted_markdown", "")
        markup = digest.get("inline_keyboard")

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": admin_chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": markup
        }
        res = requests.post(url, json=payload, timeout=20)
        if res.status_code != 200:
            payload.pop("parse_mode", None)
            res = requests.post(url, json=payload, timeout=20)
        return res.status_code == 200
    except Exception as e:
        print(f"[Send Daily Digest Error] {e}")
        return False
