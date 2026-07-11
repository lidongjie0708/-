from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

try:
    import jieba
except Exception:  # pragma: no cover
    jieba = None


def tokenize(text: str) -> list[str]:
    if jieba:
        return [token.strip().lower() for token in jieba.lcut(text) if token.strip()]
    return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())


def bm25_search(query: str, documents: list[dict], top_k: int) -> list[dict]:
    if not documents:
        return []
    corpus = [tokenize(_searchable_text(doc)) for doc in documents]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(tokenize(query))
    ranked = []
    for doc, score in zip(documents, scores):
        ranked.append({**doc, "score": float(score), "source": "bm25"})
    return sorted(ranked, key=lambda row: row["score"], reverse=True)[:top_k]


def _searchable_text(doc: dict) -> str:
    metadata = doc.get("metadata", {})
    return " ".join(
        str(part)
        for part in [
            metadata.get("title", ""),
            metadata.get("tags", ""),
            metadata.get("heading", ""),
            metadata.get("imageAlt", ""),
            doc.get("text", ""),
        ]
    )
