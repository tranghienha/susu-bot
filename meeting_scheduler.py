# -*- coding: utf-8 -*-
"""
meeting_scheduler.py - Động cơ Tự Động Nhận Diện Lịch Họp & Lưu Vào Google Tasks Cho Su Su
========================================================================================
Nhiệm vụ:
1. Tự động nhận diện tin nhắn/email thông báo mời họp từ các nhóm Zalo hoặc hộp thư Outlook.
2. Trích xuất thông minh: Tiêu đề cuộc họp, Thời gian diễn ra, Địa điểm & Thành phần tham gia.
3. Tự động lên lịch và lưu trực tiếp vào Sổ tay G-Tasks (user_personal_notes.json) danh mục VST.
4. Tự động ghim dấu sao (Starred) ưu tiên cao và đồng bộ sang Google Sheets / Google Tasks.
5. Tạo nội dung tóm tắt định dạng chuẩn cho thông báo Telegram kèm nút bấm xem Sổ tay Tasks.
========================================================================================
"""

from __future__ import annotations

import os
import sys
import re
import json
import time
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent.parent.parent if len(CURRENT_DIR.parents) >= 3 else CURRENT_DIR

# Danh sách từ khóa nhận diện thông báo họp trong ngành xây dựng / ban QLDA
MEETING_TRIGGER_KEYWORDS = [
    "mời họp", "moi hop", "lịch họp", "lich hop", "thông báo họp", "thong bao hop",
    "cuộc họp", "cuoc hop", "họp giao ban", "hop giao ban", "họp kỹ thuật", "hop ky thuat",
    "họp 3 bên", "hop 3 ben", "họp ba bên", "hop ba ben", "họp khẩn", "hop khan",
    "họp đột xuất", "hop dot xuat", "họp bch", "hop bch", "họp nội bộ", "hop noi bo",
    "họp với tvgs", "hop voi tvgs", "họp với cđt", "hop voi cdt",
    "họp với ban qlda", "hop voi ban qlda", "triệu tập họp", "trieu tap hop",
    "giao ban tuần", "giao ban tuan", "họp hiện trường", "hop hien truong"
]


def _find_data_file(filename: str = "user_personal_notes.json") -> Path:
    """Định vị file dữ liệu tasks trên mọi môi trường (Windows / Linux / Cloud)."""
    candidates = [
        CURRENT_DIR / "Data" / filename,
        CURRENT_DIR.parent / "Data" / filename,
        CURRENT_DIR / filename,
        Path("/app/Data") / filename,
        Path("/app") / filename,
        Path(r"C:\QS_Hien\Data") / filename,
        REPO_ROOT / "Data" / filename,
        REPO_ROOT.parent / "Data" / filename,
    ]
    for c in candidates:
        if c.exists():
            return c
    # Nếu chưa có file, ưu tiên tạo tại thư mục Data chuẩn
    for c in candidates:
        if c.parent.is_dir():
            return c
    return CURRENT_DIR / filename


def is_meeting_notice(text: str) -> bool:
    """Kiểm tra văn bản có phải là thông báo hoặc lời mời họp hay không."""
    if not text:
        return False
    t_low = text.lower()
    return any(kw in t_low for kw in MEETING_TRIGGER_KEYWORDS)


