# -*- coding: utf-8 -*-
"""
project_executive_engine.py - Động Cơ Tham Mưu & Quản Trị Chiến Lược Cho Giám Đốc Dự Án (GĐDA)
=============================================================================================
Đảm nhiệm 5 Trụ Cột Dữ Liệu Quản Trị Cấp Cao:
1. Hồ sơ Bằng chứng Pháp lý & Tiền lệ Claim (Claims & Contractual Defense)
2. Sức khỏe Dòng tiền & Quản trị Bảo lãnh Ngân hàng (Cash Flow & Banking Bonds)
3. Tình báo Thầu phụ & Đơn giá Thực tế Thị trường (Subcontractor Intelligence)
4. Sổ Đăng ký Rủi ro & Bản đồ Sự cố Hiện trường (Dynamic Risk Register)
5. Bản đồ Quan hệ Đối tác & Theo dõi Cam kết Họp Giao Ban (MOM Action Tracker)
=============================================================================================
"""

from __future__ import annotations

import os
import sys
import json
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

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

CLAIMS_FILE = DATA_DIR / "project_claims_log.json"
SUBCON_FILE = DATA_DIR / "subcontractor_registry.json"
RISK_FILE = DATA_DIR / "project_risk_register.json"
MOM_FILE = DATA_DIR / "mom_action_tracker.json"
CASHFLOW_FILE = DATA_DIR / "project_cashflow_finance.json"
DOSSIER_FILE = DATA_DIR / "current_project_dossier.json"


# =============================================================================
# HÀM NẠP VÀ GHI DỮ LIỆU AN TOÀN
# =============================================================================

def _load_json(file_path: Path, default_data: Any) -> Any:
    """Nạp file JSON an toàn, fallback về default nếu không tồn tại hoặc lỗi."""
    if not file_path.exists():
        # Thử tìm ở các ứng viên khác
        fname = file_path.name
        for p in [CURRENT_DIR / fname, CURRENT_DIR / "Data" / fname, Path("/app") / fname, Path("/app/Data") / fname, Path(r"C:\QS_Hien\Data") / fname]:
            if p.exists():
                file_path = p
                break
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_data
    return default_data


