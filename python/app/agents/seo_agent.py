from __future__ import annotations

import re

from app.infra.llm import llm_client
from app.rag.retriever import retrieve_blog_context


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", text.strip().lower()).strip("-")
    return slug[:80] or "blog-post"


def optimize_seo(title: str, content: str, tags: list[str]) -> dict:
    related = retrieve_blog_context(f"{title} {' '.join(tags)}", role="ADMIN", user_id=None, visible_scopes=["PUBLIC"])
    fallback = {
        "seoTitle": title[:60],
        "metaDescription": (content or "")[:150],
        "keywords": tags[:8] or ["博客", "AI Agent"],
        "slug": _slugify(title),
        "internalLinks": [
            {
                "articleId": doc["metadata"].get("articleId"),
                "title": doc["metadata"].get("title"),
                "reason": "语义相关，适合作为站内链接",
            }
            for doc in related[:3]
        ],
    }
    return llm_client.complete_json(
        "你是 SEO 优化 Agent，输出严格 JSON，包含 seoTitle/metaDescription/keywords/slug/internalLinks。",
        f"标题：{title}\n标签：{tags}\n正文：{content[:4000]}\n历史相关文章：{related[:3]}",
        fallback,
    )
