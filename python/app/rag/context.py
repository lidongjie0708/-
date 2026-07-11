from __future__ import annotations

import re
from typing import Any

from app.config import settings


def estimate_tokens(text: str) -> int:
    # A lightweight mixed Chinese/English approximation. Good enough for budget control.
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z0-9_]+", text))
    punctuation = max(len(text) - cjk - latin, 0)
    return cjk + latin + punctuation // 4


def optimize_context_docs(
    docs: list[dict[str, Any]],
    token_budget: int | None = None,
    max_chunks_per_article: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    budget = token_budget or settings.rag_context_token_budget
    per_article = max_chunks_per_article or settings.rag_max_chunks_per_article
    kept: list[dict[str, Any]] = []
    article_counts: dict[str, int] = {}
    seen_text_hashes: set[int] = set()
    total_tokens = 0
    dropped = {"duplicate": 0, "perArticleLimit": 0, "tokenBudget": 0}

    for doc in sorted(docs, key=lambda item: item.get("rerankScore", item.get("score", 0.0)), reverse=True):
        text = " ".join(str(doc.get("text", "")).split())
        text_hash = hash(text[:500])
        if text_hash in seen_text_hashes:
            dropped["duplicate"] += 1
            continue
        article_id = str(doc.get("metadata", {}).get("articleId", "unknown"))
        if article_counts.get(article_id, 0) >= per_article:
            dropped["perArticleLimit"] += 1
            continue
        tokens = estimate_tokens(text)
        if kept and total_tokens + tokens > budget:
            dropped["tokenBudget"] += 1
            continue
        item = {**doc, "text": text, "estimatedTokens": tokens}
        kept.append(item)
        seen_text_hashes.add(text_hash)
        article_counts[article_id] = article_counts.get(article_id, 0) + 1
        total_tokens += tokens

    return kept, {
        "inputDocs": len(docs),
        "keptDocs": len(kept),
        "estimatedTokens": total_tokens,
        "tokenBudget": budget,
        "maxChunksPerArticle": per_article,
        "dropped": dropped,
    }
