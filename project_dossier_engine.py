# -*- coding: utf-8 -*-
"""
project_dossier_engine.py - Não Bộ Bóc Tách & Nạp Dữ Liệu Công Trình cho Trợ Lý Su Su
=====================================================================================
Chức năng:
1. Đọc & Phân tách Hợp đồng thi công (PDF):
   - Giá trị hợp đồng, hình thức giá (Trọn gói / Đơn giá cố định / Điều chỉnh)
   - Thời gian thi công, ngày bàn giao mặt bằng, ngày hoàn thành
   - Điều khoản Tạm ứng & Thu hồi tạm ứng (%)
   - Bảo lãnh thực hiện HĐ & Bảo lãnh bảo hành (%)
   - Thời hạn khiếu nại (Time-Bar) thông báo phát sinh & nộp hồ sơ chi tiết (28/42 ngày)
   - Điều khoản phạt chậm tiến độ (%/ngày, trần tối đa %)
   - Điều kiện nghiệm thu & thời hạn thanh toán khối lượng hoàn thành
2. Đọc & Phân tích Bảng khối lượng BOQ (Excel .xlsx / .xls / PDF):
   - Tự động nhận diện cột (STT, Mã hiệu, Nội dung, ĐVT, Khối lượng, Đơn giá, Thành tiền)
   - Tổng giá trị BOQ & Số đầu việc
   - Top 15-20 hạng mục chiếm tỷ trọng chi phí cao nhất (Nguyên lý Pareto 80/20)
   - Phân nhóm cấu kiện trọng yếu (Cọc, Móng, Bê tông thân, Thép, Cốp pha, Hoàn thiện, MEP)
3. Đọc & Phân tích Tiến độ thi công (MS Project .mpp / Excel):
   - Mốc hoàn thành trọng điểm (Milestones)
   - Danh sách công việc thuộc Đường găng (Critical Path)
   - Công việc chậm trễ / nguy cơ trễ tiến độ (Negative slack)
4. Đóng gói Hồ sơ Dự án (Project Dossier) & Nạp vào Ngữ cảnh Não bộ Trợ lý Su Su:
   - Xuất tóm tắt hồ sơ dự án ra JSON
   - Sinh đoạn văn ngữ cảnh (Context Grounding) để nhúng vào Google Gemini AI
"""

from __future__ import annotations

import os
import sys
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _clean_text(text: str) -> str:
    """Chuẩn hóa khoảng trắng và dòng văn bản."""
    if not text:
        return ""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    result = "\n".join(lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def _parse_currency_vietnamese(val_str: str) -> Optional[float]:
    """Chuyển chuỗi tiền tệ tiếng Việt sang số float (VND)."""
    if not val_str:
        return None
    cleaned = re.sub(r"[^\d,\.]", "", str(val_str))
    if not cleaned:
        return None
    # Nếu có cả dấu chấm và phẩy
    if "." in cleaned and "," in cleaned:
        if cleaned.rfind(".") > cleaned.rfind(","):  # Kiểu Anh 1,000,000.50
            cleaned = cleaned.replace(",", "")
        else:  # Kiểu Việt 1.000.000,50
            cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):  # 1.000.000
            cleaned = cleaned.replace(".", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):  # 1,000,000
            cleaned = cleaned.replace(",", "")
        else:
            cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


# =============================================================================
# 1. PHÂN TÁCH HỢP ĐỒNG (PDF & WORD .DOCX)
# =============================================================================

