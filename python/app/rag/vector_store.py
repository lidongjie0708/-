from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())


def _embed(text: str) -> Counter[str]:
    return Counter(_tokens(text))


def _cosine(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[key] * b.get(key, 0) for key in a)
    norm_a = math.sqrt(sum(value * value for value in a.values()))
    norm_b = math.sqrt(sum(value * value for value in b.values()))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


class InMemoryVectorStore:
    """Demo vector store. Replace with Qdrant/PGVector without changing agents."""

    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []

    def upsert(self, chunk_id: str, text: str, metadata: dict[str, Any]) -> None:
        self.delete(chunk_id=chunk_id)
        self._items.append(
            {
                "id": chunk_id,
                "text": text,
                "metadata": metadata,
                "embedding": _embed(text + " " + " ".join(map(str, metadata.values()))),
            }
        )

    def upsert_many(self, chunks: list[dict[str, Any]]) -> None:
        for chunk in chunks:
            self.upsert(chunk["id"], chunk["text"], chunk["metadata"])

    def delete(self, article_id: str | None = None, chunk_id: str | None = None) -> None:
        if chunk_id is not None:
            self._items = [item for item in self._items if item["id"] != chunk_id]
        if article_id is not None:
            self._items = [
                item for item in self._items if str(item["metadata"].get("articleId")) != str(article_id)
            ]

    def vector_search(self, query: str, top_k: int, filters: dict[str, Any]) -> list[dict[str, Any]]:
        return self.search(query, top_k, filters)

    def scroll_documents(self, filters: dict[str, Any], limit: int = 1000) -> list[dict[str, Any]]:
        docs = []
        for item in self._items:
            if self._match_filters(item["metadata"], filters):
                docs.append(
                    {
                        "id": item["id"],
                        "text": item["text"],
                        "metadata": item["metadata"],
                        "score": 0.0,
                        "source": "bm25",
                    }
                )
        return docs[:limit]

    def search(self, query: str, top_k: int, filters: dict[str, Any]) -> list[dict[str, Any]]:
        query_vec = _embed(query)
        scored: list[dict[str, Any]] = []
        for item in self._items:
            if not self._match_filters(item["metadata"], filters):
                continue
            score = _cosine(query_vec, item["embedding"])
            scored.append(
                {
                    "id": item["id"],
                    "text": item["text"],
                    "metadata": item["metadata"],
                    "score": round(score, 4),
                    "source": "vector",
                }
            )
        return sorted(scored, key=lambda row: row["score"], reverse=True)[:top_k]

    def _match_filters(self, metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
        article_id = filters.get("articleId")
        if article_id is not None and str(metadata.get("articleId")) != str(article_id):
            return False
        scopes = filters.get("visibleScopes")
        if scopes and metadata.get("visibility", "PUBLIC") not in scopes:
            return False
        allowed_status = filters.get("status")
        if allowed_status and metadata.get("status", "PUBLISHED") not in allowed_status:
            return False
        if filters.get("includePrivate"):
            return True
        author_id = filters.get("authorId")
        include_own = filters.get("includeOwnDrafts", False)
        if metadata.get("visibility") == "PRIVATE" and not (
            include_own and str(metadata.get("authorId")) == str(author_id)
        ):
            return False
        return True


vector_store = InMemoryVectorStore()