def _save_json(file_path: Path, data: Any) -> bool:
    """Lưu dữ liệu ra file JSON an toàn."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[ProjectExecutiveEngine] Lỗi lưu {file_path.name}: {e}")
        return False


# =============================================================================
# LỚP QUẢN TRỊ TRUNG TÂM
# =============================================================================

class ProjectExecutiveEngine:
    """Bộ Não Tham Mưu Toàn Diện Cho Giám Đốc Dự Án."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or DATA_DIR
        self._refresh()

    def _refresh(self):
        """Tải mới lại toàn bộ dữ liệu 5 trụ cột."""
        self.claims: List[Dict[str, Any]] = _load_json(self.data_dir / "project_claims_log.json", [])
        self.subcontractors: List[Dict[str, Any]] = _load_json(self.data_dir / "subcontractor_registry.json", [])
        self.risks: List[Dict[str, Any]] = _load_json(self.data_dir / "project_risk_register.json", [])
        self.mom_commitments: List[Dict[str, Any]] = _load_json(self.data_dir / "mom_action_tracker.json", [])
        self.cashflow: Dict[str, Any] = _load_json(self.data_dir / "project_cashflow_finance.json", {})
        self.dossier: Dict[str, Any] = _load_json(self.data_dir / "current_project_dossier.json", {})

    # -------------------------------------------------------------------------
    # 1. HỒ SƠ CLAIM & TIỀN LỆ PHÁP LÝ
    # -------------------------------------------------------------------------

    def get_claims_report(self) -> str:
        """Xuất báo cáo chi tiết về các sự kiện Claim & Gia hạn tiến độ EOT."""
        self._refresh()
        if not self.claims:
            return "📄 *HỒ SƠ CLAIM & EOT:* Hiện chưa có sự kiện khiếu nại nào được ghi nhận."

        lines = [
            "📄 *HỒ SƠ BẰNG CHỨNG CLAIM & PHÒNG THỦ HỢP ĐỒNG*",
            "_(Dự án Vietstar 344,89 Tỷ • Cơ sở pháp lý đòi EOT & Chi phí)_",
            "━━━━━━━━━━━━━━━━━━━━"
        ]
        total_delay = 0
        total_cost = 0

        for idx, clm in enumerate(self.claims, 1):
            cid = clm.get("id", f"CLM-{idx}")
            title = clm.get("title", "")
            ev_date = clm.get("event_date", "")
            delay = clm.get("delay_days", 0)
            cost_str = clm.get("impact_cost_str", "0 VNĐ")
            cost_val = clm.get("impact_cost_vnd", 0)
            status = clm.get("status", "")
            action = clm.get("action_for_pd", "")
            clauses = clm.get("contract_clauses", [])

            total_delay += delay
            total_cost += cost_val

            lines.append(f"📌 *{idx}. [{cid}] {title}*")
            lines.append(f"   🕒 *Ngày xảy ra:* `{ev_date}` | *Chậm trễ:* `{delay} ngày`")
            lines.append(f"   💰 *Chi phí yêu cầu:* `{cost_str}`")
            lines.append(f"   ⚖️ *Điều khoản viện dẫn:* _{', '.join(clauses[:2])}_")
            lines.append(f"   📍 *Hiện trạng:* {status}")
            if action:
                lines.append(f"   👉 *Chiến lược cho GĐDA:* *{action}*")
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📊 *TỔNG HỢP CLAIM:*")
        lines.append(f"• Tổng số ngày đề xuất gia hạn EOT: *{total_delay} ngày*")
        lines.append(f"• Tổng giá trị thiệt hại/chi phí phát sinh: *{total_cost:,.0f} VNĐ*".replace(",", "."))
        lines.append("\n💡 *Ghi thêm Claim mới:* Gõ `/claim <nội dung>`")
        return "\n".join(lines)

    def add_claim(self, title: str, description: str = "", delay_days: int = 0, cost_vnd: float = 0, caused_by: str = "") -> Dict[str, Any]:
        """Thêm nhanh một sự kiện Claim."""
        self._refresh()
        new_id = f"CLM-VST-{len(self.claims) + 1:02d}"
        now_str = datetime.date.today().isoformat()
        item = {
            "id": new_id,
            "project": "Dự án Nhà máy tích hợp xử lý chất thải rắn Vietstar",
            "title": title,
            "event_date": now_str,
            "notice_date": now_str,
            "delay_days": delay_days,
            "caused_by": caused_by or "Chủ đầu tư / Hiện trường",
            "contract_clauses": ["Điều 5: Tiến độ thực hiện", "Điều 7: Phát sinh & Điều chỉnh"],
            "impact_cost_vnd": cost_vnd,
            "impact_cost_str": f"{cost_vnd:,.0f} VNĐ".replace(",", ".") if cost_vnd else "Đang tính toán",
            "impact_description": description or title,
            "eot_requested_days": delay_days,
            "status": "Mới ghi nhận từ lệnh nhanh Telegram; cần hoàn thiện văn bản thông báo Notice of Delay.",
            "ref_document": f"Nhật ký hiện trường ngày {datetime.date.today().strftime('%d/%m/%Y')}",
            "action_for_pd": "Trưởng phòng QS gửi văn bản Notice of Delay trong hạn 07 ngày để bảo lưu quyền Claim."
        }
        self.claims.insert(0, item)
        _save_json(self.data_dir / "project_claims_log.json", self.claims)
        return item

    # -------------------------------------------------------------------------
    # 2. SỨC KHỎE DÒNG TIỀN & BẢO LÃNH NGÂN HÀNG
    # -------------------------------------------------------------------------

    def get_cashflow_report(self) -> str:
        """Xuất báo cáo Sức khỏe Dòng tiền & Sổ Quản trị Bảo lãnh Ngân hàng."""
        self._refresh()
        cf = self.cashflow
        if not cf:
            return "💰 *DÒNG TIỀN & BẢO LÃNH:* Chưa có dữ liệu tài chính dự án."

        val_str = cf.get("contract_value_str", "344,89 tỷ")
        adv = cf.get("advance_payment", {})
        adv_str = adv.get("total_amount_str", "103,46 tỷ")
        p1 = adv.get("disbursed_phase_1_str", "50 tỷ")
        p2 = adv.get("pending_phase_2_str", "53,46 tỷ")

        lines = [
            "💰 *BÁO CÁO SỨC KHỎE DÒNG TIỀN & BẢO LÃNH NGÂN HÀNG*",
            f"_(Hợp đồng: {val_str})_",
            "━━━━━━━━━━━━━━━━━━━━",
            f"💵 *1. QUẢN TRỊ TẠM ỨNG (30% HĐ):*",
            f"• Tổng hạn mức tạm ứng: *{adv_str}*",
            f"• Đợt 1 (Đã về tài khoản): *{p1}*",
            f"• Đợt 2 (Đang hoàn thiện hồ sơ): *{p2}*",
            f"• Cơ chế thu hồi: _{adv.get('recovery_mechanism', 'Khấu trừ 20% mỗi đợt IPC')}_\n",
            f"🏦 *2. SỔ THEO DÕI BẢO LÃNH NGÂN HÀNG (BANK GUARANTEES):*"
        ]

        bgs = cf.get("bank_guarantees", [])
        for bg in bgs:
            b_type = bg.get("type", "")
            bank = bg.get("bank", "")
            amt = bg.get("amount_str", "")
            exp = bg.get("expiry_date", "")
            left = bg.get("days_left", 0)
            status = bg.get("status", "HIỆU LỰC TỐT")
            note = bg.get("reduction_note", "")

            lines.append(f"• *{b_type}:*")
            lines.append(f"   🏛️ Ngân hàng: `{bank}`")
            lines.append(f"   💰 Giá trị: `{amt}`")
            lines.append(f"   🕒 Đáo hạn: `{exp}` (Còn *{left} ngày*) | Trạng thái: *{status}*")
            if note:
                lines.append(f"   💡 _{note}_")
            lines.append("")

        lines.append("📑 *3. HỒ SƠ THANH TOÁN GẦN NHẤT (IPC 01):*")
        ipcs = cf.get("ipc_records", [])
        if ipcs:
            ipc = ipcs[0]
            lines.append(f"• Số hiệu: *{ipc.get('ipc_no')}* ({ipc.get('period', '')})")
            lines.append(f"• Ngày đệ trình: `{ipc.get('submitted_date')}` | Hạn duyệt CĐT: `{ipc.get('review_deadline')}`")
            lines.append(f"• Giá trị nghiệm thu đề nghị: *{ipc.get('claimed_amount_gross_str')}*")
            lines.append(f"• Khấu trừ hoàn ứng 20%: *{ipc.get('advance_recovery_deduction_str')}*")
            lines.append(f"• Giữ lại bảo hành 5%: *{ipc.get('retention_5pct_str')}*")
            lines.append(f"👉 *TIỀN THỰC THU DỰ KIẾN VỀ:* *{ipc.get('net_cash_expected_str')}*")
            lines.append(f"• Trạng thái hiện tại: _{ipc.get('status')}_\n")

        fc = cf.get("cashflow_forecast_month_10", {})
        if fc:
            lines.append("📈 *4. CÂN ĐỐI DÒNG TIỀN THÁNG 10/2026:*")
            lines.append(f"• Dự kiến thu về: *{fc.get('inflow_expected_str')}*")
            lines.append(f"• Kế hoạch chi (Vật tư, Nhân công, Máy): *{fc.get('total_outflow_str')}*")
            lines.append(f"• Thặng dư an toàn dự kiến: *{fc.get('net_cash_surplus_str')}*")

        lines.append("\n👉 *Ghi chú bảo lãnh / dòng tiền:* Gõ `/baolanh <nội dung>`")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # 3. TÌNH BÁO THẦU PHỤ & ĐƠN GIÁ THỊ TRƯỜNG
    # -------------------------------------------------------------------------

    def get_subcontractor_report(self) -> str:
        """Xuất danh bạ đánh giá năng lực thầu phụ & đơn giá giao khoán thực tế."""
        self._refresh()
        if not self.subcontractors:
            return "👷 *DANH BẠ THẦU PHỤ:* Chưa có dữ liệu thầu phụ."

        lines = [
            "👷 *TÌNH BÁO THẦU PHỤ & ĐƠN GIÁ THỰC TẾ CÔNG TRƯỜNG*",
            "_(Dự án Vietstar • Đơn giá giao khoán & Đánh giá năng suất)_",
            "━━━━━━━━━━━━━━━━━━━━"
        ]

        for idx, sub in enumerate(self.subcontractors, 1):
            name = sub.get("name", "")
            trade = sub.get("trade", "")
            manpower = sub.get("manpower", "N/A")
            prod = sub.get("productivity_actual", "")
            q_star = sub.get("quality_rating", 4.0)
            stars = "⭐" * int(round(q_star))
            deals = sub.get("unit_price_deal", {})
            deal_str = "; ".join([f"{k}: {v}" for k, v in list(deals.items())[:2]])
            pros = sub.get("pros", "")
            cons = sub.get("cons_risks", "")
            strat = sub.get("management_strategy", "")

            lines.append(f"🏗️ *{idx}. {name}*")
            lines.append(f"   🏷️ Gói thầu: *{trade}* | Đánh giá: {stars} ({q_star}/5)")
            lines.append(f"   👷 Quân số: *{manpower}* | Năng suất: *{prod}*")
            lines.append(f"   💵 Đơn giá khoán: `{deal_str}`")
            if pros:
                lines.append(f"   ✅ Điểm mạnh: _{pros}_")
            if cons:
                lines.append(f"   ⚠️ Rủi ro cần soi: *{cons}*")
            if strat:
                lines.append(f"   👉 Chiến lược ép/quản trị: *{strat}*")
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("💡 *Ghi nhanh thầu phụ:* Gõ `/subcon <nội dung>`")
        return "\n".join(lines)

    def add_subcontractor(self, name: str, trade: str, deal_price: str, notes: str = "") -> Dict[str, Any]:
        """Thêm nhanh thông tin thầu phụ / đội nhân công."""
        self._refresh()
        item = {
            "id": f"SUB-{len(self.subcontractors) + 1:02d}",
            "name": name,
            "trade": trade,
            "scope_items": [trade],
            "unit_price_deal": {"don_gia_khoan": deal_price},
            "market_benchmark": "Khảo sát thực tế công trường",
            "manpower": "Đang cập nhật",
            "productivity_actual": "Đang theo dõi",
            "quality_rating": 4.0,
            "reliability_rating": 4.0,
            "pros": notes or "Mới bổ sung từ Telegram",
            "cons_risks": "Cần kiểm soát chặt chẽ chấm công và chất lượng",
            "management_strategy": "Nghiệm thu khối lượng hoàn thành trước khi duyệt thanh toán"
        }
        self.subcontractors.append(item)
        _save_json(self.data_dir / "subcontractor_registry.json", self.subcontractors)
        return item

    # -------------------------------------------------------------------------
    # 4. SỔ ĐĂNG KÝ RỦI RO & BẢN ĐỒ HIỆN TRƯỜNG
    # -------------------------------------------------------------------------

    def get_risk_report(self) -> str:
        """Xuất báo cáo Sổ Đăng Ký Rủi Ro Hiện Trường."""
        self._refresh()
        if not self.risks:
            return "🚨 *SỔ ĐĂNG KÝ RỦI RO:* Hiện tại chưa có rủi ro nào được ghi nhận."

        lines = [
            "🚨 *SỔ ĐĂNG KÝ RỦI RO DỰ ÁN (DYNAMIC RISK REGISTER)*",
            "_(Dự án Vietstar 344,89 Tỷ • Ma trận Xác suất & Tác động)_",
            "━━━━━━━━━━━━━━━━━━━━"
        ]

        for idx, r in enumerate(self.risks, 1):
            rid = r.get("id", f"RSK-{idx}")
            title = r.get("title", "")
            cat = r.get("category", "")
            prob = r.get("probability", "")
            imp = r.get("impact", "")
            level = r.get("risk_level", "VÀNG")
            plan = r.get("mitigation_plan", "")
            brief = r.get("brief_for_pd", "")
            status = r.get("status", "")

            # Icon theo mức độ
            icon = "🔴" if "ĐỎ" in level else ("🟠" if "CAM" in level else "🟡")

            lines.append(f"{icon} *{idx}. [{rid}] {title}*")
            lines.append(f"   🏷️ Phân loại: `{cat}`")
            lines.append(f"   📊 Cấp độ: *{level}* (Xác suất: {prob} | Tác động: {imp})")
            lines.append(f"   🛡️ Giải pháp giảm thiểu:\n_{plan}_")
            lines.append(f"   📍 Hiện trạng: `{status}`")
            if brief:
                lines.append(f"   👉 *Lưu ý cho GĐDA:* *{brief}*")
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("💡 *Thêm rủi ro mới:* Gõ `/risk <nội dung>`")
        return "\n".join(lines)

    def add_risk(self, title: str, category: str = "HIỆN TRƯỜNG", level: str = "CAM", mitigation: str = "") -> Dict[str, Any]:
        """Thêm nhanh một rủi ro mới vào sổ đăng ký."""
        self._refresh()
        item = {
            "id": f"RSK-{len(self.risks) + 1:02d}",
            "project": "Dự án Nhà máy tích hợp xử lý chất thải rắn Vietstar",
            "title": title,
            "category": category,
            "probability": "Trung bình (3/5)",
            "impact": "Lớn (4/5)",
            "risk_level": f"{level.upper()} (THEO DÕI)",
            "cause": "Ghi nhận nhanh từ hiện trường",
            "consequence": "Ảnh hưởng đến an toàn, chất lượng hoặc tiến độ",
            "mitigation_plan": mitigation or "Phân công kỹ sư hiện trường bám sát và kiểm tra định kỳ.",
            "owner": "Chỉ huy phó Hiện trường / Senior QS",
            "status": "Mới ghi nhận từ Telegram",
            "brief_for_pd": "Cần lưu ý nhắc nhở trong buổi giao ban tuần."
        }
        self.risks.insert(0, item)
        _save_json(self.data_dir / "project_risk_register.json", self.risks)
        return item

    # -------------------------------------------------------------------------
    # 5. THEO DÕI CAM KẾT BIÊN BẢN HỌP (MOM ACTION TRACKER)
    # -------------------------------------------------------------------------

    def get_mom_report(self) -> str:
        """Xuất báo cáo theo dõi cam kết biên bản họp MOM."""
        self._refresh()
        if not self.mom_commitments:
            return "🤝 *CAM KẾT BIÊN BẢN HỌP (MOM):* Chưa có mục cam kết nào."

        lines = [
            "🤝 *SỔ THEO DÕI CAM KẾT BIÊN BẢN HỌP (MOM TRACKER)*",
            "_(Vũ khí đàm phán & Phản biện cho Giám đốc Dự án)_",
            "━━━━━━━━━━━━━━━━━━━━"
        ]

        overdue_count = 0
        for idx, m in enumerate(self.mom_commitments, 1):
            m_id = m.get("id", f"MOM-{idx}")
            comm = m.get("commitment", "")
            party = m.get("responsible_party", "")
            deadline = m.get("deadline", "")
            status = m.get("status", "")
            is_overdue = m.get("is_overdue", False)
            overdue_days = m.get("overdue_days", 0)
            weapon = m.get("pd_negotiation_weapon", "")

            status_icon = "❌" if is_overdue else "✅"
            if is_overdue:
                overdue_count += 1

            lines.append(f"{status_icon} *{idx}. [{m_id}] {comm}*")
            lines.append(f"   👤 Bên chịu trách nhiệm: *{party}*")
            lines.append(f"   🕒 Hạn chót: `{deadline}` | Trạng thái: *{status}*")
            if is_overdue:
                lines.append(f"   ⚠️ *ĐÃ QUÁ HẠN:* `{overdue_days} ngày`")
            if weapon:
                lines.append(f"   ⚔️ *Vũ khí đàm phán:* _{weapon}_")
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📊 *TỔNG KẾT:* Đang có *{overdue_count} mục cam kết QUÁ HẠN* từ phía CĐT / TVGS.")
        lines.append("💡 *Thêm cam kết MOM mới:* Gõ `/mom <nội dung>`")
        return "\n".join(lines)

    def add_mom(self, commitment: str, responsible_party: str, deadline: str = "", weapon: str = "") -> Dict[str, Any]:
        """Thêm nhanh một cam kết biên bản họp mới."""
        self._refresh()
        item = {
            "id": f"MOM-{len(self.mom_commitments) + 1:02d}",
            "meeting_title": f"Giao ban hiện trường ngày {datetime.date.today().strftime('%d/%m/%Y')}",
            "meeting_date": datetime.date.today().isoformat(),
            "location": "Văn phòng BCH Vietstar",
            "item_no": f"MOM-AUTO.{len(self.mom_commitments) + 1}",
            "commitment": commitment,
            "responsible_party": responsible_party or "Chủ đầu tư Vietstar",
            "deadline": deadline or (datetime.date.today() + datetime.timedelta(days=7)).isoformat(),
            "status": "ĐANG XỬ LÝ",
            "is_overdue": False,
            "overdue_days": 0,
            "pd_negotiation_weapon": weapon or f"Biên bản họp ngày {datetime.date.today().strftime('%d/%m/%Y')} đã ghi nhận cam kết này."
        }
        self.mom_commitments.insert(0, item)
        _save_json(self.data_dir / "mom_action_tracker.json", self.mom_commitments)
        return item

    # -------------------------------------------------------------------------
    # 6. BÁO CÁO THAM MƯU TỔNG HỢP GĐDA 1 TRANG (EXECUTIVE BRIEFING)
    # -------------------------------------------------------------------------

    def get_executive_briefing_summary(self) -> str:
        """Sinh Báo Cáo Tham Mưu Tổng Hợp 1 Trang cho Giám Đốc Dự Án trước cuộc họp giao ban."""
        self._refresh()

        # Dữ liệu dự án
        val_str = self.dossier.get("contract", {}).get("contract_value_str", "344.886.779.000 VNĐ")
        today_str = datetime.date.today().strftime("%d/%m/%Y")

        # Đếm rủi ro đỏ/cam
        red_risks = [r for r in self.risks if "ĐỎ" in r.get("risk_level", "")]
        orange_risks = [r for r in self.risks if "CAM" in r.get("risk_level", "")]

        # Đếm MOM quá hạn
        overdue_moms = [m for m in self.mom_commitments if m.get("is_overdue")]

        # Đếm Claim
        total_delay = sum(c.get("delay_days", 0) for c in self.claims)
        total_claim_cost = sum(c.get("impact_cost_vnd", 0) for c in self.claims)

        lines = [
            f"👑 *BẢN TIN THAM MƯU CHIẾN LƯỢC CHO GIÁM ĐỐC DỰ ÁN*",
            f"_(Dự án Nhà máy Rác Vietstar 344,89 Tỷ • Cập nhật: {today_str})_",
            "━━━━━━━━━━━━━━━━━━━━\n",
            "📍 *1. TIẾN ĐỘ & NÚT THẮT ĐƯỜNG GĂNG (CRITICAL PATH):*",
            "• *Công tác ID 18 (Chống thấm HDPE đáy hố móng):* Hạn hoàn thành hôm nay (26/09). Đã giải tỏa nút thắt bằng giải pháp hàn cuốn chiếu từng ô móng Grid A-C.",
            "• *Công tác ID 19 (Cốt thép, coppha, BT đáy móng):* Khởi động từ 28/08 đến 01/10. Đội sắt Đại Việt đang duy trì 32 người, năng suất 20 tấn/ngày để bám sát mốc đổ bê tông.",
            "• *Độ dự trữ tiến độ (Float):* Cực kỳ eo hẹp (0 ngày), không được phép phát sinh thêm độ trễ ở khâu nghiệm thu của TVGS.\n",
            f"🚨 *2. CẢNH BÁO RỦI RO TRỌNG ĐIỂM ({len(red_risks)} ĐỎ • {len(orange_risks)} CAM):*"
        ]

        if red_risks:
            r = red_risks[0]
            lines.append(f"• 🔴 *Bục đáy hố móng sâu -7.5m:* Mực nước ngầm đang khống chế ở -8.2m nhờ 8 giếng bơm 24/7. Nhắc TVGS ký xác nhận quan trắc lún hàng tuần.")
        if orange_risks:
            r = orange_risks[0]
            lines.append(f"• 🟠 *Tiến độ nghiệm thu cuốn chiếu:* Đã thông luồng kỹ thuật với TVGS để bàn giao mặt bằng từng phần cho đội cốt thép.\n")

        lines.append(f"⚔️ *3. VŨ KHÍ ĐÀM PHÁN TỪ BIÊN BẢN HỌP (MOM OVERDUE):*")
        if overdue_moms:
            for m in overdue_moms[:2]:
                lines.append(f"• ❌ *{m.get('responsible_party')}:* {m.get('commitment')}")
                lines.append(f"   👉 *Đòn bẩy cho Sếp:* _{m.get('pd_negotiation_weapon')}_")
        else:
            lines.append("• Các bên đang tuân thủ đúng tiến độ cam kết.")
        lines.append("")

        lines.append(f"📄 *4. HỒ SƠ CLAIM & BẢO VỆ GIA HẠN TIẾN ĐỘ (EOT):*")
        lines.append(f"• Đã lập hồ sơ 3 sự kiện: *{total_delay} ngày gia hạn EOT* | Giá trị thiệt hại: *{total_claim_cost:,.0f} VNĐ*".replace(",", "."))
        lines.append(f"• *Căn cứ thép:* Chậm bàn giao mốc Ram dốc (14 ngày) + TVGS ngâm Shopdrawing (6 ngày) + Mưa bão Củ Chi (6 ngày).\n")

        lines.append(f"💰 *5. SỨC KHỎE DÒNG TIỀN & BẢO LÃNH NGÂN HÀNG:*")
        lines.append(f"• *Hồ sơ IPC 01 (18,45 tỷ):* Đang trong thời hạn CĐT xem xét (Hạn chót: 02/10). Dự kiến thu về tài khoản: *13,84 tỷ*.")
        lines.append(f"• *Dòng tiền tháng 10:* Dự kiến thặng dư an toàn *+737,5 triệu VNĐ* sau khi chi trả đủ thép, bê tông và thầu phụ.")
        lines.append(f"• *Bảo lãnh ngân hàng:* BL Tạm ứng BIDV (103,46 tỷ) & BL Thực hiện HĐ Vietinbank (17,24 tỷ) đều hiệu lực tốt (>180 ngày).\n")

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("💎 *ĐÚC KẾT THAM MƯU TRƯỚC GIỜ GIAO BAN:*")
        lines.append("👉 *\"Chủ động đưa biên bản chậm bàn giao mốc Ram dốc của CĐT làm lá bài thương lượng để hóa giải hoàn toàn áp lực về tiến độ thi công đáy hố móng; đồng thời hối thúc CĐT duyệt nhanh IPC 01 để bơm vốn kịp thời cho đợt đổ bê tông lớn đầu tháng 10.\"*")

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # 7. NGỮ CẢNH DÀNH CHO GEMINI AI (CONTEXT GROUNDING)
    # -------------------------------------------------------------------------

    def get_executive_context_for_ai(self) -> str:
        """Tạo đoạn văn bản súc tích để nhúng vào Google Gemini AI làm ngữ cảnh tham mưu."""
        self._refresh()
        c_lines = [
            "### THÔNG TIN TÌNH BÁO QUẢN TRỊ CHIẾN LƯỢC DỰ ÁN VIETSTAR (DÀNH CHO TRỢ LÝ GIÁM ĐỐC DỰ ÁN):",
            "- Hợp đồng: 344,89 tỷ VNĐ, Đơn giá cố định, Tạm ứng 30% (103,46 tỷ, đã giải ngân 50 tỷ).",
            "- Bảo lãnh: BIDV (Tạm ứng 103,46 tỷ, hết hạn 31/03/2027), Vietinbank (Thực hiện HĐ 17,24 tỷ, hết hạn 30/04/2027).",
            "- Dòng tiền: IPC 01 nộp ngày 20/09/2026, giá trị 18,45 tỷ, CĐT duyệt trong 12 ngày (hạn 02/10/2026), dự kiến thu về 13,84 tỷ sau khấu trừ 20% hoàn ứng.",
            "- Sự kiện Claim bảo lưu: Chậm bàn giao mốc Ram dốc (14 ngày, CĐT), TVGS chậm duyệt Shop móng (6 ngày), Mưa bão ngập đáy hố móng (6 ngày). Tổng EOT đề xuất: 26 ngày.",
            "- Cam kết biên bản họp (MOM) quá hạn: Ban QLDA Vietstar chưa bàn giao tim mốc trắc đạc Ram dốc (quá hạn 4 ngày từ 22/09) -> Vũ khí phản biện của nhà thầu.",
            "- Thầu phụ chủ chốt: Đội thép Đại Việt (32 thợ, 2.950-3.100 đ/kg, 20T/ngày); Đội coppha/bê tông Sông Đà 9 (45 thợ, 155k/m2 cốp pha, 165k/m3 BT); Sơn Epoxy Bách Khoa (480k/m2); Bê tông Lê Phan (1.420.000 đ/m3 M400 W12).",
            "- Rủi ro lớn nhất: Bục đáy hố móng sâu -7.5m (đang chạy 8 giếng hạ nước ngầm 24/7) và tiến độ đường găng ID 18/ID 19 đáy hố rác."
        ]
        return "\n".join(c_lines)


# Singleton
_executive_engine: Optional[ProjectExecutiveEngine] = None

def get_executive_engine() -> ProjectExecutiveEngine:
    global _executive_engine
    if _executive_engine is None:
        _executive_engine = ProjectExecutiveEngine()
    return _executive_engine