def parse_contract_document(contract_path: str | Path) -> Dict[str, Any]:
    """Bóc tách các điều khoản cốt tử từ file Hợp đồng (PDF hoặc Word .docx)."""
    path = Path(contract_path)
    if not path.is_file():
        raise FileNotFoundError(f"Khong tim thay file hop dong: {path}")

    ext = path.suffix.lower()
    full_text = ""
    total_pages = 0
    file_type = "pdf" if ext == ".pdf" else "docx"

    if ext in [".docx", ".doc"]:
        file_type = "docx"
        try:
            import docx
            doc = docx.Document(str(path))
            p_texts = [p.text for p in doc.paragraphs if p.text.strip()]
            for t in doc.tables:
                for row in t.rows:
                    row_str = " | ".join([c.text.strip() for c in row.cells if c.text.strip()])
                    if row_str:
                        p_texts.append(row_str)
            full_text = "\n".join(p_texts)
            total_pages = max(1, len(doc.paragraphs) // 25)
        except Exception as e:
            full_text = f"[Loi doc file Word: {e}]"
    else:
        # File PDF
        file_type = "pdf"
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            total_pages = len(reader.pages)
            pages_text = []
            for idx, page in enumerate(reader.pages):
                t = page.extract_text() or ""
                if t.strip():
                    pages_text.append(f"--- TRANG {idx + 1} ---\n{t}")
            full_text = "\n\n".join(pages_text)
        except Exception as e:
            full_text = f"[Loi doc PDF bang pypdf: {e}]"

    contract_info: Dict[str, Any] = {
        "file_type": file_type,
        "file_name": path.name,
        "file_size_kb": round(path.stat().st_size / 1024, 1),
        "total_pages": total_pages,
        "is_scanned_pdf": False,
        "auxiliary_file": "",
        "note": "",
        "project_name": "",
        "package_name": "",
        "employer": "",       # Chủ đầu tư / Bên giao thầu
        "contractor": "",     # Nhà thầu / Bên nhận thầu
        "contract_value": None,
        "contract_value_str": "",
        "price_type": "Chưa xác định",  # Trọn gói / Đơn giá cố định / Đơn giá điều chỉnh
        "duration_days": None,
        "start_date": "",
        "end_date": "",
        "time_bars": [],      # Thời hạn khiếu nại (28 ngày, 42 ngày, v.v.)
        "advance_payment": "",# Tạm ứng
        "performance_bond": "",# Bảo lãnh thực hiện HĐ
        "warranty": "",       # Bảo hành
        "delay_penalty": "",  # Phạt chậm tiến độ
        "payment_terms": "",  # Điều khoản thanh toán
        "key_clauses": []     # Các trích đoạn điều khoản quan trọng
    }

    # Cơ chế Tự động Tìm file Word phụ trợ nếu file PDF là bản scan ảnh đóng dấu
    if file_type == "pdf" and len(full_text.strip()) < 50:
        contract_info["is_scanned_pdf"] = True
        docx_candidates = list(path.parent.glob("*.docx")) + list(path.parent.parent.glob("**/*.docx"))
        target_docx = None
        for c in docx_candidates:
            if c.name.startswith("~$"):
                continue
            c_low = c.name.lower()
            if any(k in c_low for k in ["hợp đồng", "hd", "hop dong", "contract"]):
                target_docx = c
                break
        if not target_docx and docx_candidates:
            valid_c = [c for c in docx_candidates if not c.name.startswith("~$")]
            if valid_c:
                target_docx = max(valid_c, key=lambda x: x.stat().st_size)

        if target_docx:
            try:
                import docx
                doc = docx.Document(str(target_docx))
                aux_texts = [p.text for p in doc.paragraphs if p.text.strip()]
                for t in doc.tables:
                    for row in t.rows:
                        row_str = " | ".join([c.text.strip() for c in row.cells if c.text.strip()])
                        if row_str:
                            aux_texts.append(row_str)
                aux_text = "\n".join(aux_texts)
                if len(aux_text.strip()) > 100:
                    full_text = aux_text
                    contract_info["auxiliary_file"] = target_docx.name
                    contract_info["note"] = f"File PDF là bản scan ảnh. Đã tự động đối chiếu điều khoản từ file Word: {target_docx.name}"
            except Exception:
                pass

        if not contract_info.get("auxiliary_file"):
            contract_info["note"] = "File PDF là bản scan ảnh đóng dấu đỏ (chưa OCR text layer). Bạn có thể nạp trực tiếp file Word (.docx) của hợp đồng để Su Su bóc tách từng điều khoản."

    if not full_text or full_text.startswith("[Loi doc"):
        return contract_info

    # 1. Tên dự án & Tên gói thầu
    m_proj = re.search(r"(?:Dự\s*án|Du\s*an|Công\s*trình|Cong\s*trinh)\s*[:：]\s*([^\n\r,;]+)", full_text, re.IGNORECASE)
    if m_proj:
        contract_info["project_name"] = m_proj.group(1).strip()
    m_pkg = re.search(r"(?:Gói\s*thầu|Goi\s*thau)\s*[:：]\s*([^\n\r,;]+)", full_text, re.IGNORECASE)
    if m_pkg:
        contract_info["package_name"] = m_pkg.group(1).strip()

    # 2. Chủ đầu tư & Nhà thầu
    m_emp = re.search(r"(?:BÊN\s*A|BEN\s*A|BÊN\s*GIAO\s*THẦU|CHỦ\s*ĐẦU\s*TƯ|CHU\s*DAU\s*TU)\s*[:：\n]\s*([^\n\r]+)", full_text, re.IGNORECASE)
    if m_emp:
        contract_info["employer"] = m_emp.group(1).strip()
    m_con = re.search(r"(?:BÊN\s*B|BEN\s*B|BÊN\s*NHẬN\s*THẦU|NHÀ\s*THẦU|NHA\s*THAU)\s*[:：\n]\s*([^\n\r]+)", full_text, re.IGNORECASE)
    if m_con:
        contract_info["contractor"] = m_con.group(1).strip()

    # 3. Giá trị hợp đồng
    m_val = re.search(r"(?:Giá\s*trị\s*hợp\s*đồng|Gia\s*tri\s*hop\s*dong|Giá\s*hợp\s*đồng|Gia\s*hop\s*dong)\s*[:：]?\s*([0-9\.,]{6,20})\s*(?:đồng|dong|VND|VNĐ)", full_text, re.IGNORECASE)
    if m_val:
        contract_info["contract_value_str"] = m_val.group(1).strip() + " VNĐ"
        contract_info["contract_value"] = _parse_currency_vietnamese(m_val.group(1))

    # 4. Hình thức giá hợp đồng
    if re.search(r"trọn\s*gói|tron\s*goi", full_text, re.IGNORECASE):
        contract_info["price_type"] = "Hợp đồng trọn gói"
    elif re.search(r"đơn\s*giá\s*cố\s*định|don\s*gia\s*co\s*dinh", full_text, re.IGNORECASE):
        contract_info["price_type"] = "Hợp đồng theo đơn giá cố định"
    elif re.search(r"đơn\s*giá\s*điều\s*chỉnh|don\s*gia\s*dieu\s*chinh", full_text, re.IGNORECASE):
        contract_info["price_type"] = "Hợp đồng theo đơn giá điều chỉnh"
    elif re.search(r"theo\s*thời\s*gian|theo\s*thoi\s*gian", full_text, re.IGNORECASE):
        contract_info["price_type"] = "Hợp đồng theo thời gian"

    # 5. Thời gian thực hiện hợp đồng
    m_dur = re.search(r"(?:Thời\s*gian\s*thực\s*hiện|Thoi\s*gian\s*thuc\s*hien|Tiến\s*độ\s*thi\s*công|Tien\s*do\s*thi\s*cong)[^\n\r0-9]{0,35}([0-9]{1,5})\s*(?:ngày|ngay)", full_text, re.IGNORECASE)
    if m_dur:
        try:
            contract_info["duration_days"] = int(m_dur.group(1))
        except ValueError:
            pass

    # 6. Thời hạn khiếu nại (Time-Bar Claim) - CỰC KỲ QUAN TRỌNG
    timebar_matches = re.finditer(
        r"([^\n\.]*(?:thông\s*báo|thong\s*bao|khiếu\s*nại|khieu\s*nai|phát\s*sinh|phat\s*sinh|thời\s*hạn|thoi\s*han|claim)[^\n\.]*([0-9]{1,3})\s*(?:ngày|ngay)[^\n\.]*)",
        full_text, re.IGNORECASE
    )
    for m in timebar_matches:
        snip = m.group(1).strip()
        days_num = m.group(2).strip()
        if int(days_num) in [7, 14, 21, 28, 42, 56, 84]:
            contract_info["time_bars"].append({
                "days": int(days_num),
                "clause_text": _clean_text(snip)
            })

    # Nếu không bắt được regex hẹp, quét các điều khoản 28 ngày hoặc 42 ngày
    if not contract_info["time_bars"]:
        m_28 = re.search(r"([^\r\n]*28\s*(?:ngày|ngay)[^\r\n]*)", full_text, re.IGNORECASE)
        if m_28:
            contract_info["time_bars"].append({"days": 28, "clause_text": _clean_text(m_28.group(1))})
        m_42 = re.search(r"([^\r\n]*42\s*(?:ngày|ngay)[^\r\n]*)", full_text, re.IGNORECASE)
        if m_42:
            contract_info["time_bars"].append({"days": 42, "clause_text": _clean_text(m_42.group(1))})

    # 7. Tạm ứng & Thu hồi tạm ứng
    m_adv = re.search(r"([^\r\n]*(?:tạm\s*ứng|tam\s*ung|thu\s*hồi\s*tạm\s*ứng|thu\s*hoi\s*tam\s*ung)[^\r\n]*(?:[0-9]{1,2}%|[0-9\.,]{6,15}\s*(?:đồng|dong|VND|VNĐ))[^\r\n]*)", full_text, re.IGNORECASE)
    if m_adv:
        contract_info["advance_payment"] = _clean_text(m_adv.group(1))

    # 8. Phạt chậm tiến độ
    m_pen = re.search(r"([^\r\n]*(?:phạt|phat|vi\s*phạm\s*tiến\s*độ|vi\s*pham\s*tien\s*do)[^\r\n]*(?:%|đồng|dong|VND|VNĐ)[^\r\n]*)", full_text, re.IGNORECASE)
    if m_pen:
        contract_info["delay_penalty"] = _clean_text(m_pen.group(1))

    # 9. Bảo hành & Bảo lãnh
    m_war = re.search(r"([^\r\n]*(?:bảo\s*hành|bao\s*hanh|bảo\s*lãnh\s*thực\s*hiện|bao\s*lanh)[^\r\n]*(?:%|[0-9]{1,2}\s*(?:tháng|thang))[^\r\n]*)", full_text, re.IGNORECASE)
    if m_war:
        contract_info["warranty"] = _clean_text(m_war.group(1))

    # 10. Điều kiện thanh toán
    m_pay = re.search(r"([^\r\n]*(?:thanh\s*toán|thanh\s*toan|nghiệm\s*thu|nghiem\s*thu)[^\r\n]*(?:hồ\s*sơ|trong\s*vòng|thời\s*hạn)[^\r\n]*[0-9]{1,2}\s*(?:ngày|ngay)[^\r\n]*)", full_text, re.IGNORECASE)
    if m_pay:
        contract_info["payment_terms"] = _clean_text(m_pay.group(1))

    # Trích xuất 5-8 điều khoản chính làm bối cảnh RAG
    sections = re.findall(r"(?:Điều\s*[0-9]{1,2}|MỤC\s*[0-9]{1,2})[^\n\r]*\n(?:[^\n\r]+\n){1,10}", full_text, re.IGNORECASE)
    contract_info["key_clauses"] = [_clean_text(sec) for sec in sections[:8] if len(sec.strip()) > 30]

    return contract_info


def parse_contract_pdf(pdf_path: str | Path) -> Dict[str, Any]:
    """Alias tương thích ngược cho parse_contract_document."""
    return parse_contract_document(pdf_path)


# =============================================================================
# 2. PHÂN TÁCH BẢNG KHỐI LƯỢNG BOQ (EXCEL / PDF)
# =============================================================================

def extract_grand_total_summary(wb) -> Dict[str, Any]:
    """
    Quét tìm Hàng TỔNG CỘNG (Grand Total) trong các sheet Excel (ưu tiên sheet TOTAL, Tổng Hợp, Summary).
    Dân QS luôn căn cứ vào Hàng Tổng Cộng (trước thuế, thuế VAT, sau thuế) để xác định Giá Trị Hợp Đồng.
    """
    summary = {
        "found": False,
        "sheet_name": "",
        "total_without_vat": None,
        "total_with_vat": None,
        "vat_amount": None,
        "grand_total": None,
        "raw_label": ""
    }

    # Ưu tiên các sheet tổng hợp trước
    priority_sheets = []
    other_sheets = []
    for s in wb.sheetnames:
        sl = s.lower()
        if any(k in sl for k in ["total", "tổng hợp", "tong hop", "summary", "bảng giá", "hợp đồng"]):
            priority_sheets.append(s)
        else:
            other_sheets.append(s)

    ordered_sheets = priority_sheets + other_sheets

    for sname in ordered_sheets:
        try:
            ws = wb[sname]
            rows = list(ws.iter_rows(values_only=True))
        except Exception:
            continue

        for r_idx, row in enumerate(rows):
            if not row:
                continue
            for c_idx, cell in enumerate(row):
                if cell is None or not isinstance(cell, str):
                    continue
                cl = cell.strip().lower()

                # 1. Hàng Tổng cộng bao gồm VAT
                if any(k in cl for k in ["tổng cộng bao gồm vat", "tổng cộng có vat", "tổng cộng sau thuế", "bao gồm vat", "đã bao gồm vat", "sau thuế"]):
                    for val in row[c_idx + 1:]:
                        if isinstance(val, (int, float)) and val > 1000:
                            summary["total_with_vat"] = float(val)
                            summary["found"] = True
                            summary["sheet_name"] = sname
                            summary["raw_label"] = cell.strip()
                            break
                # 2. Hàng Tổng cộng chưa bao gồm VAT
                elif any(k in cl for k in ["tổng cộng chưa bao gồm vat", "tổng cộng trước thuế", "chưa bao gồm vat", "trước thuế"]):
                    for val in row[c_idx + 1:]:
                        if isinstance(val, (int, float)) and val > 1000:
                            summary["total_without_vat"] = float(val)
                            summary["found"] = True
                            summary["sheet_name"] = sname
                            break
                # 3. Hàng Thuế VAT
                elif any(k in cl for k in ["thuế vat", "thue vat", "vat 8%", "vat 10%", "vat:"]):
                    for val in row[c_idx + 1:]:
                        if isinstance(val, (int, float)) and val > 1000:
                            summary["vat_amount"] = float(val)
                            break
                # 4. Hàng Tổng cộng chung
                elif cl in ["tổng cộng", "tong cong", "cộng", "grand total", "total", "tổng giá trị"]:
                    for val in row[c_idx + 1:]:
                        if isinstance(val, (int, float)) and val > 1000:
                            if summary["grand_total"] is None:
                                summary["grand_total"] = float(val)
                                summary["found"] = True
                                summary["sheet_name"] = sname
                            break

        if summary["total_with_vat"] or summary["total_without_vat"]:
            break

    if summary["total_with_vat"]:
        summary["grand_total"] = summary["total_with_vat"]
    elif summary["total_without_vat"]:
        summary["grand_total"] = summary["total_without_vat"]

    return summary


def parse_boq_excel(excel_path: str | Path) -> Dict[str, Any]:
    """Bóc tách danh mục công việc, khối lượng và đơn giá từ BOQ Excel (Đa Sheet Thông Minh & Trích Xuất Hàng Tổng Cộng)."""
    path = Path(excel_path)
    if not path.is_file():
        raise FileNotFoundError(f"Khong tim thay file BOQ: {path}")

    boq_info: Dict[str, Any] = {
        "file_name": path.name,
        "file_size_kb": round(path.stat().st_size / 1024, 1),
        "sheet_name": "",
        "total_items": 0,
        "total_amount": 0.0,
        "total_amount_str": "0 VNĐ",
        "total_without_vat": None,
        "total_with_vat": None,
        "vat_amount": None,
        "top_cost_items": [],       # Top 15-20 hạng mục chiếm chi phí cao nhất (Pareto 80/20)
        "work_categories": {},      # Phân loại khối lượng theo cấu kiện
        "anomalies": []             # Cảnh báo bất thường (đơn giá 0, khối lượng âm...)
    }

    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(path), data_only=True)
    except Exception as e:
        boq_info["anomalies"].append(f"Lỗi đọc file Excel bằng openpyxl: {e}")
        return boq_info

    # 1. Trích xuất Hàng Tổng Cộng (Grand Total) - Cốt lõi của Giá trị Hợp đồng
    grand_summary = extract_grand_total_summary(wb)

    # 2. Lọc các sheet ứng viên (bỏ qua sheet ghi chú, note, hướng dẫn, bìa, làm rõ, dmvt)
    ignored_kw = ["ghi chú", "ghi chu", "note", "notes", "hướng dẫn", "huong dan", "bìa", "cover", "làm rõ", "lam ro", "dmvt"]
    candidate_sheets = [s for s in wb.sheetnames if not any(k in s.lower() for k in ignored_kw)]
    if not candidate_sheets:
        candidate_sheets = list(wb.sheetnames)

    sheet_candidates_data = []

    for sname in candidate_sheets:
        try:
            ws = wb[sname]
            rows = list(ws.iter_rows(values_only=True))
        except Exception:
            continue
        if not rows:
            continue

        # Tìm Table Header Row
        hdr_idx = -1
        col_map: Dict[str, int] = {}
        for r_idx, row in enumerate(rows[:35]):
            row_strs = [str(c).strip().lower() if c is not None else "" for c in row]
            non_empty = [s for s in row_strs if s]
            if len(non_empty) < 3:
                continue

            # Bỏ qua nếu là dòng tiêu đề dự án hoặc tên báo cáo chung chung
            if any(any(k in s for k in ["bảng khối lượng", "bảng tổng hợp", "dự án:", "địa điểm:"]) for s in row_strs):
                if not any(s in ["stt", "tt", "no", "no."] for s in row_strs):
                    continue

            m_name = next((i for i, s in enumerate(row_strs) if any(k in s for k in ["nội dung", "tên công tác", "tên công việc", "mô tả", "hạng mục", "diễn giải"])), None)
            m_qty = next((i for i, s in enumerate(row_strs) if any(k in s for k in ["khối lượng", "kl", "số lượng", "qty"])), None)
            m_total = next((i for i, s in enumerate(row_strs) if any(k in s for k in ["thành tiền", "thanh tien", "tổng cộng", "amount"])), None)
            m_price = next((i for i, s in enumerate(row_strs) if any(k in s for k in ["đơn giá", "don gia", "unit price"])), None)
            m_unit = next((i for i, s in enumerate(row_strs) if any(k in s for k in ["đơn vị", "đvt", "unit"])), None)
            m_code = next((i for i, s in enumerate(row_strs) if any(k in s for k in ["mã hiệu", "mã định mức", "mã số", "code", "stt", "tt"])), None)

            if m_name is not None and (m_qty is not None or m_total is not None or m_price is not None):
                hdr_idx = r_idx
                col_map = {
                    "name": m_name,
                    "qty": m_qty,
                    "price": m_price,
                    "total": m_total,
                    "unit": m_unit,
                    "code": m_code
                }
                break

        if hdr_idx < 0:
            continue

        valid_cols = [v for v in col_map.values() if v is not None]
        sheet_items = []
        for r in rows[hdr_idx + 1:]:
            if not r or len(r) <= max(valid_cols, default=0):
                continue

            name_val = str(r[col_map["name"]]).strip() if col_map.get("name") is not None and r[col_map["name"]] is not None else ""
            if not name_val or name_val.lower() in ["none", "vat", "thuế"]:
                continue

            # Lọc bỏ dòng Subtotal / Tổng con hoặc Tiêu đề nhóm để tránh cộng trùng lặp
            nl = name_val.lower()
            if any(nl.startswith(k) for k in [
                "tổng cộng:", "tổng:", "cộng:", "subtotal", "grand total",
                "tổng cộng (", "tổng cộng "
            ]) or nl in ["tổng cộng", "cộng", "tổng"]:
                continue

            code_val = str(r[col_map["code"]]).strip() if col_map.get("code") is not None and r[col_map["code"]] is not None else ""
            unit_val = str(r[col_map["unit"]]).strip() if col_map.get("unit") is not None and r[col_map["unit"]] is not None else ""

            qty_val = 0.0
            if col_map.get("qty") is not None and r[col_map["qty"]] is not None:
                try:
                    qty_val = float(r[col_map["qty"]])
                except (ValueError, TypeError):
                    qty_val = 0.0

            # Bỏ qua nếu dòng không có đơn vị tính và khối lượng = 0 (dòng tiêu đề nhóm / tổng gộp)
            if not unit_val and qty_val == 0:
                continue

            price_val = 0.0
            if col_map.get("price") is not None and r[col_map["price"]] is not None:
                try:
                    price_val = float(r[col_map["price"]])
                except (ValueError, TypeError):
                    price_val = 0.0

            amount_val = 0.0
            if col_map.get("total") is not None and r[col_map["total"]] is not None:
                try:
                    amount_val = float(r[col_map["total"]])
                except (ValueError, TypeError):
                    amount_val = qty_val * price_val
            else:
                amount_val = qty_val * price_val

            if amount_val > 0 or qty_val > 0:
                sheet_items.append({
                    "code": code_val,
                    "name": name_val,
                    "unit": unit_val,
                    "quantity": qty_val,
                    "unit_price": price_val,
                    "amount": amount_val
                })

        if sheet_items:
            sheet_sum = sum(it["amount"] for it in sheet_items)
            sheet_candidates_data.append({
                "sheet_name": sname,
                "items": sheet_items,
                "total_amount": sheet_sum
            })

    if not sheet_candidates_data and not grand_summary["found"]:
        return boq_info

    # Lựa chọn sheet chi tiết tối ưu
    chosen_items = []
    if sheet_candidates_data:
        detail_sheets = [s for s in sheet_candidates_data if len(s["items"]) >= 15]
        if detail_sheets:
            selected_sheet = max(detail_sheets, key=lambda x: len(x["items"]))
            chosen_items = list(selected_sheet["items"])
            boq_info["sheet_name"] = selected_sheet["sheet_name"]

            for other in detail_sheets:
                if other["sheet_name"] != selected_sheet["sheet_name"]:
                    chosen_items.extend(other["items"])
                    boq_info["sheet_name"] += f" + {other['sheet_name']}"
        else:
            selected_sheet = max(sheet_candidates_data, key=lambda x: x["total_amount"])
            chosen_items = list(selected_sheet["items"])
            boq_info["sheet_name"] = selected_sheet["sheet_name"]

    items = chosen_items
    detail_sum = sum(it["amount"] for it in items)

    # Ưu tiên lấy Giá Trị Hợp Đồng từ Hàng Tổng Cộng (Grand Total)
    if grand_summary["found"] and grand_summary["grand_total"]:
        total_val = grand_summary["grand_total"]
        boq_info["total_with_vat"] = grand_summary["total_with_vat"]
        boq_info["total_without_vat"] = grand_summary["total_without_vat"]
        boq_info["vat_amount"] = grand_summary["vat_amount"]
        if grand_summary["total_with_vat"]:
            boq_info["total_amount_str"] = f"{total_val:,.0f} VNĐ".replace(",", ".")
        else:
            boq_info["total_amount_str"] = f"{total_val:,.0f} VNĐ".replace(",", ".")
    else:
        total_val = detail_sum
        boq_info["total_amount_str"] = f"{total_val:,.0f} VNĐ".replace(",", ".")

    boq_info["total_items"] = len(items)
    boq_info["total_amount"] = total_val

    # Sắp xếp Top 15-20 hạng mục có chi phí cao nhất (Pareto 80/20)
    base_calc = boq_info["total_without_vat"] if boq_info.get("total_without_vat") else total_val
    items_sorted = sorted(items, key=lambda x: x["amount"], reverse=True)
    for it in items_sorted[:20]:
        pct = (it["amount"] / base_calc * 100) if base_calc > 0 else 0
        boq_info["top_cost_items"].append({
            "name": it["name"],
            "unit": it["unit"],
            "quantity": it["quantity"],
            "unit_price": it["unit_price"],
            "amount": it["amount"],
            "amount_str": f"{it['amount']:,.0f} VNĐ".replace(",", "."),
            "pct_of_total": round(pct, 2)
        })

    # Phân loại nhóm công tác
    cat_rules = {
        "Cọc & Địa kỹ thuật": ["cọc", "khoan nhồi", "ép cọc", "đóng cọc", "tường vây", "barrette"],
        "Đất & Hố móng": ["đào đất", "đắp đất", "vận chuyển đất", "hố móng", "cừ larsen", "shoring"],
        "Bê tông & Vữa": ["bê tông", "btct", "vữa", "đổ bê tông", "xoa nền"],
        "Cốt thép": ["cốt thép", "thép hình", "thép tròn", "gia công thép", "bu lông"],
        "Ván khuôn (Cốp pha)": ["ván khuôn", "cốp pha", "cop pha", "giàn giáo"],
        "Kết cấu thép & Mái": ["kết cấu thép", "dầm thép", "xà gồ", "mái tole", "tấm lợp", "bông cách nhiệt"],
        "Xây & Trát": ["xây gạch", "trát tường", "láng nền", "ốp lát", "gạch"],
        "Chống thấm & Hoàn thiện": ["chống thấm", "màng hdpe", "sơn", "trần thạch cao", "cửa", "kính"],
        "Cơ điện (MEP)": ["mep", "điện", "cấp thoát nước", "hvac", "pccc", "ống luồn", "dây cáp"]
    }

    for cat_name, keywords in cat_rules.items():
        cat_amount = sum(it["amount"] for it in items if any(k in it["name"].lower() for k in keywords))
        if cat_amount > 0:
            boq_info["work_categories"][cat_name] = {
                "amount": cat_amount,
                "amount_str": f"{cat_amount:,.0f} VNĐ".replace(",", "."),
                "pct": round(cat_amount / total_val * 100, 1) if total_val > 0 else 0
            }

    return boq_info


