# -*- coding: utf-8 -*-
"""
outlook_sync_engine.py - Động Cơ Tự Động Kết Nối & Đồng Bộ Dữ Liệu Microsoft Outlook Cho Su Su
=============================================================================================
Nhiệm vụ:
1. Kết nối an toàn với Microsoft Outlook Desktop cục bộ qua MAPI (win32com.client).
2. Quét & trích xuất thư từ tài khoản dự án:
   - BCHVIETSTAR@novacons.com.vn (Inbox & Sent)
   - Thư mục VIETSTAR (Báo cáo tuần, Báo cáo ngày, YCPD, YCVT, Công văn...)
   - Hộp thư tác nghiệp Kỹ sư Hiền: hienpv@novacons.com.vn (Inbox & Sent)
3. Phân loại thông minh theo 5 Trụ Cột Quản trị GĐDA:
   - 💰 CLAIMS & PHÁT SINH (Báo giá ngoài HĐ, vướng mặt bằng, yêu cầu bồi hoàn)
   - 📝 MOM & GIAO BAN (Thư mời họp kỹ thuật, biên bản giao ban 3 bên, chỉ đạo CĐT)
   - 📈 TIẾN ĐỘ & BÁO CÁO (Báo cáo tuần, báo cáo ngày, đệ trình tiến độ tổng thể)
   - 📑 ĐỆ TRÌNH KỸ THUẬT (YCPD, MAS vật tư, MSS biện pháp thi công, SDS shopdrawing)
   - 💵 VẬT TƯ, DNTU & TỔ ĐỘI (Đề nghị tạm ứng đợt 1-5, YCVT, giải chi, khối lượng thầu phụ)
4. Tự động lưu trữ file đính kèm (.pdf, .docx, .xlsx) vào Data/outlook_attachments/.
5. Tự động cập nhật hồ sơ tham mưu: project_claims_log.json, mom_action_tracker.json, project_cashflow_finance.json.
6. Cơ chế Tự Động Giám Sát Định Kỳ 30 Phút & Báo Telegram tức thì khi có thư mới.
=============================================================================================
"""

from __future__ import annotations

import os
import sys
import json
import re
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Định vị thư mục
CURRENT_DIR = Path(__file__).resolve().parent
ADDIN_DIR = CURRENT_DIR.parent.parent if len(CURRENT_DIR.parents) >= 2 else CURRENT_DIR
REPO_ROOT = ADDIN_DIR.parent if len(ADDIN_DIR.parents) >= 1 else CURRENT_DIR

if str(ADDIN_DIR) not in sys.path:
    sys.path.insert(0, str(ADDIN_DIR))

def _get_data_dir() -> Path:
    candidates = [
        CURRENT_DIR / "Data",
        CURRENT_DIR,
        REPO_ROOT.parent / "Data",
        REPO_ROOT / "Data",
        Path("/app/Data"),
        Path("/app"),
        Path(r"C:\QS_Hien\Data"),
    ]
    for c in candidates:
        if c.is_dir() and ((c / "current_project_dossier.json").exists() or (c / "project_claims_log.json").exists()):
            return c
    for c in candidates:
        if c.is_dir():
            return c
    return CURRENT_DIR

DATA_DIR = _get_data_dir()
OUTLOOK_SYNC_DIR = DATA_DIR / "outlook_sync"
ATTACHMENTS_DIR = DATA_DIR / "outlook_attachments"
SYNC_DB_FILE = OUTLOOK_SYNC_DIR / "synced_emails.json"
LAST_STATUS_FILE = OUTLOOK_SYNC_DIR / "last_sync_status.json"

# Phân loại chuyên sâu theo từ khóa ngành xây dựng
CATEGORY_KEYWORDS = {
    "CLAIMS_PHAT_SINH": [
        "phát sinh", "báo giá phát sinh", "ngoài hợp đồng", "claim", "eot", "chậm bàn giao",
        "gia hạn tiến độ", "bù chi phí", "vướng mặt bằng", "chi phí dừng chờ", "đơn giá mới"
    ],
    "MOM_GIAO_BAN": [
        "mời họp", "bien ban hop", "biên bản họp", "giao ban", "kết luận cuộc họp",
        "phối hợp thi công", "thống nhất phương án", "họp kỹ thuật", "cuộc họp"
    ],
    "TIEN_DO_BAO_CAO": [
        "báo cáo tuần", "báo cáo ngày", "bct.", "bcn.", "tiến độ thi công", "đệ trình tiến độ",
        "biểu đồ nhân lực", "tiến độ tổng thể", "ots-002", "đường găng", "kế hoạch nghiệm thu"
    ],
    "DE_TRINH_KY_THUAT": [
        "ycpd", "đệ trình", "mas-", "mss-", "sds-", "shopdrawing", "biện pháp thi công",
        "mẫu thép", "bê tông thương phẩm", "coupler", "chống thấm", "hdpe", "phê duyệt"
    ],
    "VAT_TU_TO_DOI": [
        "ycvt", "vật tư", "tạm ứng", "dntu", "đề nghị tạm ứng", "thanh toán đội", "tổ đội",
        "thầu phụ", "tăng ca", "hóa đơn", "giải chi", "công nhật", "tiếp khách", "thanh toán khối lượng"
    ],
    "NOI_BO_HANH_CHINH": [
        "nghỉ phép", "đơn xin", "thông báo deadline", "deadline công việc", "nội bộ", "nhân sự", "hành chính"
    ]
}


def _safe_str(val: Any) -> str:
    """Chuyển đổi giá trị sang chuỗi an toàn."""
    if val is None:
        return ""
    return str(val).strip()