def extract_meeting_time(text: str) -> str:
    """
    Trích xuất ngày giờ tổ chức cuộc họp từ nội dung văn bản.
    Ví dụ: '14h00 chiều mai', '9h sáng thứ 2', '08h30 ngày 28/09/2026', 'hôm nay lúc 15h'.
    """
    if not text:
        return "Trong ngày (Chưa rõ giờ)"

    t_clean = text.replace("\r\n", " ").replace("\n", " ")
    t_low = t_clean.lower()

    # 1. Tìm giờ: 14h, 14h30, 14:00, 8h sáng, 15 giờ...
    hour_part = ""
    m_hour = re.search(r'\b(\d{1,2})\s*(?:h|:|\s*giờ)\s*(\d{2})?\b', t_low)
    if m_hour:
        h = int(m_hour.group(1))
        m = m_hour.group(2) or "00"
        if 0 <= h <= 24:
            hour_part = f"{h:02d}h{m}"

    # 2. Tìm buổi / ngày tương đối: chiều mai, sáng mai, tối nay, hôm nay, thứ 2...
    rel_part = ""
    rel_keywords = [
        ("sáng mai", "Sáng mai"),
        ("chiều mai", "Chiều mai"),
        ("tối mai", "Tối mai"),
        ("ngày mai", "Ngày mai"),
        ("sáng nay", "Sáng nay"),
        ("chiều nay", "Chiều nay"),
        ("tối nay", "Tối nay"),
        ("hôm nay", "Hôm nay"),
        ("thứ hai", "Thứ Hai"),
        ("thứ ba", "Thứ Ba"),
        ("thứ tư", "Thứ Tư"),
        ("thứ năm", "Thứ Năm"),
        ("thứ sáu", "Thứ Sáu"),
        ("thứ bảy", "Thứ Bảy"),
        ("chủ nhật", "Chủ Nhật"),
        ("thứ 2", "Thứ Hai"),
        ("thứ 3", "Thứ Ba"),
        ("thứ 4", "Thứ Tư"),
        ("thứ 5", "Thứ Năm"),
        ("thứ 6", "Thứ Sáu"),
        ("thứ 7", "Thứ Bảy"),
        ("cn", "Chủ Nhật")
    ]
    for kw, label in rel_keywords:
        if kw in t_low:
            rel_part = label
            break

    # 3. Tìm ngày tháng cụ thể: ngày 28/09, 28/09/2026...
    date_part = ""
    m_date = re.search(r'(?:ngày\s+)?\b(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{4}))?\b', t_low)
    if m_date:
        d = int(m_date.group(1))
        mo = int(m_date.group(2))
        y = m_date.group(3) or datetime.date.today().year
        if 1 <= d <= 31 and 1 <= mo <= 12:
            date_part = f"{d:02d}/{mo:02d}" + (f"/{y}" if m_date.group(3) else "")

    # Tổng hợp chuỗi thời gian thân thiện
    components = []
    if hour_part:
        components.append(hour_part)
    if rel_part:
        components.append(rel_part)
    if date_part:
        components.append(f"({date_part})")

    if components:
        return " ".join(components)

    # Fallback nếu không bóc tách được rõ
    return "Sắp diễn ra (Xem chi tiết nội dung)"


def extract_location(text: str) -> str:
    """Trích xuất địa điểm cuộc họp nếu có trong văn bản."""
    m_loc = re.search(r'(?:tại|ở|phòng họp)\s+([^,.\n;\(\)]+)', text, re.IGNORECASE)
    if m_loc:
        loc = m_loc.group(1).strip()
        if 3 <= len(loc) <= 50:
            return loc
    return "Văn phòng BCH Công trường Vietstar"