# =============================================================================
# 3. PHÂN TÁCH TIẾN ĐỘ THI CÔNG (MS PROJECT / EXCEL)
# =============================================================================

def parse_schedule_mpp(mpp_path: str | Path) -> Dict[str, Any]:
    """Bóc tách mốc hoàn thành, đường găng và rủi ro trễ hạn từ MS Project .mpp."""
    path = Path(mpp_path)
    if not path.is_file():
        raise FileNotFoundError(f"Khong tim thay file MPP: {path}")

    sched_info: Dict[str, Any] = {
        "file_name": path.name,
        "file_size_kb": round(path.stat().st_size / 1024, 1),
        "total_tasks": 0,
        "project_start": "",
        "project_finish": "",
        "milestones": [],           # Các mốc hoàn thành quan trọng
        "critical_tasks": [],       # Công việc nằm trên đường găng (Critical Path)
        "delayed_tasks": [],        # Công việc trễ hạn so với baseline
        "overall_progress_pct": 0.0 # % Hoàn thành tổng thể
    }

    # Thử kết nối qua MS Project COM
    try:
        import win32com.client
        app = win32com.client.Dispatch("MSProject.Application")
        app.Visible = False
        app.FileOpen(str(path.resolve()))
        proj = app.ActiveProject

        sched_info["project_start"] = str(proj.ProjectStart)[:10]
        sched_info["project_finish"] = str(proj.ProjectFinish)[:10]
        
        all_tasks = []
        for t in proj.Tasks:
            if t is None:
                continue
            is_summary = getattr(t, "Summary", False)
            name = getattr(t, "Name", "")
            dur_days = getattr(t, "Duration", 0) / 480.0  # 480 phút = 1 ngày công
            pct = getattr(t, "PercentComplete", 0)
            is_milestone = getattr(t, "Milestone", False) or dur_days == 0
            is_critical = getattr(t, "Critical", False)
            start_d = str(getattr(t, "Start", ""))[:10]
            finish_d = str(getattr(t, "Finish", ""))[:10]
            slack = getattr(t, "TotalSlack", 0)

            t_dict = {
                "id": getattr(t, "ID", 0),
                "name": name,
                "start": start_d,
                "finish": finish_d,
                "duration_days": round(dur_days, 1),
                "pct_complete": pct,
                "is_milestone": is_milestone,
                "is_critical": is_critical,
                "slack": slack
            }
            all_tasks.append(t_dict)

            if is_milestone:
                sched_info["milestones"].append(t_dict)
            if is_critical and not is_summary:
                sched_info["critical_tasks"].append(t_dict)
            if slack is not None and slack < 0:
                sched_info["delayed_tasks"].append(t_dict)

        sched_info["total_tasks"] = len(all_tasks)
        if all_tasks:
            # Task ID 0 hoặc task tổng thể
            root_task = next((t for t in all_tasks if t["id"] in [0, 1]), all_tasks[0])
            sched_info["overall_progress_pct"] = root_task.get("pct_complete", 0.0)

        app.FileClose(0)
    except Exception as e:
        sched_info["delayed_tasks"].append({"error": f"Chưa đọc được trực tiếp COM MS Project ({e}). Vui lòng mở file hoặc xuất bảng Excel."})

    return sched_info


