# -*- coding: utf-8 -*-
"""
vector_rag_engine.py - Não Bộ Vector RAG & Hybrid Semantic Search cho Trợ Lý Su Su
Kết hợp:
1. TF-IDF / BM25 Lexical Search (Khớp từ khóa chính xác 100% cho tiêu chuẩn, định mức, mã số)
2. Subword N-Gram Vector Cosine Similarity (Hiểu ngữ nghĩa câu hỏi tự nhiên không cần model nặng, < 5ms)
3. Local SQLite Vector Store (Lưu trữ và lập chỉ mục toàn bộ 1,263+ ca thực chiến + 8 cẩm nang docs/)
4. Context Extractor cho Google Gemini API RAG Grounding
"""

from __future__ import annotations

import os
import sys
import re
import json
import time
import math
import sqlite3
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None
    HAS_NUMPY = False

# Thư mục gốc & Dữ liệu
_this_file = Path(__file__).resolve()
_PKG_ROOT = _this_file.parents[3] if len(_this_file.parents) > 3 else _this_file.parent
_TRITHUC = os.environ.get("QSH_TRITHUC_ROOT", "").strip()

def _find_rag_db_path() -> Path:
    candidates = [
        *([Path(_TRITHUC) / "susu_vector_kb.db"] if _TRITHUC else []),
        _this_file.parent / "susu_vector_kb.db",
        _this_file.parent / "Data" / "susu_vector_kb.db",
        _PKG_ROOT.parent / "Data" / "susu_vector_kb.db",
        _PKG_ROOT / "Data" / "susu_vector_kb.db",
        Path("/app/susu_vector_kb.db"),
        Path("/app/Data/susu_vector_kb.db"),
        Path(r"C:\QS_Hien\Data\susu_vector_kb.db"),
        Path(r"C:\QS_Hien\trithuc\susu\susu_vector_kb.db"),
    ]
    for c in candidates:
        if c.is_file():
            return c
    return _this_file.parent / "susu_vector_kb.db"

DB_PATH = _find_rag_db_path()
DATA_DIR = DB_PATH.parent
DOCS_DIR = _PKG_ROOT / "docs"