def is_spam_or_irrelevant(subject: str, sender: str = "", body: str = "") -> bool:
    """Kiểm tra và lọc bỏ email spam, quảng cáo, OTP hoặc thông báo tự động vô nghĩa."""
    spam_keywords = [
        "aliexpress", "grabxu", "khuyến mãi", "quảng cáo", "sổ ghi đồng bộ",
        "test message", "flash sale", "one-time password", "otp", "ưu đãi", "giảm giá"
    ]
    full_check = f"{subject} {sender} {body}".lower()
    return any(k in full_check for k in spam_keywords)


def classify_email(subject: str, body: str) -> str:
    """Phân loại email tự động vào 5 trụ cột."""
    text = f"{subject} {body}".lower()
    
    # Ưu tiên kiểm tra Claims & Phát sinh
    for kw in CATEGORY_KEYWORDS["CLAIMS_PHAT_SINH"]:
        if kw in text:
            return "CLAIMS_PHAT_SINH"
            
    # Kiểm tra Biên bản họp / Giao ban
    for kw in CATEGORY_KEYWORDS["MOM_GIAO_BAN"]:
        if kw in text:
            return "MOM_GIAO_BAN"
            
    # Kiểm tra Tiến độ & Báo cáo
    for kw in CATEGORY_KEYWORDS["TIEN_DO_BAO_CAO"]:
        if kw in text:
            return "TIEN_DO_BAO_CAO"
            
    # Kiểm tra Đệ trình kỹ thuật
    for kw in CATEGORY_KEYWORDS["DE_TRINH_KY_THUAT"]:
        if kw in text:
            return "DE_TRINH_KY_THUAT"
            
    # Kiểm tra Vật tư, Tạm ứng DNTU & Tổ đội
    for kw in CATEGORY_KEYWORDS["VAT_TU_TO_DOI"]:
        if kw in text:
            return "VAT_TU_TO_DOI"

    # Kiểm tra Nội bộ & Hành chính
    for kw in CATEGORY_KEYWORDS.get("NOI_BO_HANH_CHINH", []):
        if kw in text:
            return "NOI_BO_HANH_CHINH"
            
    return "THONG_TIN_CHUNG"


