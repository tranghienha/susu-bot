# -*- coding: utf-8 -*-
"""
outlook_sync_engine.py - Động Cơ Tự Động Kết Nối & Đồng Bộ Dữ Liệu Microsoft Outlook Cho Su Su
=============================================================================================
Nhiệm vụ:
1. Kết nối an toàn với Microsoft Outlook Desktop cục bộ qua MAPI (win32com.client).
2. Quét & trích xuất thư từ tài khoản dự án:
   - BCHVIETSTAR@novacons.com.vn (Inbox & Sent)
   - Thư mục VIETSTAR (Báo cáo tuần, Báo cáo ngày, YCPD, YCVT, Công văn...)
   - Lọc thư liên quan đến Vietstar trong hienpv@novacons.com.vn (bảo mật tuyệt đối email cá nhân).
3. Phân loại thông minh theo 5 Trụ Cột Quản trị GĐDA:
   - 💰 CLAIMS & PHÁT SINH (Báo giá ngoài HĐ, vướng mặt bằng, yêu cầu bồi hoàn)
   - 📝 MOM & GIAO BAN (Thư mời họp kỹ thuật, biên bản giao ban 3 bên, chỉ đạo CĐT)
   - 📈 TIẾN ĐỘ & BÁO CÁO (Báo cáo tuần, báo cáo ngày, đệ trình tiến độ tổng thể)
   - 📑 ĐỆ TRÌNH KỸ THUẬT (YCPD, MAS vật tư, MSS biện pháp thi công, SDS shopdrawing)
   - 👷 VẬT TƯ & TỔ ĐỘI (YCVT, tạm ứng, khối lượng thầu phụ)
4. Tự động lưu trữ file đính kèm (.pdf, .docx, .xlsx) vào Data/outlook_attachments/.
5. Tự động cập nhật hồ sơ tham mưu: project_claims_log.json, mom_action_tracker.json.
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
        "ycvt", "vật tư", "tạm ứng", "thanh toán đội", "tổ đội", "thầu phụ", "tăng ca", "hóa đơn"
    ]
}


def _safe_str(val: Any) -> str:
    """Chuyển đổi giá trị sang chuỗi an toàn."""
    if val is None:
        return ""
    return str(val).strip()


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
            
    # Kiểm tra Vật tư & Tổ đội
    for kw in CATEGORY_KEYWORDS["VAT_TU_TO_DOI"]:
        if kw in text:
            return "VAT_TU_TO_DOI"
            
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
        Trả về thống kê số lượng email mới, file tải về và cảnh báo.
        """
        if not self._is_connected:
            if not self.connect():
                return {
                    "success": False,
                    "error": "Không thể kết nối với Microsoft Outlook trên máy tính.",
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
            # 3. Hộp thư cá nhân anh Hiền (Chỉ quét thư liên quan đến Vietstar)
            elif "HIENPV" in f_name.lower():
                try:
                    inbox = folder.Folders["Inbox"]
                    target_sources.append((f"{f_name}/Inbox_Filtered", inbox))
                except Exception:
                    pass

        for source_name, folder_obj in target_sources:
            try:
                items = folder_obj.Items
                # Sắp xếp theo ReceivedTime giảm dần nếu có
                count = items.Count
                start_idx = max(1, count - limit_per_folder + 1)

                is_personal = "HIENPV" in source_name.upper()

                for i in range(count, start_idx - 1, -1):
                    try:
                        item = items(i)
                        
                        # Bỏ qua nếu không phải email
                        if not hasattr(item, "Subject"):
                            continue

                        subject = _safe_str(getattr(item, "Subject", ""))
                        body = _safe_str(getattr(item, "Body", ""))

                        # Nếu là hòm thư cá nhân, chỉ lấy thư có chứa từ khóa dự án Vietstar
                        if is_personal:
                            check_text = f"{subject} {body}".lower()
                            if not any(k in check_text for k in ["vietstar", "vst", "lò đốt", "hố rác", "novacons"]):
                                continue

                        entry_id = _safe_str(getattr(item, "EntryID", ""))
                        if not entry_id:
                            entry_id = f"{subject}_{str(getattr(item, 'ReceivedTime', ''))}"

                        if entry_id in existing_ids:
                            continue

                        sender_name = _safe_str(getattr(item, "SenderName", ""))
                        sender_email = _safe_str(getattr(item, "SenderEmailAddress", ""))
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
        # Sắp xếp mới nhất lên đầu
        all_emails.sort(key=lambda x: x.get("time", ""), reverse=True)
        self.save_cached_emails(all_emails)

        # Tự động đồng bộ các thư quan trọng vào Hồ sơ Claim & MOM
        self._auto_update_project_dossiers(new_records)

        return {
            "success": True,
            "new_emails": len(new_records),
            "total_cached": len(all_emails),
            "downloaded_files": downloaded_count
        }

    def _auto_update_project_dossiers(self, new_emails: List[Dict[str, Any]]):
        """Tự động phân tích các email mới để bổ sung vào project_claims_log.json & mom_action_tracker.json."""
        claims_file = DATA_DIR / "project_claims_log.json"
        mom_file = DATA_DIR / "mom_action_tracker.json"

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

        existing_mom_events = {m.get("event", "").lower() for m in mom_data}

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
                    title = "Báo giá phát sinh sử dụng Coupler nối thép móng lò đốt PK1 & vách hố rác"
                    if title.lower() not in existing_claim_titles:
                        new_clm = {
                            "id": f"CLM-VST-{len(claims_data)+1:02d}",
                            "project": "Dự án Nhà máy tích hợp xử lý chất thải rắn Vietstar (344,89 tỷ)",
                            "title": title,
                            "event_date": date_str,
                            "notice_date": date_str,
                            "delay_days": 0,
                            "caused_by": "Chủ đầu tư / Thiết kế yêu cầu đổi biện pháp nối thép bằng Coupler",
                            "contract_clauses": [
                                "Điều 7: Phát sinh và Điều chỉnh giá hợp đồng",
                                "Điều 4: Tiêu chuẩn kỹ thuật thi công và nghiệm thu"
                            ],
                            "impact_cost_vnd": 0,
                            "impact_cost_str": "Đang chờ CĐT phê duyệt dự toán chi tiết",
                            "impact_description": "Novacons đã phát hành Báo giá phát sinh Coupler móng lò đốt PK1 + vách hố rác và Bê tông chèn Shoring cừ Larsen gửi CĐT ngày 24/09/2026.",
                            "eot_requested_days": 0,
                            "status": "Đã gửi Email & Tờ trình báo giá phát sinh; đang theo dõi phản hồi phê duyệt từ CĐT Vietstar.",
                            "ref_document": f"Email gửi CĐT ngày {date_str} kèm file Báo giá PDF",
                            "action_for_pd": "Đôn đốc Đại diện CĐT (Anh Hạnh Lê / Anh Tuấn) phê duyệt văn bản trước khi đổ bê tông lót và gia công thép đại trà."
                        }
                        claims_data.insert(0, new_clm)
                        existing_claim_titles.add(title.lower())
                        claims_updated = True

            # Kiểm tra MOM / Cuộc họp kỹ thuật
            if cat == "MOM_GIAO_BAN" or "mời họp kỹ thuật" in subj.lower():
                if "hố rác" in subj.lower() and "lò đốt" in subj.lower():
                    event_title = "Họp kỹ thuật phối hợp 3 Nhà thầu (Novacons, Minh Khanh, Lũng Lô) khu vực Hố rác - Lò đốt"
                    if event_title.lower() not in existing_mom_events:
                        new_mom = {
                            "id": f"MOM-VST-{len(mom_data)+1:02d}",
                            "meeting_date": date_str,
                            "meeting_title": "Cuộc họp kỹ thuật giao thoa mặt bằng thi công khu vực Hố rác, Lò đốt & Sảnh mở rộng",
                            "party": "Chủ đầu tư Vietstar, Novacons, Minh Khanh (Cọc/Cừ), Lũng Lô (Sảnh), Tư vấn VNCC-VCC",
                            "commitments": [
                                "Novacons là Nhà thầu chính kết cấu Hố rác & Lò đốt.",
                                "Thống nhất ranh giới bàn giao mặt bằng và tuyến đường công vụ dùng chung giữa 3 nhà thầu.",
                                "Minh Khanh cam kết mốc hoàn thành cừ chắn tải bãi rác và cọc hố rác để không làm cản trở tiến độ đào đất móng lò đốt của Novacons.",
                                "Nếu các nhà thầu khác làm tắc nghẽn mặt bằng hoặc cản trở đường công vụ, Novacons sẽ lập biên bản hiện trường làm căn cứ bảo lưu quyền đòi EOT."
                            ],
                            "status": "Đang theo dõi thực hiện tại hiện trường",
                            "action_for_pd": "Cử Chỉ huy trưởng và Trưởng ban An ninh công trường chốt ngay mốc ranh giới, chụp ảnh hiện trạng lập biên bản 3 bên làm bằng chứng phòng thủ pháp lý."
                        }
                        mom_data.insert(0, new_mom)
                        existing_mom_events.add(event_title.lower())
                        mom_updated = True

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
        """
        cached = self.load_cached_emails()
        if not cached:
            # Thử đồng bộ ngay nếu chưa có dữ liệu
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

        lines = [
            f"📧 *TỔNG HỢP TÌNH BÁO OUTLOOK DỰ ÁN VIETSTAR* (Trong {days_back} ngày qua)",
            f"⚡ *Tổng số email trao đổi:* `{total_recent}` thư | *Hòm thư chính:* `BCHVIETSTAR@novacons.com.vn`",
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
            lines.append("• _Không có email phát sinh mới trong 7 ngày qua._")
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

        lines.append("💡 *Khuyến nghị cho GĐDA:* Đôn đốc CĐT phê duyệt Báo giá phát sinh Coupler móng lò đốt và chốt biên bản hiện trạng mặt bằng với Minh Khanh/Lũng Lô để bảo lưu quyền đòi gia hạn EOT!")
        return "\n".join(lines)


# Singleton
_outlook_engine = None

def get_outlook_engine() -> OutlookSyncEngine:
    global _outlook_engine
    if _outlook_engine is None:
        _outlook_engine = OutlookSyncEngine()
    return _outlook_engine


if __name__ == "__main__":
    print("--- KIỂM TRA ĐỒNG BỘ OUTLOOK DỰ ÁN VIETSTAR ---")
    engine = get_outlook_engine()
    res = engine.sync_outlook_data(limit_per_folder=30, download_attachments=True)
    print("Kết quả quét:", res)
    print("\n--- BẢN TIN THAM MƯU OUTLOOK ---")
    print(engine.get_executive_outlook_briefing(days_back=10))