# =============================================================================
# 4. TỔNG HỢP HỒ SƠ DỰ ÁN & GROUNDING NGỮ CẢNH
# =============================================================================

def build_project_dossier(
    contract_path: Optional[str | Path] = None,
    boq_path: Optional[str | Path] = None,
    schedule_path: Optional[str | Path] = None,
    project_title: str = ""
) -> Dict[str, Any]:
    """Tổng hợp dữ liệu từ cả 3 nguồn thành một Hồ sơ Dự án đầy đủ (Project Dossier)."""
    dossier: Dict[str, Any] = {
        "title": project_title or "Dự án Hiện Hành",
        "created_at": "",
        "contract": {},
        "boq": {},
        "schedule": {},
        "executive_summary": ""
    }

    import datetime
    dossier["created_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Hợp đồng
    if contract_path and Path(contract_path).exists():
        try:
            dossier["contract"] = parse_contract_pdf(contract_path)
            if not project_title and dossier["contract"].get("project_name"):
                dossier["title"] = dossier["contract"]["project_name"]
        except Exception as e:
            dossier["contract"] = {"error": str(e)}

    # 2. BOQ
    if boq_path and Path(boq_path).exists():
        try:
            dossier["boq"] = parse_boq_excel(boq_path)
        except Exception as e:
            dossier["boq"] = {"error": str(e)}

    # 3. Tiến độ
    if schedule_path and Path(schedule_path).exists():
        try:
            dossier["schedule"] = parse_schedule_mpp(schedule_path)
        except Exception as e:
            dossier["schedule"] = {"error": str(e)}

    # 4. Tạo Bản Tóm Tắt Chiến Lược (Executive Summary)
    lines = []
    lines.append(f"📌 TÊN DỰ ÁN: {dossier['title']}")

    if dossier.get("contract") and not dossier["contract"].get("error"):
        c = dossier["contract"]
        if c.get("note"):
            lines.append(f"• Lưu ý pháp lý: {c['note']}")

        # Nếu Hợp đồng chưa có giá trị số tiền (để trống hoặc ghi theo phụ lục), tự động lấy từ Hàng TỔNG CỘNG của BOQ
        if not c.get("contract_value") and dossier.get("boq") and not dossier["boq"].get("error"):
            b_dat = dossier["boq"]
            if b_dat.get("total_with_vat"):
                c["contract_value"] = b_dat["total_with_vat"]
                c["contract_value_str"] = f"{b_dat['total_with_vat']:,.0f} VNĐ (Đã gồm 8% VAT - Trích xuất từ hàng Tổng Cộng BOQ)".replace(",", ".")
            elif b_dat.get("total_amount") and b_dat["total_amount"] > 0:
                c["contract_value"] = b_dat["total_amount"]
                c["contract_value_str"] = f"{b_dat['total_amount']:,.0f} VNĐ (Trích xuất từ hàng Tổng Cộng BOQ)".replace(",", ".")
            if b_dat.get("total_without_vat"):
                c["contract_value_before_vat"] = b_dat["total_without_vat"]

        c_val = c.get("contract_value_str")
        lines.append(f"• Giá trị HĐ: {c_val or 'Chưa rõ'} ({c.get('price_type', '')})")

        # Chi tiết trước thuế & thuế VAT từ hàng Tổng cộng BOQ
        if dossier.get("boq") and dossier["boq"].get("total_without_vat"):
            b_no = dossier["boq"]["total_without_vat"]
            b_vat = dossier["boq"].get("vat_amount")
            vat_str = f" | Thuế VAT 8%: {b_vat:,.0f} VNĐ".replace(",", ".") if b_vat else ""
            lines.append(f"  └─ Giá trị trước thuế: {b_no:,.0f} VNĐ{vat_str}".replace(",", "."))
            if c.get("advance_payment") and "30%" in c["advance_payment"]:
                adv_val = 0.3 * b_no
                lines.append(f"  └─ Tạm ứng 30% HĐ trước thuế: {adv_val:,.0f} VNĐ".replace(",", "."))

        dur_val = c.get("duration_days")
        dur_str = f"{dur_val} ngày" if dur_val else "Theo bảng tiến độ chi tiết (Phụ lục 05)"
        if dossier.get("schedule") and not dossier["schedule"].get("error"):
            s_data = dossier["schedule"]
            if s_data.get("project_start") and s_data.get("project_finish"):
                dur_str += f" ({s_data['project_start']} -> {s_data['project_finish']})"
        lines.append(f"• Thời gian thi công: {dur_str}")
        if c.get("time_bars"):
            tb_strs = [f"{tb['days']} ngày ({tb['clause_text'][:60]}...)" for tb in c["time_bars"]]
            lines.append(f"• THỜI HẠN KHIẾU NẠI (TIME-BAR): {'; '.join(tb_strs)}")
        if c.get("delay_penalty"):
            lines.append(f"• Phạt vi phạm tiến độ: {c['delay_penalty']}")
        if c.get("advance_payment"):
            lines.append(f"• Điều khoản tạm ứng: {c['advance_payment']}")

    if dossier.get("boq") and not dossier["boq"].get("error"):
        b = dossier["boq"]
        lines.append(f"• Bảng BOQ Chi tiết: {b.get('total_items', 0)} đầu việc thực tế")
        if b.get("top_cost_items"):
            top_names = [f"{it['name']} ({it['pct_of_total']}%)" for it in b["top_cost_items"][:5]]
            lines.append(f"• Top 5 hạng mục chi phí lớn nhất (Pareto 80/20): {'; '.join(top_names)}")

    if dossier.get("schedule") and not dossier["schedule"].get("error"):
        s = dossier["schedule"]
        lines.append(f"• Tiến độ tổng thể: {s.get('overall_progress_pct', 0)}% hoàn thành")
        if s.get("critical_tasks"):
            lines.append(f"• Số công việc trên Đường Găng (Critical Path): {len(s['critical_tasks'])} công việc")
        if s.get("milestones"):
            lines.append(f"• Số mốc hoàn thành (Milestones): {len(s['milestones'])} mốc")

    dossier["executive_summary"] = "\n".join(lines)
    return dossier


def format_dossier_prompt_context(dossier: Dict[str, Any]) -> str:
    """Tạo chuỗi ngữ cảnh nhúng thẳng vào System Prompt của Google Gemini AI."""
    if not dossier or not dossier.get("executive_summary"):
        return ""

    context_lines = [
        "\n=======================================================",
        "THÔNG TIN DỰ ÁN & HỒ SƠ CÔNG TRÌNH THỰC TẾ (GROUNDING CONTEXT)",
        "=======================================================",
        dossier.get("executive_summary", ""),
        ""
    ]

    # Chi tiết hợp đồng
    c = dossier.get("contract", {})
    if c and not c.get("error"):
        context_lines.append("--- ĐIỀU KHOẢN HỢP ĐỒNG CỐT TỬ ---")
        if c.get("time_bars"):
            context_lines.append("⚠️ CÁC MỐC THỜI HẠN KHIẾU NẠI (TIME-BAR):")
            for tb in c["time_bars"]:
                context_lines.append(f"  + {tb['days']} ngày: {tb['clause_text']}")
        if c.get("delay_penalty"):
            context_lines.append(f"⚠️ ĐIỀU KHOẢN PHẠT TIẾN ĐỘ: {c['delay_penalty']}")
        if c.get("payment_terms"):
            context_lines.append(f"ℹ️ ĐIỀU KIỆN THANH TOÁN: {c['payment_terms']}")
        if c.get("key_clauses"):
            context_lines.append("Trích đoạn điều khoản chính:")
            for kl in c["key_clauses"][:4]:
                context_lines.append(f"- {kl[:150]}...")

    # Chi tiết BOQ
    b = dossier.get("boq", {})
    if b and not b.get("error") and b.get("top_cost_items"):
        context_lines.append("\n--- HẠNG MỤC BOQ TRỌNG ĐIỂM (CẦN KIỂM SOÁT HAO HỤT) ---")
        for it in b["top_cost_items"][:8]:
            context_lines.append(f"- {it['name']}: {it['quantity']} {it['unit']} | Thành tiền: {it['amount_str']} ({it['pct_of_total']}%)")

    # Chi tiết Tiến độ
    s = dossier.get("schedule", {})
    if s and not s.get("error"):
        if s.get("critical_tasks"):
            context_lines.append("\n--- CÔNG VIỆC TRÊN ĐƯỜNG GĂNG (CRITICAL PATH) ---")
            for ct in s["critical_tasks"][:8]:
                context_lines.append(f"- [ID {ct.get('id')}] {ct.get('name')}: Bắt đầu {ct.get('start')} -> Xong {ct.get('finish')} ({ct.get('pct_complete')}%)")

    context_lines.append("=======================================================\n")
    return "\n".join(context_lines)


def get_default_dossier_path() -> Path:
    """Trả về đường dẫn mặc định của file hồ sơ dự án."""
    _this_file = Path(__file__).resolve()
    pkg_root = _this_file.parents[3] if len(_this_file.parents) > 3 else _this_file.parent
    candidates = [
        _this_file.parent / "Data" / "current_project_dossier.json",
        _this_file.parent / "current_project_dossier.json",
        pkg_root.parent / "Data" / "current_project_dossier.json",
        pkg_root / "Data" / "current_project_dossier.json",
        Path("/app/Data/current_project_dossier.json"),
        Path("/app/current_project_dossier.json"),
        Path(r"C:\QS_Hien\Data\current_project_dossier.json"),
    ]
    for c in candidates:
        if c.is_file():
            return c

    data_dir = pkg_root.parent / "Data"
    if not data_dir.exists():
        data_dir = pkg_root / "Data"
    if not data_dir.exists():
        data_dir = _this_file.parent / "Data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "current_project_dossier.json"


def save_project_dossier(dossier: Dict[str, Any], file_path: Optional[str | Path] = None) -> Path:
    """Lưu hồ sơ dự án ra tệp JSON."""
    target_path = Path(file_path) if file_path else get_default_dossier_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(dossier, f, ensure_ascii=False, indent=2)
    return target_path


def load_project_dossier(file_path: Optional[str | Path] = None) -> Optional[Dict[str, Any]]:
    """Đọc hồ sơ dự án hiện hành từ tệp JSON."""
    target_path = Path(file_path) if file_path else get_default_dossier_path()
    if not target_path.is_file():
        _this_file = Path(__file__).resolve()
        pkg_root = _this_file.parents[3] if len(_this_file.parents) > 3 else _this_file.parent
        candidates = [
            _this_file.parent / "Data" / "current_project_dossier.json",
            _this_file.parent / "current_project_dossier.json",
            pkg_root.parent / "Data" / "current_project_dossier.json",
            pkg_root / "Data" / "current_project_dossier.json",
            Path("/app/Data/current_project_dossier.json"),
            Path("/app/current_project_dossier.json"),
            Path(r"C:\QS_Hien\Data\current_project_dossier.json"),
        ]
        for c in candidates:
            if c.is_file():
                target_path = c
                break
        else:
            return None

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