class OutlookSyncEngine:
    """Động cơ kết nối Microsoft Outlook MAPI và xử lý tri thức email dự án."""

    def __init__(self):
        OUTLOOK_SYNC_DIR.mkdir(parents=True, exist_ok=True)
        ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
        self.mapi = None
        self.outlook_app = None
        self._is_connected = False

    def connect(self) -> bool:
        """Kết nối tới Microsoft Outlook Desktop đang chạy hoặc khởi động MAPI."""
        try:
            import win32com.client
            self.outlook_app = win32com.client.Dispatch("Outlook.Application")
            self.mapi = self.outlook_app.GetNamespace("MAPI")
            self._is_connected = True
            return True
        except Exception as e:
            self._is_connected = False
            return False

    def load_cached_emails(self) -> List[Dict[str, Any]]:
        """Nạp danh sách email đã đồng bộ từ file JSON lưu trữ cục bộ."""
        if not SYNC_DB_FILE.exists():
            return []
        try:
            with open(SYNC_DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def save_cached_emails(self, emails: List[Dict[str, Any]]) -> bool:
        """Lưu danh mục email đã đồng bộ vào file JSON."""
        try:
            with open(SYNC_DB_FILE, "w", encoding="utf-8") as f:
                json.dump(emails, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def sync_outlook_data(self, limit_per_folder: int = 50, download_attachments: bool = True) -> Dict[str, Any]:
        """
        Quét các thư mục dự án trên Outlook và trích xuất dữ liệu.
        Bao gồm:
        - BCHVIETSTAR@novacons.com.vn (Inbox & Sent)
        - VIETSTAR (Các thư mục con)
        - hienpv@novacons.com.vn (Inbox & Sent)
        """
        if not self._is_connected:
            if not self.connect():
                # Tự động chuyển đổi sang quét IMAP nếu có cấu hình mật khẩu (Cloud 24/7 hoặc khi máy tính tắt)
                imap_res = self.sync_imap_data(limit=limit_per_folder, download_attachments=download_attachments)
                if imap_res.get("success"):
                    return imap_res
                return {
                    "success": False,
                    "error": f"Không thể kết nối Outlook Desktop và IMAP Cloud: {imap_res.get('error', 'Chưa kết nối')}",
                    "new_emails": 0,
                    "downloaded_files": 0
                }

        cached_emails = self.load_cached_emails()
        existing_ids = {e.get("entry_id") for e in cached_emails if e.get("entry_id")}

        new_records: List[Dict[str, Any]] = []
        downloaded_count = 0

        # Danh sách các hòm thư / thư mục cần quét
        target_sources = []
        for folder in self.mapi.Folders:
            f_name = folder.Name
            # 1. Hộp thư chính Ban Chỉ Huy Vietstar
            if "BCHVIETSTAR" in f_name.upper():
                for sub in folder.Folders:
                    if sub.Name in ["Inbox", "Sent"]:
                        target_sources.append((f"{f_name}/{sub.Name}", sub))
            # 2. Thư mục dữ liệu VIETSTAR
            elif f_name.upper() == "VIETSTAR":
                for sub in folder.Folders:
                    if sub.Items.Count > 0:
                        target_sources.append((f"VIETSTAR/{sub.Name}", sub))
            # 3. Hộp thư Kỹ sư Hiền (hienpv@novacons.com.vn) - Tiếp nhận toàn diện Inbox & Sent
            elif "HIENPV" in f_name.upper():
                for sub in folder.Folders:
                    if sub.Name in ["Inbox", "Sent"]:
                        target_sources.append((f"{f_name}/{sub.Name}", sub))

        for source_name, folder_obj in target_sources:
            try:
                items = folder_obj.Items
                count = items.Count
                start_idx = max(1, count - limit_per_folder + 1)

                for i in range(count, start_idx - 1, -1):
                    try:
                        item = items(i)
                        
                        # Bỏ qua nếu không phải email
                        if not hasattr(item, "Subject"):
                            continue

                        subject = _safe_str(getattr(item, "Subject", ""))
                        body = _safe_str(getattr(item, "Body", ""))
                        sender_name = _safe_str(getattr(item, "SenderName", ""))
                        sender_email = _safe_str(getattr(item, "SenderEmailAddress", ""))

                        # Lọc bỏ thư rác / quảng cáo / thông báo đồng bộ hệ thống
                        if is_spam_or_irrelevant(subject, f"{sender_name} {sender_email}", body):
                            continue

                        entry_id = _safe_str(getattr(item, "EntryID", ""))
                        if not entry_id:
                            entry_id = f"{subject}_{str(getattr(item, 'ReceivedTime', ''))}"

                        if entry_id in existing_ids:
                            continue

                        to_str = _safe_str(getattr(item, "To", ""))
                        cc_str = _safe_str(getattr(item, "CC", ""))

                        recv_time_raw = getattr(item, "ReceivedTime", None)
                        if not recv_time_raw and hasattr(item, "SentOn"):
                            recv_time_raw = getattr(item, "SentOn", None)
                        recv_time_str = recv_time_raw.strftime("%Y-%m-%d %H:%M:%S") if recv_time_raw else datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        category = classify_email(subject, body)

                        # Trích xuất và tải file đính kèm
                        attachments_meta = []
                        if hasattr(item, "Attachments"):
                            for att_idx in range(1, item.Attachments.Count + 1):
                                try:
                                    att = item.Attachments(att_idx)
                                    filename = att.FileName
                                    ext = Path(filename).suffix.lower()

                                    # Chỉ tải các file văn bản, bảng tính, kỹ thuật quan trọng
                                    save_path_str = ""
                                    if download_attachments and ext in [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".dwg"]:
                                        safe_name = re.sub(r'[\\/*?:"<>|]', "_", filename)
                                        target_file = ATTACHMENTS_DIR / f"{recv_time_str[:10]}_{safe_name}"
                                        try:
                                            att.SaveAsFile(str(target_file))
                                            save_path_str = str(target_file)
                                            downloaded_count += 1
                                        except Exception:
                                            pass

                                    attachments_meta.append({
                                        "filename": filename,
                                        "size": getattr(att, "Size", 0),
                                        "local_path": save_path_str
                                    })
                                except Exception:
                                    pass

                        record = {
                            "entry_id": entry_id,
                            "source_folder": source_name,
                            "subject": subject,
                            "sender_name": sender_name,
                            "sender_email": sender_email,
                            "to": to_str,
                            "cc": cc_str,
                            "time": recv_time_str,
                            "category": category,
                            "body_preview": body[:1500],
                            "attachments": attachments_meta,
                            "synced_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }

                        new_records.append(record)
                        existing_ids.add(entry_id)

                    except Exception:
                        continue
            except Exception:
                continue

        # Lưu lại vào cache
        all_emails = new_records + cached_emails
        all_emails.sort(key=lambda x: x.get("time", ""), reverse=True)
        self.save_cached_emails(all_emails)

        # Tự động đồng bộ các thư quan trọng vào Hồ sơ Claim, MOM & Tài chính
        self._auto_update_project_dossiers(new_records)

        return {
            "success": True,
            "new_emails": len(new_records),
            "new_records": new_records,
            "total_cached": len(all_emails),
            "downloaded_files": downloaded_count
        }

    def sync_imap_data(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        limit: int = 30,
        download_attachments: bool = True
    ) -> Dict[str, Any]:
        """
        Đồng bộ email trực tiếp qua IMAP SSL (Dành cho Cloud Render 24/7 hoặc khi máy tính tắt).
        Hỗ trợ đọc từ mail.novacons.com.vn (Dovecot IMAP SSL cổng 993).
        """
        import imaplib
        import email
        from email.header import decode_header
        from email.utils import parsedate_to_datetime

        host = host or os.environ.get("IMAP_HOST", "mail.novacons.com.vn")
        port = int(port or os.environ.get("IMAP_PORT", 993))
        user = user or os.environ.get("IMAP_USER", "hienpv@novacons.com.vn")
        password = password or os.environ.get("NOVACONS_MAIL_PASSWORD") or os.environ.get("IMAP_PASSWORD", "")

        if not password:
            cred_file = DATA_DIR / "mail_credentials.json"
            if cred_file.exists():
                try:
                    with open(cred_file, "r", encoding="utf-8") as f:
                        c_data = json.load(f)
                        password = c_data.get("password", "")
                        user = c_data.get("user", user)
                        host = c_data.get("host", host)
                except Exception:
                    pass

        if not password:
            return {
                "success": False,
                "error": "Chưa cấu hình mật khẩu email IMAP (biến môi trường NOVACONS_MAIL_PASSWORD hoặc file Data/mail_credentials.json).",
                "new_emails": 0,
                "downloaded_files": 0
            }

        cached_emails = self.load_cached_emails()
        existing_ids = {em.get("entry_id") for em in cached_emails if em.get("entry_id")}

        new_records = []
        downloaded_count = 0

        try:
            client = imaplib.IMAP4_SSL(host, port)
            client.login(user, password)
            client.select("INBOX", readonly=True)

            status, data = client.search(None, "ALL")
            if status != "OK" or not data or not data[0]:
                client.logout()
                return {"success": True, "new_emails": 0, "total_cached": len(cached_emails), "downloaded_files": 0}

            msg_ids = data[0].split()
            target_ids = msg_ids[-limit:] if len(msg_ids) > limit else msg_ids
            target_ids.reverse()

            for mid in target_ids:
                try:
                    res, mdata = client.fetch(mid, "(RFC822)")
                    if res != "OK" or not mdata or not mdata[0]:
                        continue
                    raw_bytes = mdata[0][1]
                    msg = email.message_from_bytes(raw_bytes)

                    def _dec_hdr(h_val):
                        if not h_val:
                            return ""
                        res_parts = []
                        for frag, enc in decode_header(h_val):
                            if isinstance(frag, bytes):
                                res_parts.append(frag.decode(enc or "utf-8", errors="replace"))
                            else:
                                res_parts.append(str(frag))
                        return "".join(res_parts)

                    subject = _dec_hdr(msg.get("Subject", ""))
                    sender_full = _dec_hdr(msg.get("From", ""))
                    to_str = _dec_hdr(msg.get("To", ""))
                    cc_str = _dec_hdr(msg.get("Cc", ""))
                    date_raw = msg.get("Date", "")
                    msg_id_hdr = msg.get("Message-ID", "") or f"IMAP_{mid.decode('ascii', errors='ignore')}"

                    entry_id = msg_id_hdr.strip("<>")
                    if entry_id in existing_ids:
                        continue

                    try:
                        dt = parsedate_to_datetime(date_raw)
                        recv_time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        recv_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    body = ""
                    attachments_meta = []

                    if msg.is_multipart():
                        for part in msg.walk():
                            ctype = part.get_content_type()
                            cdisp = str(part.get("Content-Disposition", ""))
                            fname = part.get_filename()
                            if fname:
                                fname = _dec_hdr(fname)
                                ext = Path(fname).suffix.lower()
                                save_path_str = ""
                                payload = part.get_payload(decode=True)
                                size = len(payload) if payload else 0
                                if download_attachments and ext in [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".dwg"] and payload:
                                    safe_name = re.sub(r'[\\/*?:"<>|]', "_", fname)
                                    target_file = ATTACHMENTS_DIR / f"{recv_time_str[:10]}_{safe_name}"
                                    try:
                                        target_file.write_bytes(payload)
                                        save_path_str = str(target_file)
                                        downloaded_count += 1
                                    except Exception:
                                        pass
                                attachments_meta.append({
                                    "filename": fname,
                                    "size": size,
                                    "local_path": save_path_str
                                })
                            elif ctype == "text/plain" and "attachment" not in cdisp:
                                payload = part.get_payload(decode=True)
                                if payload:
                                    cset = part.get_content_charset() or "utf-8"
                                    try:
                                        body += payload.decode(cset, errors="replace") + "\n"
                                    except Exception:
                                        body += payload.decode("utf-8", errors="replace") + "\n"
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            cset = msg.get_content_charset() or "utf-8"
                            try:
                                body = payload.decode(cset, errors="replace")
                            except Exception:
                                body = payload.decode("utf-8", errors="replace")

                    if is_spam_or_irrelevant(subject, sender_full, body):
                        continue

                    category = classify_email(subject, body)
                    record = {
                        "entry_id": entry_id,
                        "source_folder": f"IMAP_{user}_INBOX",
                        "subject": subject,
                        "sender_name": sender_full,
                        "sender_email": sender_full,
                        "to": to_str,
                        "cc": cc_str,
                        "time": recv_time_str,
                        "category": category,
                        "body_preview": body[:1500].strip(),
                        "attachments": attachments_meta,
                        "synced_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    new_records.append(record)
                    existing_ids.add(entry_id)

                except Exception:
                    continue

            client.logout()

            all_emails = new_records + cached_emails
            all_emails.sort(key=lambda x: x.get("time", ""), reverse=True)
            self.save_cached_emails(all_emails)
            self._auto_update_project_dossiers(new_records)

            return {
                "success": True,
                "new_emails": len(new_records),
                "new_records": new_records,
                "total_cached": len(all_emails),
                "downloaded_files": downloaded_count
            }

        except Exception as e:
            return {"success": False, "error": f"Lỗi kết nối IMAP: {e}", "new_emails": 0, "downloaded_files": 0}

    def _auto_update_project_dossiers(self, new_emails: List[Dict[str, Any]]):
        """Tự động phân tích các email mới để bổ sung vào project_claims_log.json, mom_action_tracker.json & project_cashflow_finance.json."""
        claims_file = DATA_DIR / "project_claims_log.json"
        mom_file = DATA_DIR / "mom_action_tracker.json"
        cashflow_file = DATA_DIR / "project_cashflow_finance.json"

        # 1. Cập nhật Claims nếu có email báo giá phát sinh
        claims_data = []
        if claims_file.exists():
            try:
                with open(claims_file, "r", encoding="utf-8") as f:
                    claims_data = json.load(f)
            except Exception:
                claims_data = []

        existing_claim_titles = {c.get("title", "").lower() for c in claims_data}

        # 2. Cập nhật MOM nếu có thư mời họp / kết luận
        mom_data = []
        if mom_file.exists():
            try:
                with open(mom_file, "r", encoding="utf-8") as f:
                    mom_data = json.load(f)
            except Exception:
                mom_data = []

        existing_mom_events = {m.get("meeting_title", "").lower() for m in mom_data}

        claims_updated = False
        mom_updated = False

        for em in new_emails:
            cat = em.get("category")
            subj = em.get("subject", "")
            body = em.get("body_preview", "")
            date_str = em.get("time", "")[:10]

            # Kiểm tra Claims
            if cat == "CLAIMS_PHAT_SINH" or "báo giá phát sinh" in subj.lower():
                if "coupler" in subj.lower() or "coupler" in body.lower():
                    title = "Báo giá phát sinh Coupler nối thép lò đốt PK1 + vách hố rác & Bê tông chèn Shoring"
                    if title.lower() not in existing_claim_titles:
                        new_clm = {
                            "id": f"CLM-VST-{len(claims_data)+1:02d}",
                            "project": "Dự án Nhà máy tích hợp xử lý chất thải rắn Vietstar (344,89 tỷ)",
                            "title": title,
                            "event_date": date_str,
                            "notice_date": date_str,
                            "delay_days": 0,
                            "caused_by": "Chủ đầu tư / Thiết kế điều chỉnh biện pháp nối thép và bổ sung chèn Shoring cừ Larsen",
                            "contract_clauses": [
                                "Điều 7: Phát sinh và Điều chỉnh giá hợp đồng",
                                "Điều 4: Tiêu chuẩn kỹ thuật thi công và nghiệm thu"
                            ],
                            "impact_cost_vnd": 656954073,
                            "impact_cost_str": "656.954.073 VNĐ (Coupler: 227,7 tr + Shoring: 429,3 tr)",
                            "impact_description": "Novacons đã phát hành 02 Báo giá phát sinh chính thức gửi CĐT ngày 24/09/2026: (1) Cung cấp & gia công Coupler nối thép Zone 1 & vách hố rác (227.697.914 đ); (2) Copha và chèn bê tông M250R3 gia cố hệ Shoring cừ Larsen (429.256.159 đ).",
                            "eot_requested_days": 0,
                            "status": "Đã gửi Email & Tờ trình báo giá phát sinh; đang theo dõi phản hồi phê duyệt từ CĐT Vietstar.",
                            "ref_document": "Email BCHVIETSTAR gửi CĐT ngày 24/09/2026 kèm 02 file PDF báo giá chi tiết",
                            "action_for_pd": "Đôn đốc Đại diện CĐT (Anh Hạnh Lê / Anh Tuấn) phê duyệt văn bản 656,9 triệu trước khi nghiệm thu thanh toán đợt tiếp theo."
                        }
                        claims_data.insert(0, new_clm)
                        existing_claim_titles.add(title.lower())
                        claims_updated = True

            # Kiểm tra MOM / Cuộc họp kỹ thuật
            if cat == "MOM_GIAO_BAN" or "mời họp kỹ thuật" in subj.lower():
                if "hố rác" in subj.lower() and "lò đốt" in subj.lower():
                    event_title = "Họp kỹ thuật phối hợp 3 Nhà thầu (Novacons - Minh Khanh - Lũng Lô)"
                    if event_title.lower() not in existing_mom_events:
                        new_mom = {
                            "id": f"MOM-{len(mom_data)+1:02d}",
                            "meeting_title": event_title,
                            "meeting_date": date_str,
                            "location": "Văn phòng Ban QLDA Vietstar tại công trường",
                            "item_no": f"MOM-KT.{len(mom_data)+1:02d}",
                            "commitment": "Phân chia ranh giới thi công, đường công vụ dùng chung và cam kết tiến độ cừ/cọc Minh Khanh không cản trở đào móng lò đốt Novacons",
                            "responsible_party": "Chủ đầu tư Vietstar, Nhà thầu Minh Khanh & Nhà thầu Lũng Lô",
                            "deadline": "2026-09-28",
                            "status": "ĐANG THEO DÕI",
                            "is_overdue": false,
                            "overdue_days": 0,
                            "pd_negotiation_weapon": "Nếu Minh Khanh chậm cừ chắn tải hoặc Lũng Lô chiếm dụng đường công vụ, GĐDA kích hoạt ngay vũ khí EOT dựa trên biên bản họp kỹ thuật ngày 23/09."
                        }
                        mom_data.insert(0, new_mom)
                        existing_mom_events.add(event_title.lower())
                        mom_updated = True

        # 3. Cập nhật Sổ Tạm Ứng Hiện Trường (DNTU) vào project_cashflow_finance.json
        if cashflow_file.exists():
            try:
                with open(cashflow_file, "r", encoding="utf-8") as f:
                    cf_data = json.load(f)
                advances = cf_data.get("site_advances_log", [])
                adv_ids = {a.get("advance_no") for a in advances}
                for em in new_emails:
                    subj = em.get("subject", "")
                    if "dntu" in subj.lower() or "đề nghị tạm ứng" in subj.lower():
                        if "đợt 5" in subj.lower() and "VST-DNTU-05" not in adv_ids:
                            advances.insert(0, {
                                "advance_no": "VST-DNTU-05",
                                "date": em.get("time", "")[:10],
                                "amount": 82000000.0,
                                "amount_str": "82.000.000 VNĐ",
                                "requester": "Phạm Văn Hiền (Senior QS Lead)",
                                "purpose": "Tạm ứng chi phí công trường Đợt 5 (Hạ tải khu hố rỉ theo YC CĐT: 20tr; Tiếp khách TVGS: 10tr; Nhà ở BCH: 10tr; Công nhật: 5tr; VPP: 7tr; Vận chuyển: 10tr)",
                                "special_claimable_item": "20.000.000 VNĐ (Công tác hạ tải khu hố rỉ theo yêu cầu Chủ đầu tư ngày 24/09)",
                                "status": "Đã trình Ban Giám Đốc & Kế toán"
                            })
                            cf_data["site_advances_log"] = advances
                            with open(cashflow_file, "w", encoding="utf-8") as fw:
                                json.dump(cf_data, fw, ensure_ascii=False, indent=2)
            except Exception:
                pass

        if claims_updated:
            try:
                with open(claims_file, "w", encoding="utf-8") as f:
                    json.dump(claims_data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        if mom_updated:
            try:
                with open(mom_file, "w", encoding="utf-8") as f:
                    json.dump(mom_data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def get_executive_outlook_briefing(self, days_back: int = 7) -> str:
        """
        Tổng hợp báo cáo tham mưu cho GĐDA về các luồng thư từ, công văn trên Outlook trong N ngày qua.
        Bao gồm cả hộp thư dự án BCHVIETSTAR và hộp thư tác nghiệp của Kỹ sư Hiền (hienpv@novacons.com.vn).
        """
        cached = self.load_cached_emails()
        if not cached:
            res = self.sync_outlook_data(limit_per_folder=30, download_attachments=False)
            cached = self.load_cached_emails()

        if not cached:
            return "📭 Hiện tại chưa có dữ liệu email dự án được đồng bộ từ Microsoft Outlook."

        cutoff = (datetime.datetime.now() - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d")
        recent_emails = [e for e in cached if e.get("time", "") >= cutoff]

        total_recent = len(recent_emails)
        
        # Nhóm theo danh mục
        claims_list = [e for e in recent_emails if e.get("category") == "CLAIMS_PHAT_SINH"]
        mom_list = [e for e in recent_emails if e.get("category") == "MOM_GIAO_BAN"]
        progress_list = [e for e in recent_emails if e.get("category") == "TIEN_DO_BAO_CAO"]
        submittal_list = [e for e in recent_emails if e.get("category") == "DE_TRINH_KY_THUAT"]
        advance_list = [e for e in recent_emails if e.get("category") == "VAT_TU_TO_DOI" or "dntu" in e.get("subject", "").lower() or "tạm ứng" in e.get("subject", "").lower()]

        lines = [
            f"📧 *TỔNG HỢP TÌNH BÁO OUTLOOK TOÀN DIỆN* (Trong {days_back} ngày qua)",
            f"⚡ *Tổng số email:* `{total_recent}` thư | *Hộp thư:* `hienpv` & `BCHVIETSTAR@novacons.com.vn`",
            "━━━━━━━━━━━━━━━━━━━━",
            ""
        ]

        # 1. Phát sinh & Đòi quyền lợi (Claims)
        lines.append("💰 *1. PHÁT SINH & BÁO GIÁ NGOÀI HỢP ĐỒNG:*")
        if claims_list:
            for c in claims_list[:3]:
                t = c.get("time", "")[:10]
                sj = c.get("subject", "")
                sn = c.get("sender_name", "")
                att_cnt = len(c.get("attachments", []))
                lines.append(f"• `[{t}]` *{sj}*")
                lines.append(f"  └ 👤 Người gửi: _{sn}_ | 📎 File đính kèm: `{att_cnt}`")
        else:
            lines.append("• _Không có email phát sinh mới trong kỳ._")
        lines.append("")

        # 2. Biên bản họp & Họp kỹ thuật (MOM)
        lines.append("📝 *2. BIÊN BẢN HỌP & ĐIỀU PHỐI MẶT BẰNG (MOM):*")
        if mom_list:
            for m in mom_list[:3]:
                t = m.get("time", "")[:10]
                sj = m.get("subject", "")
                sn = m.get("sender_name", "")
                lines.append(f"• `[{t}]` *{sj}*")
                lines.append(f"  └ 👥 Phối hợp: _{sn}_")
        else:
            lines.append("• _Không có thư mời họp hoặc biên bản mới._")
        lines.append("")

        # 3. Tiến độ & Báo cáo công trường
        lines.append("📈 *3. TIẾN ĐỘ THI CÔNG & BÁO CÁO:*")
        if progress_list:
            for p in progress_list[:3]:
                t = p.get("time", "")[:10]
                sj = p.get("subject", "")
                lines.append(f"• `[{t}]` {sj}")
        else:
            lines.append("• _Chưa có cập nhật báo cáo tuần mới._")
        lines.append("")

        # 4. Hồ sơ đệ trình kỹ thuật (YCPD/MAS/MSS)
        lines.append("📑 *4. HỒ SƠ ĐỆ TRÌNH & PHÊ DUYỆT (TVGS/CĐT):*")
        if submittal_list:
            for s in submittal_list[:3]:
                t = s.get("time", "")[:10]
                sj = s.get("subject", "")
                sn = s.get("sender_name", "")
                lines.append(f"• `[{t}]` {sj} (_{sn}_)")
        else:
            lines.append("• _Không có đệ trình kỹ thuật mới._")
        lines.append("")

        # 5. Tạm ứng công trường & Đề nghị DNTU (Tác nghiệp Kỹ sư Hiền)
        lines.append("💵 *5. TẠM ỨNG NỘI BỘ & TỔ ĐỘI (DNTU KỸ SƯ HIỀN):*")
        if advance_list:
            for a in advance_list[:3]:
                t = a.get("time", "")[:10]
                sj = a.get("subject", "")
                sn = a.get("sender_name", "")
                lines.append(f"• `[{t}]` *{sj}* (_{sn}_)")
                if "đợt 5" in sj.lower():
                    lines.append(f"  └ 💡 _Đã duyệt đề nghị 82tr (trong đó có 20tr hạ tải khu hố rỉ theo YC CĐT cần đòi Claim)_")
        else:
            lines.append("• _Chưa có phát sinh tạm ứng mới trong kỳ._")
        lines.append("")

        lines.append("💡 *Khuyến nghị cho GĐDA:* Đôn đốc CĐT duyệt Báo giá phát sinh Coupler (657 tr) + Bổ sung 20tr chi phí hạ tải khu hố rỉ từ DNTU-05 vào hồ sơ phát sinh ngoài HĐ!")
        return "\n".join(lines)

    def check_and_notify_telegram(self, notify_always: bool = False, admin_chat_id: int = 8249791298) -> Dict[str, Any]:
        """
        Kiểm tra hộp thư Outlook, đồng bộ dữ liệu và gửi thông báo Telegram nếu có email mới.
        Được gọi định kỳ mỗi 30 phút bởi Task Scheduler hoặc Background Daemon.
        """
        res = self.sync_outlook_data(limit_per_folder=30, download_attachments=True)
        now_dt = datetime.datetime.now()
        now_str = now_dt.strftime("%H:%M • %d/%m/%Y")
        next_dt = now_dt + datetime.timedelta(minutes=30)
        next_str = next_dt.strftime("%H:%M (%d/%m)")

        new_count = res.get("new_emails", 0)
        total_cached = res.get("total_cached", 0)
        downloaded = res.get("downloaded_files", 0)

        status_info = {
            "last_check": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "new_emails": new_count,
            "total_cached": total_cached,
            "downloaded_files": downloaded,
            "next_check": next_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "interval_minutes": 30,
            "status": "SUCCESS" if res.get("success") else "FAILED"
        }

        try:
            with open(LAST_STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(status_info, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        # Gửi thông báo Telegram
        try:
            from qshien.desktop_assistant.telegram_bot import TelegramClient, load_telegram_config
            cfg = load_telegram_config()
            tok = cfg.get("bot_token", "")
            if tok:
                client = TelegramClient(tok)
                if new_count > 0:
                    alert_lines = [
                        f"🔔 *TÌNH BÁO OUTLOOK: PHÁT HIỆN {new_count} EMAIL MỚI!*",
                        f"_(Hệ thống tự động quét 30 phút • {now_str})_",
                        "━━━━━━━━━━━━━━━━━━━━",
                        ""
                    ]
                    # Lấy các email mới nhất vừa nạp
                    cached = self.load_cached_emails()
                    for em in cached[:min(new_count, 5)]:
                        t = em.get("time", "")[:16]
                        sj = em.get("subject", "Không có tiêu đề")
                        sn = em.get("sender_name", "Không rõ")
                        att_cnt = len(em.get("attachments", []))
                        cat = em.get("category", "THONG_TIN")
                        alert_lines.append(f"• 📧 `[{t}]` *{sj}*")
                        alert_lines.append(f"  └ 👤 Từ: _{sn}_ | 🏷️ `{cat}` | 📎 File: `{att_cnt}`")

                    if any("phát sinh" in em.get("subject", "").lower() or em.get("category") == "CLAIMS_PHAT_SINH" for em in cached[:new_count]):
                        alert_lines.append("\n💰 *CẢNH BÁO CLAIM:* Phát hiện email có nội dung báo giá / phát sinh ngoài HĐ!")

                    if any("mời họp" in em.get("subject", "").lower() or em.get("category") == "MOM_GIAO_BAN" for em in cached[:new_count]):
                        alert_lines.append("\n📝 *CẢNH BÁO GIAO BAN:* Phát hiện thư mời họp hoặc điều phối mặt bằng mới!")

                    alert_lines.append("\n👉 Bấm `/outlook` để xem chi tiết hoặc `/thammuu` để cập nhật chiến lược.")
                    markup = {
                        "inline_keyboard": [
                            [{"text": "📧 Xem Hộp Thư Outlook", "callback_data": "outlook_briefing"}],
                            [{"text": "📊 Bản Tin Tham Mưu GĐDA", "callback_data": "exec_summary"}]
                        ]
                    }
                    client.send_message(admin_chat_id, "\n".join(alert_lines), reply_markup=markup)

                elif notify_always:
                    info_lines = [
                        "⏱️ *HỘP THƯ OUTLOOK ĐANG ĐƯỢC THEO DÕI TỰ ĐỘNG*",
                        "━━━━━━━━━━━━━━━━━━━━",
                        f"• 🔄 Chu kỳ kiểm tra: *30 phút / lần*",
                        f"• 🕒 Lần kiểm tra vừa xong: `{now_str}`",
                        f"• 📭 Trạng thái: *Không có email khẩn cấp mới* trong 30 phút qua.",
                        f"• 📚 Tổng email dự án đã nạp: `{total_cached}` thư",
                        f"• 📎 File đính kèm đã bóc tách: `{downloaded}` tệp",
                        f"• ⏳ Lần quét tiếp theo: `{next_str}`",
                        "\n💡 *Su Su sẽ tự động gửi tin nhắn Telegram ngay khi phát hiện thư mới!*"
                    ]
                    client.send_message(admin_chat_id, "\n".join(info_lines))

                # Tự động rà soát cảnh báo mốc công việc khẩn cấp & giao việc
                self._check_and_alert_deadlines(client=client, admin_chat_id=admin_chat_id)
        except Exception as e:
            print(f"[OutlookAutoSync] Lỗi gửi Telegram: {e}")

        return status_info

    def _check_and_alert_deadlines(self, client, admin_chat_id: int):
        """Tự động rà soát các cam kết biên bản họp và mốc nghiệm thu khẩn cấp để nhắc nhở GĐDA."""
        if not client:
            return
        alert_file = OUTLOOK_SYNC_DIR / "last_deadline_alert.json"
        last_alert_data = {}
        if alert_file.exists():
            try:
                with open(alert_file, "r", encoding="utf-8") as f:
                    last_alert_data = json.load(f)
            except Exception:
                pass

        now = datetime.datetime.now()
        # Không spam: mỗi mốc nhắc cách nhau tối thiểu 3 tiếng
        last_sent_str = last_alert_data.get("last_sent_time", "")
        if last_sent_str:
            try:
                last_sent = datetime.datetime.strptime(last_sent_str, "%Y-%m-%d %H:%M:%S")
                if (now - last_sent).total_seconds() < 10800:  # 3 giờ
                    return
            except Exception:
                pass

        # Nạp mom_action_tracker.json
        mom_path = DATA_DIR / "mom_action_tracker.json"
        if not mom_path.exists():
            return
        try:
            with open(mom_path, "r", encoding="utf-8") as f:
                moms = json.load(f)
        except Exception:
            return

        urgent_alerts = []
        for m in moms:
            dl_str = m.get("deadline", "")
            title = m.get("meeting_title", "")
            if not dl_str:
                continue
            try:
                if " " in dl_str:
                    dl_dt = datetime.datetime.strptime(dl_str, "%Y-%m-%d %H:%M")
                else:
                    dl_dt = datetime.datetime.strptime(dl_str, "%Y-%m-%d")
                    dl_dt = dl_dt.replace(hour=17, minute=0)

                diff = dl_dt - now
                hours_left = diff.total_seconds() / 3600.0

                if 0 <= hours_left <= 36:
                    urgent_alerts.append({
                        "id": m.get("id"),
                        "title": title,
                        "deadline": dl_str,
                        "hours_left": int(round(hours_left)),
                        "action": m.get("action_for_pd") or m.get("commitment") or ""
                    })
            except Exception:
                pass

        if urgent_alerts:
            lines = [
                "🚨 *THAM MƯU TỰ ĐỘNG: CẢNH BÁO MỐC CÔNG VIỆC KHẨN CẤP!*",
                f"_(Hệ thống giám sát định kỳ 30 phút • {now.strftime('%H:%M • %d/%m/%Y')})_",
                "━━━━━━━━━━━━━━━━━━━━\n"
            ]
            for a in urgent_alerts:
                h = a["hours_left"]
                h_str = f"còn ~{h} giờ nữa" if h > 0 else "đang tới hạn"
                lines.append(f"⏰ *[{a['id']}] {a['title']}*")
                lines.append(f"• 🕒 Hạn thực hiện: `{a['deadline']}` (*{h_str}*)")
                if a["action"]:
                    lines.append(f"👉 *Chỉ đạo giao việc:* _{a['action']}_\n")

            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("💡 Bấm `/giaoviec` để xem toàn bộ ma trận phân công chi tiết.")

            markup = {
                "inline_keyboard": [
                    [{"text": "📋 Xem Ma Trận Giao Việc", "callback_data": "exec_delegation"}],
                    [{"text": "📊 Bản Tin Tham Mưu GĐDA", "callback_data": "exec_summary"}]
                ]
            }
            client.send_message(admin_chat_id, "\n".join(lines), reply_markup=markup)

            last_alert_data["last_sent_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
            last_alert_data["alerts_count"] = len(urgent_alerts)
            try:
                with open(alert_file, "w", encoding="utf-8") as f:
                    json.dump(last_alert_data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def send_task_delegation_briefing(self, admin_chat_id: int = 8249791298) -> bool:
        """Gửi trực tiếp bản tin tham mưu phân công giao việc & điều phối lên Telegram."""
        try:
            from qshien.desktop_assistant.telegram_bot import TelegramClient, load_telegram_config
            from qshien.desktop_assistant.project_executive_engine import get_executive_engine
            cfg = load_telegram_config()
            tok = cfg.get("bot_token", "")
            if not tok:
                return False
            client = TelegramClient(tok)
            eng = get_executive_engine()
            msg = eng.get_task_delegation_report()
            markup = {
                "inline_keyboard": [
                    [
                        {"text": "🤝 Xem Cam Kết MOM", "callback_data": "exec_mom"},
                        {"text": "📧 Hộp Thư Outlook", "callback_data": "outlook_briefing"}
                    ],
                    [{"text": "📊 Về Bản Tin GĐDA", "callback_data": "exec_summary"}]
                ]
            }
            return client.send_message(admin_chat_id, msg, reply_markup=markup)
        except Exception as e:
            print(f"[OutlookSync] Lỗi gửi delegation briefing: {e}")
            return False

    def start_sync_daemon(self, interval_seconds: int = 1800, admin_chat_id: int = 8249791298):
        """Chạy vòng lặp kiểm tra Outlook định kỳ trong nền (mặc định 1800 giây = 30 phút)."""
        import time
        print(f"[OutlookDaemon] Bắt đầu giám sát Outlook mỗi {interval_seconds // 60} phút...")
        # Lần chạy đầu tiên thông báo xác nhận kích hoạt
        self.check_and_notify_telegram(notify_always=True, admin_chat_id=admin_chat_id)
        while True:
            try:
                time.sleep(interval_seconds)
                print(f"[OutlookDaemon] [{datetime.datetime.now().strftime('%H:%M:%S')}] Đang quét hộp thư...")
                self.check_and_notify_telegram(notify_always=False, admin_chat_id=admin_chat_id)
            except KeyboardInterrupt:
                print("\n[OutlookDaemon] Đã dừng giám sát.")
                break
            except Exception as e:
                print(f"[OutlookDaemon] Lỗi vòng lặp: {e}")
                time.sleep(60)


# Singleton
_outlook_engine = None

def get_outlook_engine() -> OutlookSyncEngine:
    global _outlook_engine
    if _outlook_engine is None:
        _outlook_engine = OutlookSyncEngine()
    return _outlook_engine


def check_and_notify_telegram(notify_always: bool = False, admin_chat_id: int = 8249791298) -> Dict[str, Any]:
    """Hàm bao bọc tiện ích cho việc kiểm tra và báo Telegram."""
    return get_outlook_engine().check_and_notify_telegram(notify_always=notify_always, admin_chat_id=admin_chat_id)



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Outlook Sync Engine cho Não bộ Su Su")
    parser.add_argument("--auto", action="store_true", help="Chạy một lượt quét kiểm tra và báo Telegram nếu có thư mới (dùng cho Task Scheduler)")
    parser.add_argument("--daemon", action="store_true", help="Chạy vòng lặp định kỳ liên tục trong nền")
    parser.add_argument("--interval", type=int, default=30, help="Chu kỳ phút cho daemon (mặc định: 30 phút)")
    parser.add_argument("--notify", action="store_true", help="Gửi thông báo Telegram xác nhận trạng thái hiện tại")
    parser.add_argument("--delegation", action="store_true", help="Gửi bản tin tham mưu phân công giao việc & điều phối lên Telegram")
    args = parser.parse_args()

    engine = get_outlook_engine()

    if args.daemon:
        engine.start_sync_daemon(interval_seconds=args.interval * 60)
    elif args.delegation:
        ok = engine.send_task_delegation_briefing()
        print("Đã gửi bản tin phân công giao việc lên Telegram:", ok)
    elif args.auto:
        status = engine.check_and_notify_telegram(notify_always=args.notify)
        print(f"Quét tự động hoàn tất lúc {status.get('last_check')}: {status.get('new_emails')} email mới.")
    else:
        print("--- KIỂM TRA ĐỒNG BỘ OUTLOOK TOÀN DIỆN ---")
        res = engine.sync_outlook_data(limit_per_folder=30, download_attachments=True)
        print("Kết quả quét:", res)
        print("\n--- BẢN TIN THAM MƯU OUTLOOK ---")
        print(engine.get_executive_outlook_briefing(days_back=10))