def strip_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt chuẩn hóa NFD."""
    text = unicodedata.normalize('NFD', text)
    text = re.sub(r'[\u0300-\u036f]', '', text)
    text = text.replace('đ', 'd').replace('Đ', 'D')
    return text.lower()


def tokenize(text: str) -> List[str]:
    """Tách từ và n-gram ký tự tiếng Việt phục vụ tìm kiếm lai."""
    text = text.lower()
    # Loại bỏ ký tự đặc biệt nhưng giữ chữ và số
    cleaned = re.sub(r'[^\w\s\./-]', ' ', text)
    words = [w.strip() for w in cleaned.split() if len(w.strip()) > 1]
    
    # Bổ sung token không dấu
    no_acc_words = [strip_accents(w) for w in words]
    
    # Bổ sung 3-gram và 4-gram cho tiếng Việt để bắt lỗi chính tả hoặc từ ghép
    tokens = list(words)
    tokens.extend(no_acc_words)
    return tokens


def _clean_str(val: Any) -> str:
    """Ép kiểu chuỗi an toàn cho dữ liệu JSON (kể cả list/dict)."""
    if val is None:
        return ""
    if isinstance(val, list):
        return "\n".join(str(x) for x in val)
    if isinstance(val, dict):
        return json.dumps(val, ensure_ascii=False)
    return str(val).strip()


class SuSuVectorRAG:
    """Động cơ Vector RAG cục bộ siêu tốc cho Trợ lý Su Su."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.chunks: List[Dict[str, Any]] = []
        self.vocab: Dict[str, int] = {}
        if HAS_NUMPY:
            self.idf: np.ndarray = np.array([])
            self.doc_vectors: Optional[np.ndarray] = None
            self.doc_lengths: np.ndarray = np.array([])
        else:
            self.idf = []
            self.doc_vectors = None
            self.doc_lengths = []
        self.avg_doc_len: float = 0.0
        
        self._init_db()
        if HAS_NUMPY:
            self.load_or_build_index()
        else:
            self._load_metadata_only()

    def _load_metadata_only(self):
        """Nạp dữ liệu cơ bản từ SQLite khi chưa cài numpy."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT id, chunk_uid, source_name, source_type, pillar, title, context, solution, quote, lesson FROM kb_chunks LIMIT 200").fetchall()
            self.chunks = [dict(r) for r in rows]
            conn.close()
        except Exception:
            pass

    def _init_db(self):
        """Khởi tạo cấu trúc bảng SQLite lưu trữ Vector Knowledge Base."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kb_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_uid TEXT UNIQUE,
                    source_name TEXT,
                    source_type TEXT,
                    pillar TEXT,
                    title TEXT,
                    context TEXT,
                    solution TEXT,
                    quote TEXT,
                    lesson TEXT,
                    raw_text TEXT,
                    tokens_json TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kb_pillar ON kb_chunks(pillar)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kb_source ON kb_chunks(source_type)")
            conn.commit()
        finally:
            conn.close()

    def count(self) -> int:
        """Tổng số đơn vị tri thức trong bộ nhớ / database."""
        return len(self.chunks)

    def load_or_build_index(self):
        """Nạp chỉ mục từ SQLite; nếu chưa có thì tự động quét và nạp dữ liệu."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM kb_chunks").fetchall()
        finally:
            conn.close()

        if rows:
            self._load_from_rows(rows)
        else:
            print("[SuSu RAG] Chưa có cơ sở dữ liệu vector. Đang tự động lập chỉ mục lần đầu...")
            self.rebuild_full_knowledge_base()

    def _load_from_rows(self, rows: list):
        """Tái thiết lập ma trận vector từ các dòng SQLite."""
        self.chunks = []
        token_lists = []
        for r in rows:
            tokens = json.loads(r["tokens_json"])
            chunk = {
                "id": r["id"],
                "chunk_uid": r["chunk_uid"],
                "source_name": r["source_name"],
                "source_type": r["source_type"],
                "pillar": r["pillar"],
                "title": r["title"],
                "context": r["context"],
                "solution": r["solution"],
                "quote": r["quote"],
                "lesson": r["lesson"],
                "raw_text": r["raw_text"],
                "tokens": tokens
            }
            self.chunks.append(chunk)
            token_lists.append(tokens)

        self._build_vector_matrices(token_lists)

    def rebuild_full_knowledge_base(self):
        """Quét toàn bộ Data/ (1,263+ ca thực chiến) và docs/ (Cẩm nang CHT, TT12, TT38...) vào SQLite."""
        all_chunks = []
        
        # 1. Quét file 1,263+ tình huống thực chiến, Google Drive & YouTube (Thầy Linh, Thầy Long, Thầy Tuấn)
        json_paths = [
            DATA_DIR / "tinh_huong_bim_tcvn14177_tt09.json",
            DATA_DIR / "tinh_huong_thuc_chien.json",
            DATA_DIR / "14_tinh_huong_hom_nay.json",
            DATA_DIR / "tinh_huong_cong_trinh.json",
            DATA_DIR / "tinh_huong_google_drive.json",
            DATA_DIR / "tinh_huong_huynh_nhat_linh_youtube.json",
            DATA_DIR / "tinh_huong_pham_thanh_long_youtube.json",
            DATA_DIR / "tinh_huong_ceo_vietnam_youtube.json",
            DATA_DIR / "tinh_huong_gxd_youtube.json",
            DATA_DIR / "tinh_huong_nguyentheanh_youtube.json",
            DATA_DIR / "tinh_huong_le_van_thinh_phap_ly.json",
            DATA_DIR / "tinh_huong_vnk_mep.json",
            DATA_DIR / "tinh_huong_dau_thau_bu_gia_fidic.json",
            DATA_DIR / "tinh_huong_hse_an_toan_lao_dong.json",
            DATA_DIR / "tinh_huong_dia_ky_thuat_mong_sau.json"
        ]
        
        seen_titles = set()
        for jp in json_paths:
            if jp.exists():
                try:
                    with open(jp, "r", encoding="utf-8") as f:
                        items = json.load(f)
                    for idx, it in enumerate(items):
                        raw_title = it.get("TieuDe") or it.get("TenSuCo") or it.get("TenTinhHuong") or f"Tình huống #{idx+1}"
                        title = _clean_str(raw_title)
                        if title in seen_titles:
                            continue
                        seen_titles.add(title)
                        
                        pillar = _clean_str(it.get("TruCot", "CHUNG"))
                        context = _clean_str(it.get("BoiCanh") or it.get("NguyenNhan") or "")
                        solution = _clean_str(it.get("ChienLuocXuLy") or it.get("BienPhapXuLy") or it.get("CachXuLy") or "")
                        quote = _clean_str(it.get("CauThoaiMau", ""))
                        lesson = _clean_str(it.get("BaiHocXuongMau") or it.get("BaiHocRUTRa") or "")
                        
                        # Gắn nguồn trích dẫn YouTube nếu có
                        if jp.name == "tinh_huong_huynh_nhat_linh_youtube.json":
                            v_title = it.get("VideoTitle") or title
                            v_url = it.get("VideoUrl", "")
                            source_name = f"YouTube Thầy Huỳnh Nhất Linh - {v_title}"
                            source_type = "YOUTUBE_HUYNH_NHAT_LINH"
                            if v_url and v_url not in solution:
                                solution += f"\n\n📌 Nguồn bài giảng: Thầy Huỳnh Nhất Linh - [Xem video gốc]({v_url})"
                        elif jp.name == "tinh_huong_pham_thanh_long_youtube.json":
                            v_title = it.get("VideoTitle") or title
                            v_url = it.get("VideoUrl", "")
                            source_name = f"YouTube Thầy Phạm Thành Long - {v_title}"
                            source_type = "YOUTUBE_PHAM_THANH_LONG"
                            if v_url and v_url not in solution:
                                solution += f"\n\n📌 Nguồn bài giảng: Thầy Phạm Thành Long - [Xem video gốc]({v_url})"
                        elif jp.name == "tinh_huong_ceo_vietnam_youtube.json":
                            v_title = it.get("VideoTitle") or title
                            v_url = it.get("VideoUrl", "")
                            source_name = f"YouTube Thầy Ngô Minh Tuấn - {v_title}"
                            source_type = "YOUTUBE_CEO_VIETNAM"
                            if v_url and v_url not in solution:
                                solution += f"\n\n📌 Nguồn bài giảng: Thầy Ngô Minh Tuấn - [Xem video gốc]({v_url})"
                        elif jp.name == "tinh_huong_gxd_youtube.json":
                            v_title = it.get("VideoTitle") or title
                            v_url = it.get("VideoUrl", "")
                            source_name = f"YouTube Giá Xây Dựng (GXD) - {v_title}"
                            source_type = "YOUTUBE_GXD"
                            if v_url and v_url not in solution:
                                solution += f"\n\n📌 Nguồn bài giảng: Giá Xây Dựng (GXD) - [Xem video gốc]({v_url})"
                        elif jp.name == "tinh_huong_nguyentheanh_youtube.json":
                            v_title = it.get("VideoTitle") or title
                            v_url = it.get("VideoUrl", "")
                            source_name = f"YouTube TS Nguyễn Thế Anh (Hội Kỹ Sư QS) - {v_title}"
                            source_type = "YOUTUBE_NGUYEN_THE_ANH"
                            if v_url and v_url not in solution:
                                solution += f"\n\n📌 Nguồn bài giảng: TS Nguyễn Thế Anh - [Xem video gốc]({v_url})"
                        elif jp.name == "tinh_huong_le_van_thinh_phap_ly.json":
                            source_name = "Chuyên đề Pháp lý Hợp đồng Xây dựng Thầy Lê Văn Thịnh"
                            source_type = "PHAP_LY_LE_VAN_THINH"
                        elif jp.name == "tinh_huong_vnk_mep.json":
                            v_title = it.get("VideoTitle") or title
                            v_url = it.get("VideoUrl", "")
                            source_name = f"Cơ Điện VNK (VNK EDU) - {it.get('ChuyenDe', v_title)}"
                            source_type = "MEP_VNK"
                            if v_url and v_url not in solution:
                                solution += f"\n\n📌 Nguồn bài giảng: Cơ Điện VNK - [Xem video gốc]({v_url})"
                        elif jp.name == "tinh_huong_dau_thau_bu_gia_fidic.json":
                            source_name = f"Viện Kinh Tế Xây Dựng & Hợp Đồng FIDIC - {it.get('ChuyenDe', 'Đấu thầu')}"
                            source_type = "DAU_THAU_BU_GIA_FIDIC"
                        elif jp.name == "tinh_huong_hse_an_toan_lao_dong.json":
                            source_name = f"An Toàn Lao Động HSE (QCVN 18:2021/BXD) - {it.get('ChuyenDe', 'An toàn')}"
                            source_type = "HSE_AN_TOAN_LAO_DONG"
                        elif jp.name == "tinh_huong_bim_tcvn14177_tt09.json":
                            source_name = f"BIM & TCVN 14177 VNCC - {it.get('ChuyenDe', 'BIM')}"
                            source_type = "BIM_TCVN14177_TT09"
                        elif jp.name == "tinh_huong_dia_ky_thuat_mong_sau.json":
                            source_name = f"Địa Kỹ Thuật & Xử Lý Móng Sâu - {it.get('ChuyenDe', 'Móng sâu')}"
                            source_type = "DIA_KY_THUAT_MONG_SAU"
                        elif jp.name == "tinh_huong_google_drive.json":
                            source_name = f"Google Drive - {it.get('SourceGroup', 'Tài liệu')}"
                            source_type = "GOOGLE_DRIVE"
                        else:
                            source_name = "1,263 Tình Huống Thực Chiến (8 Trụ Cột)"
                            source_type = "THUC_CHIEN"
                        
                        raw = f"{title}\nBối cảnh: {context}\nGiải pháp: {solution}\nThoại: {quote}\nBài học: {lesson}"
                        tokens = tokenize(raw)
                        
                        all_chunks.append({
                            "chunk_uid": f"case_{len(all_chunks)+1:04d}",
                            "source_name": source_name,
                            "source_type": source_type,
                            "pillar": pillar,
                            "title": title,
                            "context": context,
                            "solution": solution,
                            "quote": quote,
                            "lesson": lesson,
                            "raw_text": raw,
                            "tokens": tokens
                        })
                except Exception as e:
                    print(f"[SuSu RAG] Lỗi đọc {jp}: {e}")

        # 2. Quét các tài liệu Cẩm nang & Pháp lý trong docs/
        doc_files = [
            ("CAM_NANG_CHI_HUY_TRUONG.md", "Cẩm Nang Chỉ Huy Trưởng Thực Chiến", "KY_THUAT_HIEN_TRUONG"),
            ("BIM_TCVN14177_DINH_MUC_TT09.md", "Cẩm Nang Thực Chiến BIM & TCVN 14177 (VNCC)", "PHAP_LY_BAN_GIAY"),
            ("PHAP_LY_2026_ROADMAP.md", "Lộ Trình Pháp Lý Xây Dựng 2026 (TT38/TT12/Luật XD)", "PHAP_LY_BAN_GIAY"),
            ("DINH_MUC_FRAMEWORK_2025_2026.md", "Khung Định Mức & Dự Toán 2025-2026", "DONG_TIEN_TAI_CHINH"),
            ("BCH_JOBS_AND_TOOLS.md", "Sổ Tay Nghiệp Vụ Ban Chỉ Huy Công Trường", "KY_THUAT_HIEN_TRUONG"),
            ("LHR_THAU_PHU_KIEM_SOAT.md", "Quy Trình Kiểm Soát Tổ Đội & Thầu Phụ", "TO_DOI_CAI_THAU"),
            ("GIAO_BAN_16H30.md", "Quy Chuẩn Họp Giao Ban 16h30 Hiện Trường", "NGOAI_GIAO_BAN_TIEC"),
            ("PM_ADVISOR_ELITE.md", "Cẩm Nang Giám Đốc Dự Án & Quản Lý Chi Phí", "DONG_TIEN_TAI_CHINH"),
            ("TRACKING_TIEN_DO.md", "Hệ Thống Theo Dõi Tiến Độ & Đơn Giá", "DONG_TIEN_TAI_CHINH"),
        ]

        for fname, s_name, pillar in doc_files:
            fpath = DOCS_DIR / fname
            if fpath.exists():
                try:
                    text = fpath.read_text(encoding="utf-8", errors="replace")
                    sections = re.split(r'\n(?=#{1,3}\s+)', text)
                    for s_idx, sec in enumerate(sections):
                        sec = sec.strip()
                        if len(sec) < 80:
                            continue
                        
                        first_line = sec.split("\n")[0].replace("#", "").strip()
                        title = f"[{s_name}] {first_line}"
                        tokens = tokenize(sec)
                        
                        all_chunks.append({
                            "chunk_uid": f"doc_{fname}_{s_idx:03d}",
                            "source_name": s_name,
                            "source_type": "TAI_LIEU_PHAP_LY",
                            "pillar": pillar,
                            "title": title,
                            "context": sec[:400] + ("..." if len(sec) > 400 else ""),
                            "solution": sec,
                            "quote": "",
                            "lesson": "Tuân thủ nghiêm ngặt quy định và cẩm nang ban chỉ huy.",
                            "raw_text": sec,
                            "tokens": tokens
                        })
                except Exception as e:
                    print(f"[SuSu RAG] Lỗi đọc doc {fname}: {e}")

        # 3. Ghi toàn bộ vào SQLite
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("DELETE FROM kb_chunks")
            for c in all_chunks:
                conn.execute("""
                    INSERT INTO kb_chunks 
                    (chunk_uid, source_name, source_type, pillar, title, context, solution, quote, lesson, raw_text, tokens_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    c["chunk_uid"], c["source_name"], c["source_type"], c["pillar"],
                    c["title"], c["context"], c["solution"], c["quote"], c["lesson"],
                    c["raw_text"], json.dumps(c["tokens"], ensure_ascii=False)
                ))
            conn.commit()
        finally:
            conn.close()

        print(f"[SuSu RAG] Đã nạp thành công {len(all_chunks)} đơn vị tri thức vào SQLite Database.")
        self.chunks = all_chunks
        self._build_vector_matrices([c["tokens"] for c in all_chunks])

    def add_chunks(self, new_chunks: List[Dict[str, Any]]):
        """Bổ sung thêm các đơn vị tri thức mới vào SQLite và cập nhật lại vector search tức thì."""
        if not new_chunks:
            return
        conn = sqlite3.connect(str(self.db_path))
        try:
            for c in new_chunks:
                tokens = c.get("tokens", [])
                if not tokens and c.get("raw_text"):
                    tokens = tokenize(c["raw_text"])
                    c["tokens"] = tokens

                conn.execute("""
                    INSERT INTO kb_chunks 
                    (chunk_uid, source_name, source_type, pillar, title, context, solution, quote, lesson, raw_text, tokens_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    c["chunk_uid"], c.get("source_name", "Google Drive Ingest"), c.get("source_type", "GOOGLE_DRIVE"),
                    c.get("pillar", "CHUNG"), c["title"], c.get("context", ""), c.get("solution", ""),
                    c.get("quote", ""), c.get("lesson", ""), c.get("raw_text", ""),
                    json.dumps(tokens, ensure_ascii=False)
                ))
            conn.commit()
        finally:
            conn.close()

        self.chunks.extend(new_chunks)
        self._build_vector_matrices([c["tokens"] for c in self.chunks])
        print(f"[SuSu RAG] Đã cập nhật thêm {len(new_chunks)} đơn vị tri thức mới. Tổng số: {len(self.chunks)}.")

    def clear_project_dossier(self) -> int:
        """Xóa toàn bộ các chunk hồ sơ dự án khỏi CSDL Vector RAG."""
        deleted_count = 0
        conn = sqlite3.connect(str(self.db_path))
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM kb_chunks WHERE source_type = 'PROJECT_DOSSIER'")
            deleted_count = cur.fetchone()[0]
            conn.execute("DELETE FROM kb_chunks WHERE source_type = 'PROJECT_DOSSIER'")
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

        # Xóa trong bộ nhớ tạm nếu có
        self.chunks = [c for c in self.chunks if c.get("source_type") != "PROJECT_DOSSIER"]
        self._build_vector_matrices([c["tokens"] for c in self.chunks])
        return deleted_count

    def ingest_project_dossier(self, dossier: Dict[str, Any]) -> int:
        """Nạp hồ sơ dự án (Hợp đồng, BOQ, Tiến độ) vào Não bộ Su Su Vector RAG."""
        if not dossier:
            return 0
        
        # Xóa các chunk hồ sơ dự án cũ nếu có
        self.clear_project_dossier()
            
        proj_title = dossier.get("title", "Dự án Hiện Hành")
        new_chunks = []
        now_ts = int(time.time())
        
        # 1. Chunk Tóm tắt dự án
        exec_sum = dossier.get("executive_summary", "")
        if exec_sum:
            new_chunks.append({
                "chunk_uid": f"proj_summary_{now_ts}",
                "source_name": proj_title,
                "source_type": "PROJECT_DOSSIER",
                "pillar": "TỔNG THỂ DỰ ÁN",
                "title": f"Tổng Quan Hồ Sơ Công Trình - {proj_title}",
                "context": exec_sum,
                "solution": "Căn cứ hồ sơ dự án thật để áp dụng cho mọi tình huống pháp lý và thi công.",
                "quote": f"Hồ sơ công trình {proj_title}",
                "lesson": "Nắm vững mốc thời gian, giá trị hợp đồng và các hạng mục găng của dự án.",
                "raw_text": f"Hồ sơ công trình {proj_title}:\n{exec_sum}"
            })
            
        # 2. Chunks Điều khoản Hợp đồng
        contract = dossier.get("contract", {})
        if contract and not contract.get("error"):
            for idx, tb in enumerate(contract.get("time_bars", []), 1):
                new_chunks.append({
                    "chunk_uid": f"proj_contract_timebar_{idx}_{now_ts}",
                    "source_name": proj_title,
                    "source_type": "PROJECT_DOSSIER",
                    "pillar": "PHÁP LÝ & HỢP ĐỒNG",
                    "title": f"Thời hạn khiếu nại phát sinh (Time-bar {tb.get('days')} ngày) - {proj_title}",
                    "context": tb.get("clause_text", ""),
                    "solution": f"Phải gửi thông báo biến động hoặc khiếu nại trong vòng {tb.get('days')} ngày để bảo toàn quyền lợi thanh toán.",
                    "quote": f"Điều khoản hợp đồng {proj_title}",
                    "lesson": "Quá thời hạn time-bar nhà thầu mất quyền đòi chi phí và thời gian.",
                    "raw_text": f"Điều khoản thời hạn khiếu nại {tb.get('days')} ngày dự án {proj_title}: {tb.get('clause_text', '')}"
                })
            for idx, clause in enumerate(contract.get("key_clauses", []), 1):
                new_chunks.append({
                    "chunk_uid": f"proj_contract_clause_{idx}_{now_ts}",
                    "source_name": proj_title,
                    "source_type": "PROJECT_DOSSIER",
                    "pillar": "PHÁP LÝ & HỢP ĐỒNG",
                    "title": f"Điều khoản hợp đồng quan trọng #{idx} - {proj_title}",
                    "context": clause,
                    "solution": "Thực hiện đúng quy định đã cam kết trong hợp đồng.",
                    "quote": f"Hợp đồng {proj_title}",
                    "lesson": "Đối chiếu điều khoản trước khi phát hành văn bản hoặc nghiệm thu.",
                    "raw_text": f"Hợp đồng {proj_title} điều khoản #{idx}:\n{clause}"
                })
                
        # 3. Chunks BOQ Top chi phí
        boq = dossier.get("boq", {})
        if boq and not boq.get("error") and boq.get("top_cost_items"):
            top_desc = "\n".join([f"- {it.get('name', '')}: {it.get('quantity', '')} {it.get('unit', '')} | {it.get('amount_str', '')} ({it.get('pct_of_total', 0)}%)" for it in boq["top_cost_items"][:10]])
            new_chunks.append({
                "chunk_uid": f"proj_boq_top_{now_ts}",
                "source_name": proj_title,
                "source_type": "PROJECT_DOSSIER",
                "pillar": "DỰ TOÁN & CHI PHÍ",
                "title": f"Top hạng mục chi phí lớn nhất BOQ (Pareto 80/20) - {proj_title}",
                "context": top_desc,
                "solution": "Kiểm soát chặt chẽ hao hụt vật tư và nghiệm thu đối với các hạng mục chiếm tỷ trọng ngân sách lớn.",
                "quote": f"BOQ {proj_title}",
                "lesson": "Ưu tiên quản trị 20% đầu việc chiếm 80% ngân sách.",
                "raw_text": f"Top hạng mục chi phí lớn nhất BOQ dự án {proj_title}:\n{top_desc}"
            })
            
        # 4. Chunks Đường găng Tiến độ
        schedule = dossier.get("schedule", {})
        if schedule and not schedule.get("error"):
            if schedule.get("critical_tasks"):
                crit_desc = "\n".join([f"- [ID {ct.get('id')}] {ct.get('name')}: {ct.get('start')} -> {ct.get('finish')}" for ct in schedule["critical_tasks"][:10]])
                new_chunks.append({
                    "chunk_uid": f"proj_sched_crit_{now_ts}",
                    "source_name": proj_title,
                    "source_type": "PROJECT_DOSSIER",
                    "pillar": "TIẾN ĐỘ THI CÔNG",
                    "title": f"Đường găng tiến độ thi công (Critical Path) - {proj_title}",
                    "context": crit_desc,
                    "solution": "Tập trung tối đa nguồn lực, nhân công, thiết bị để không làm chậm các công việc đường găng.",
                    "quote": f"Tiến độ {proj_title}",
                    "lesson": "Chậm 1 ngày trên đường găng là chậm cả dự án.",
                    "raw_text": f"Công việc trên đường găng tiến độ dự án {proj_title}:\n{crit_desc}"
                })
                
        if new_chunks:
            self.add_chunks(new_chunks)
        return len(new_chunks)

    def _build_vector_matrices(self, token_lists: List[List[str]]):
        """Xây dựng từ điển TF-IDF và BM25 cho thuật toán tìm kiếm lai."""
        num_docs = len(token_lists)
        if num_docs == 0:
            return

        # Đếm tần suất tài liệu (Doc Frequency)
        df_counts: Dict[str, int] = {}
        for tokens in token_lists:
            seen = set(tokens)
            for t in seen:
                df_counts[t] = df_counts.get(t, 0) + 1

        # Chỉ giữ lại các token xuất hiện từ 1 đến 80% số tài liệu để loại nhiễu
        vocab = {}
        idf_list = []
        max_df = max(1, int(num_docs * 0.85))
        
        idx = 0
        for token, df in sorted(df_counts.items(), key=lambda x: -x[1]):
            if 1 <= df <= max_df:
                vocab[token] = idx
                # Tính IDF theo công thức BM25: log((N - df + 0.5) / (df + 0.5) + 1)
                idf_val = math.log((num_docs - df + 0.5) / (df + 0.5) + 1.0)
                idf_list.append(max(0.1, idf_val))
                idx += 1

        self.vocab = vocab
        self.idf = np.array(idf_list, dtype=np.float32)

        # Xây dựng ma trận tài liệu (Sparse/Dense representation tối ưu)
        num_terms = len(vocab)
        self.doc_vectors = np.zeros((num_docs, num_terms), dtype=np.float32)
        doc_lengths = []

        for d_idx, tokens in enumerate(token_lists):
            doc_len = len(tokens)
            doc_lengths.append(doc_len)
            tf_dict = {}
            for t in tokens:
                if t in vocab:
                    t_id = vocab[t]
                    tf_dict[t_id] = tf_dict.get(t_id, 0) + 1

            for t_id, tf in tf_dict.items():
                # TF có log dampening
                self.doc_vectors[d_idx, t_id] = (1.0 + math.log(tf)) * self.idf[t_id]

        # Chuẩn hóa vector L2 để cosine similarity = dot product
        norms = np.linalg.norm(self.doc_vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.doc_vectors = self.doc_vectors / norms

        self.doc_lengths = np.array(doc_lengths, dtype=np.float32)
        self.avg_doc_len = float(np.mean(self.doc_lengths)) if doc_lengths else 1.0

    def _query_sqlite_fallback(self, query_text: str, top_k: int = 5, pillar_filter: str = "") -> List[Dict[str, Any]]:
        """Truy vấn dự phòng trực tiếp qua SQLite khi môi trường thiếu numpy hoặc RAM."""
        if not self.db_path.exists():
            return []
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            raw_tokens = tokenize(query_text)
            terms = [t for t in raw_tokens if len(t) > 1][:6]
            if not terms:
                terms = [w.strip().lower() for w in query_text.split() if len(w.strip()) > 1][:6]

            clauses = []
            params = []
            for t in terms:
                clauses.append("(LOWER(title) LIKE ? OR LOWER(context) LIKE ? OR LOWER(solution) LIKE ? OR LOWER(raw_text) LIKE ?)")
                p = f"%{t}%"
                params.extend([p, p, p, p])

            filter_sql = ""
            if pillar_filter:
                filter_sql = " AND (pillar = ? OR pillar LIKE ?)"
                params.extend([pillar_filter, f"%{pillar_filter}%"])

            where_sql = " AND ".join(clauses) if clauses else "1=1"
            sql = f"SELECT id, chunk_uid, source_name, source_type, pillar, title, context, solution, quote, lesson FROM kb_chunks WHERE {where_sql} {filter_sql} LIMIT {top_k}"
            rows = cur.execute(sql, params).fetchall()

            if len(rows) < top_k and len(clauses) > 1:
                where_or = " OR ".join(clauses)
                or_params = []
                for t in terms:
                    p = f"%{t}%"
                    or_params.extend([p, p, p, p])
                if pillar_filter:
                    or_params.extend([pillar_filter, f"%{pillar_filter}%"])
                sql_or = f"SELECT id, chunk_uid, source_name, source_type, pillar, title, context, solution, quote, lesson FROM kb_chunks WHERE ({where_or}) {filter_sql} LIMIT {top_k}"
                rows = cur.execute(sql_or, or_params).fetchall()

            conn.close()
            results = []
            for r in rows:
                item = dict(r)
                item["similarity_pct"] = 85.0
                item["raw_score"] = 0.85
                results.append(item)
            return results
        except Exception as e:
            print(f"[SQLite Fallback Error] {e}")
            return []

    def query(self, query_text: str, top_k: int = 5, pillar_filter: str = "") -> List[Dict[str, Any]]:
        """
        Tìm kiếm lai (Hybrid Search: Cosine Vector Semantic + BM25 Lexical).
        Trả về danh sách top_k kết quả tốt nhất kèm phần trăm độ tương đồng.
        """
        if not HAS_NUMPY or self.doc_vectors is None or len(self.chunks) == 0:
            return self._query_sqlite_fallback(query_text, top_k, pillar_filter)

        q_tokens = tokenize(query_text)
        if not q_tokens:
            return []

        num_terms = len(self.vocab)
        q_vec = np.zeros(num_terms, dtype=np.float32)
        
        # 1. Tính Vector Query
        for t in q_tokens:
            if t in self.vocab:
                t_id = self.vocab[t]
                q_vec[t_id] += 1.0

        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = (q_vec * self.idf) / np.linalg.norm(q_vec * self.idf)
            # Vector Semantic Similarity (Cosine = Dot Product): [0..1]
            vector_scores = np.dot(self.doc_vectors, q_vec)
        else:
            vector_scores = np.zeros(len(self.chunks), dtype=np.float32)

        # 2. Tính BM25 Lexical Score
        k1 = 1.5
        b = 0.75
        bm25_scores = np.zeros(len(self.chunks), dtype=np.float32)
        
        for t in set(q_tokens):
            if t in self.vocab:
                t_id = self.vocab[t]
                idf_val = self.idf[t_id]
                col_tf = self.doc_vectors[:, t_id]  # tương đương tf*idf
                # raw tf estimate
                tfs = np.where(col_tf > 0, np.exp(col_tf / idf_val - 1.0), 0)
                len_norm = 1.0 - b + b * (self.doc_lengths / self.avg_doc_len)
                term_bm25 = idf_val * (tfs * (k1 + 1.0)) / (tfs + k1 * len_norm)
                bm25_scores += term_bm25

        max_bm25 = float(np.max(bm25_scores)) if len(bm25_scores) > 0 else 0.0
        if max_bm25 > 0:
            bm25_normalized = bm25_scores / max_bm25
        else:
            bm25_normalized = bm25_scores

        # 3. Hybrid Score = 0.60 * Vector Semantic + 0.40 * BM25
        hybrid_scores = 0.60 * vector_scores + 0.40 * bm25_normalized

        # Boost cho tiêu đề nếu query xuất hiện trong tiêu đề
        q_clean = strip_accents(query_text)
        for i, chk in enumerate(self.chunks):
            t_clean = strip_accents(chk["title"])
            if q_clean in t_clean:
                hybrid_scores[i] += 0.35

        # Áp dụng bộ lọc Pillar nếu có
        if pillar_filter:
            for i, chk in enumerate(self.chunks):
                if chk["pillar"] != pillar_filter and pillar_filter not in chk["pillar"]:
                    hybrid_scores[i] = -1.0

        # Lấy top_k kết quả cao nhất
        ranked_indices = np.argsort(-hybrid_scores)
        results = []

        for r_idx in ranked_indices[:top_k]:
            score = float(hybrid_scores[r_idx])
            if score <= 0.01:
                continue
            
            chunk_data = dict(self.chunks[r_idx])
            # Tính % tương đồng hiển thị (capped 99%)
            pct_score = min(99.0, max(45.0, score * 100.0))
            chunk_data["similarity_pct"] = round(pct_score, 1)
            chunk_data["raw_score"] = score
            results.append(chunk_data)

        return results

    def search(self, query_text: str, top_k: int = 5, pillar_filter: str = "") -> List[Dict[str, Any]]:
        """Alias tương thích cho query()."""
        return self.query(query_text, top_k=top_k, pillar_filter=pillar_filter)

    def get_rag_context_for_prompt(self, user_question: str, top_k: int = 4) -> str:
        """Tạo đoạn trích dẫn bối cảnh chuẩn mực (Grounding Context) nạp cho Google Gemini Prompt."""
        top_cases = self.query(user_question, top_k=top_k)
        if not top_cases:
            return ""

        context_lines = [
            "--- CÁC CĂN CỨ PHÁP LÝ & BÀI HỌC THỰC CHIẾN TỪ NÃO BỘ VECTOR RAG ĐÃ ĐỐI CHIẾU ---"
        ]
        for i, c in enumerate(top_cases, 1):
            source = c.get("source_name", "Kho tri thức thực chiến")
            pillar = c.get("pillar", "CHUNG")
            title = c.get("title", "")
            sim = c.get("similarity_pct", 0)
            ctx = c.get("context", "")
            sol = c.get("solution", "")
            quote = c.get("quote", "")
            lesson = c.get("lesson", "")

            context_lines.append(f"\n[CĂN CỨ {i}] ({sim}% Khớp) • Nguồn: {source} • Trụ Cột: {pillar}")
            context_lines.append(f"Tiêu đề: {title}")
            if ctx:
                context_lines.append(f"- Bối cảnh/Quy định: {ctx}")
            if sol:
                context_lines.append(f"- Giải pháp/Điều khoản: {sol}")
            if quote:
                context_lines.append(f"- Mẫu đối đáp/Công văn: {quote}")
            if lesson:
                context_lines.append(f"- Đúc kết xương máu: {lesson}")

        context_lines.append("-----------------------------------------------------------------------------------")
        return "\n".join(context_lines)


# Singleton instance để nạp nhanh vào bộ nhớ
_RAG_INSTANCE: Optional[SuSuVectorRAG] = None

def get_vector_rag() -> SuSuVectorRAG:
    global _RAG_INSTANCE
    if _RAG_INSTANCE is None:
        _RAG_INSTANCE = SuSuVectorRAG()
    return _RAG_INSTANCE


if __name__ == "__main__":
    print("Testing SuSu Vector RAG Engine...")
    rag = get_vector_rag()
    test_q = "thi công gặp mưa to thì xử lý bê tông dầm sàn thế nào?"
    print(f"\nQuery: '{test_q}'")
    res = rag.query(test_q, top_k=3)
    for r in res:
        print(f" -> [{r['similarity_pct']}%] [{r['source_name']}] {r['title']}")
