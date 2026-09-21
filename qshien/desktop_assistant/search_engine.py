# -*- coding: utf-8 -*-
"""
search_engine.py - Bộ Máy Tìm Kiếm Siêu Tốc & Vector RAG cho Trợ Lý Su Su
Tích hợp:
1. Lexical Keyword Matching (Từ khóa tức thì < 0.001s)
2. Vector RAG Hybrid Semantic Search (Hiểu câu hỏi tự nhiên, độ khớp %)
"""

from __future__ import annotations

import unicodedata
import re
from typing import List, Dict, Any, Optional

try:
    from .vector_rag_engine import get_vector_rag, SuSuVectorRAG, strip_accents, tokenize
except ImportError:
    from vector_rag_engine import get_vector_rag, SuSuVectorRAG, strip_accents, tokenize


class FastSearchEngine:
    def __init__(self, raw_scenarios: List[Dict[str, Any]]):
        self.raw_scenarios = raw_scenarios
        self.index: List[Dict[str, Any]] = []
        self.rag: Optional[SuSuVectorRAG] = None
        
        try:
            self.rag = get_vector_rag()
        except Exception as e:
            print(f"[SearchEngine] Khởi tạo RAG cảnh báo: {e}")
            
        self._build_fallback_index()

    def _build_fallback_index(self):
        """Xây dựng chỉ mục nhanh trong RAM làm phương án dự phòng."""
        self.index.clear()
        for idx, sc in enumerate(self.raw_scenarios):
            title = sc.get("TieuDe") or sc.get("TenSuCo") or sc.get("TenTinhHuong") or "Tình huống thực chiến"
            context = sc.get("BoiCanh") or sc.get("NguyenNhan") or ""
            sol = sc.get("ChienLuocXuLy") or sc.get("BienPhapXuLy") or sc.get("CachXuLy") or ""
            thoai = sc.get("CauThoaiMau") or ""
            bai_hoc = sc.get("BaiHocXuongMau") or sc.get("BaiHocRUTRa") or ""
            pillar = sc.get("TruCot", "")

            raw_blob = f"{title} {context} {sol} {thoai} {bai_hoc}".lower()
            no_acc_blob = strip_accents(raw_blob)

            self.index.append({
                "idx": idx,
                "title": title,
                "pillar": pillar,
                "blob_accent": raw_blob,
                "blob_no_accent": no_acc_blob,
                "data": sc,
                "source": "1,263 Tình Huống"
            })

    def search(self, query: str = "", target_pillar: str = "", use_vector_rag: bool = True) -> List[Dict[str, Any]]:
        """
        Tìm kiếm thông minh:
        - Nếu query rỗng: trả về danh sách đầy đủ.
        - Nếu có query và bật Vector RAG: dùng thuật toán Hybrid Vector Semantic + BM25 của SuSuVectorRAG.
        - Tự động fallback sang Lexical In-Memory Search nếu cần.
        """
        q_raw = query.strip()
        
        # 1. Query rỗng -> trả về toàn bộ danh sách
        if not q_raw:
            if not target_pillar:
                return self.index
            return [it for it in self.index if it["pillar"] == target_pillar or target_pillar in it["pillar"]]

        # 2. Sử dụng Não bộ Vector RAG nếu sẵn sàng
        if use_vector_rag and self.rag is not None:
            try:
                rag_results = self.rag.query(q_raw, top_k=40, pillar_filter=target_pillar)
                if rag_results:
                    formatted = []
                    for it in rag_results:
                        sim = it.get("similarity_pct", 50.0)
                        title_clean = it.get("title", "").replace("•", "").strip()
                        formatted.append({
                            "idx": it.get("id", 0),
                            "title": f"[{sim}%] {title_clean}",
                            "pillar": it.get("pillar", "CHUNG"),
                            "data": {
                                "TieuDe": it.get("title"),
                                "BoiCanh": it.get("context"),
                                "ChienLuocXuLy": it.get("solution"),
                                "CauThoaiMau": it.get("quote"),
                                "BaiHocXuongMau": it.get("lesson"),
                                "TruCot": it.get("pillar"),
                                "Source": it.get("source_name", "Tài liệu"),
                                "Similarity": sim
                            },
                            "source": it.get("source_name", "RAG KB")
                        })
                    return formatted
            except Exception as e:
                print(f"[SearchEngine RAG error] {e} - chuyển sang fallback")

        # 3. Fallback: Lexical Search trong RAM
        q_no_acc = strip_accents(q_raw)
        words_accent = q_raw.lower().split()
        words_no_acc = q_no_acc.split()

        scored = []
        for item in self.index:
            if target_pillar and (item["pillar"] != target_pillar and target_pillar not in item["pillar"]):
                continue

            blob_a = item["blob_accent"]
            blob_n = item["blob_no_accent"]
            title_a = item["title"].lower()
            title_n = strip_accents(title_a)

            score = 0
            match = True
            for wa, wn in zip(words_accent, words_no_acc):
                in_blob = wa in blob_a or wn in blob_n
                if not in_blob:
                    match = False
                    break
                score += 1
                if wa in title_a or wn in title_n:
                    score += 3
            if not match:
                continue

            scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [it for _, it in scored]