def extract_meeting_title(text: str, source_type: str = "Zalo") -> str:
    """Rút trích tiêu đề ngắn gọn cho cuộc họp để lưu vào Google Tasks."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # Ưu tiên tìm dòng chứa từ khóa cuộc họp
    target_line = ""
    for l in lines:
        l_low = l.lower()
        if any(k in l_low for k in ["họp", "giao ban", "meeting", "mời họp"]):
            target_line = l
            break

    if not target_line and lines:
        target_line = lines[0]

    # Làm sạch tiêu đề
    clean_title = re.sub(r'^[-\*\•\d\.\s\:]+', '', target_line).strip()
    if len(clean_title) > 60:
        clean_title = clean_title[:57] + "..."

    if not clean_title or len(clean_title) < 5:
        clean_title = "Cuộc họp điều phối công trường"

    return f"[{source_type.upper()}] {clean_title}"


def auto_save_meeting_to_tasks(
    text: str,
    group_name: str = "Nhóm điều hành dự án",
    sender_name: str = "Thành viên dự án",
    source_type: str = "Zalo",
    due_date_override: str = ""
) -> Optional[Dict[str, Any]]:
    """
    Tự động xử lý, lên lịch và lưu cuộc họp vào file Sổ tay Google Tasks (user_personal_notes.json).
    Trả về dict task đã lưu thành công, hoặc None nếu không phải thông báo họp.
    """
    if not is_meeting_notice(text):
        return None

    meeting_time = due_date_override or extract_meeting_time(text)
    meeting_loc = extract_location(text)
    meeting_title = extract_meeting_title(text, source_type=source_type)
    now_dt = datetime.datetime.now()
    now_str = now_dt.strftime("%d/%m/%Y %H:%M")

    # Nội dung rút gọn không quá dài
    snippet = " ".join(text.split())
    if len(snippet) > 250:
        snippet = snippet[:247] + "..."

    details = (
        f"🏢 Nguồn: {group_name} ({source_type})\n"
        f"👤 Người thông báo: {sender_name}\n"
        f"📍 Địa điểm: {meeting_loc}\n"
        f"🕒 Lịch hẹn: {meeting_time}\n"
        f"📝 Nội dung thông báo: \"{snippet}\"\n"
        f"🤖 Tự động lên lịch bởi Trợ lý Su Su lúc: {now_str}"
    )

    new_task = {
        "id": f"tsk_mtg_{int(time.time())}_{now_dt.microsecond // 1000}",
        "list": "VST",
        "title": meeting_title,
        "details": details,
        "due_date": meeting_time,
        "location": meeting_loc,
        "source": source_type,
        "group": group_name,
        "starred": True,
        "completed": False,
        "created_at": now_str,
        "completed_at": ""
    }

    # Lưu vào file JSON
    notes_path = _find_data_file("user_personal_notes.json")
    notes_data = {"lists": ["VST", "Việc cần làm của tôi"], "current_list": "VST", "tasks": []}

    try:
        if notes_path.exists():
            with open(notes_path, "r", encoding="utf-8") as f:
                notes_data = json.load(f)

        existing_tasks = notes_data.setdefault("tasks", [])

        # Kiểm tra trùng lặp trong 10 task gần nhất
        for ex in existing_tasks[:10]:
            if ex.get("title") == meeting_title and ex.get("due_date") == meeting_time:
                # Đã có task này trong hệ thống
                return ex

        # Chèn lên đầu danh sách việc cần làm
        existing_tasks.insert(0, new_task)

        # Lưu lại file
        notes_path.parent.mkdir(parents=True, exist_ok=True)
        with open(notes_path, "w", encoding="utf-8") as f:
            json.dump(notes_data, f, ensure_ascii=False, indent=2)

        print(f"[MeetingScheduler] ✅ Đã tự động tạo Google Task: '{meeting_title}' | Hạn: {meeting_time}")

        # Đồng bộ thêm sang file local C:\QS_Hien\Data nếu đang trên máy Windows
        if sys.platform == "win32":
            local_win_path = Path(r"C:\QS_Hien\Data\user_personal_notes.json")
            if local_win_path != notes_path and local_win_path.parent.exists():
                try:
                    with open(local_win_path, "w", encoding="utf-8") as f_win:
                        json.dump(notes_data, f_win, ensure_ascii=False, indent=2)
                except Exception:
                    pass

        return new_task

    except Exception as e:
        print(f"[MeetingScheduler Error] Không thể lưu task: {e}")
        return None


def format_meeting_telegram_banner(task_item: Dict[str, Any]) -> str:
    """Tạo đoạn văn bản thông báo Telegram khi đã tự động lên lịch cuộc họp."""
    if not task_item:
        return ""

    lines = [
        "📅 *ĐÃ TỰ ĐỘNG LÊN LỊCH & LƯU VÀO GOOGLE TASKS!*",
        f"• 📌 *Lịch họp:* *{task_item.get('title', 'Cuộc họp công trường')}*",
        f"• 🕒 *Thời gian:* `{task_item.get('due_date', 'Chưa rõ')}`",
        f"• 📍 *Địa điểm:* `{task_item.get('location', 'VP Ban QLDA')}`",
        f"• 🏢 *Nguồn:* `{task_item.get('group', 'Nhóm Zalo')}`",
        f"• ⭐ *Độ ưu tiên:* `Ghim Dấu Sao Quan Trọng (Danh mục VST)`"
    ]
    return "\n".join(lines)
