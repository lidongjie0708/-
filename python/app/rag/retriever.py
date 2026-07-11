from __future__ import annotations

from typing import Any

from app.config import settings
from app.rag.bm25 import bm25_search
from app.rag.fusion import reciprocal_rank_fusion
from app.rag.query_rewriter import rewrite_query
from app.rag.reranker import rerank
from app.rag.store import get_blog_vector_store
from app.rag.trace import add_trace_stage, summarize_docs


def build_permission_filter(user_id: int | None, role: str, visible_scopes: list[str]) -> dict[str, Any]:
    if role.upper() == "ADMIN":
        return {
            "status": ["PUBLISHED", "DRAFT"],
            "visibleScopes": sanitize_visible_scopes(role, visible_scopes),
            "authorId": user_id,
            "includePrivate": True,
        }
    return {
        "status": ["PUBLISHED"],
        "visibleScopes": sanitize_visible_scopes(role, visible_scopes),
        "authorId": user_id,
        "includeOwnDrafts": False,
    }


def sanitize_visible_scopes(role: str, visible_scopes: list[str] | None) -> list[str]:
    if role.upper() == "ADMIN":
        requested = {scope.upper() for scope in (visible_scopes or ["PUBLIC", "PRIVATE"])}
        return [scope for scope in ["PUBLIC", "PRIVATE"] if scope in requested] or ["PUBLIC", "PRIVATE"]
    return ["PUBLIC"]


def retrieve_blog_context(
    question: str,
    user_id: int | None = None,
    role: str = "USER",
    visible_scopes: list[str] | None = None,
    top_k: int | None = None,
    memory_context: dict | None = None,
    trace: dict | None = None,
) -> list[dict[str, Any]]:
    filters = build_permission_filter(user_id, role, visible_scopes or ["PUBLIC"])
    add_trace_stage(trace, "permission_filter", {"filters": filters})
    should_rewrite, rewrite_reason = _should_rewrite_query(question, memory_context)
    rewritten = rewrite_query(question, memory_context) if should_rewrite else _identity_rewrite(question, memory_context)
    add_trace_stage(
        trace,
        "query_rewrite",
        {
            "rewrite": rewritten,
            "memoryTurns": (memory_context or {}).get("turnCount", 0),
            "mode": settings.rag_query_rewrite_mode,
            "applied": should_rewrite,
            "reason": rewrite_reason,
        },
    )
    retrieval_query = " ".join(
        part
        for part in [
            rewritten.get("rewritten", question),
            " ".join(rewritten.get("keywords", [])),
        ]
        if part
    )
    vector_store = get_blog_vector_store()
    vector_results = vector_store.vector_search(retrieval_query, settings.rag_vector_top_k, filters)
    add_trace_stage(trace, "vector_search", {"query": retrieval_query, "count": len(vector_results), "sample": summarize_docs(vector_results)})
    bm25_candidates = vector_store.scroll_documents(filters, limit=1000)
    bm25_results = bm25_search(retrieval_query, bm25_candidates, settings.rag_bm25_top_k)
    add_trace_stage(trace, "bm25_search", {"candidateCount": len(bm25_candidates), "count": len(bm25_results), "sample": summarize_docs(bm25_results)})
    fused = reciprocal_rank_fusion([vector_results, bm25_results], settings.rag_rrf_k)
    add_trace_stage(trace, "rrf_fusion", {"count": len(fused), "sample": summarize_docs(fused)})
    preliminary = rerank(question, fused, top_k or settings.rag_rerank_top_k, use_remote=False)
    use_remote_rerank, rerank_reason = _should_remote_rerank(preliminary)
    reranked = rerank(question, fused, top_k or settings.rag_rerank_top_k, use_remote=use_remote_rerank)
    add_trace_stage(
        trace,
        "rerank",
        {
            "count": len(reranked),
            "mode": settings.rag_remote_rerank_mode,
            "remoteApplied": use_remote_rerank,
            "reason": rerank_reason,
            "sample": summarize_docs(reranked),
        },
    )
    for item in reranked:
        item["queryRewrite"] = rewritten
    filtered = [
        item
        for item in reranked
        if item.get("rerankScore", item["score"]) >= settings.rag_min_score
    ]
    add_trace_stage(trace, "score_filter", {"minScore": settings.rag_min_score, "count": len(filtered), "sample": summarize_docs(filtered)})
    return filtered


def _identity_rewrite(question: str, memory_context: dict | None = None) -> dict[str, Any]:
    return {
        "original": question,
        "rewritten": question.strip(),
        "keywords": [part for part in question.replace("?", " ").replace("？", " ").split() if part][:8],
        "usedMemory": bool(memory_context and memory_context.get("turnCount")),
        "skipped": True,
    }


def _should_rewrite_query(question: str, memory_context: dict | None) -> tuple[bool, str]:
    mode = settings.rag_query_rewrite_mode
    if mode == "always":
        return True, "mode:always"
    if mode == "never":
        return False, "mode:never"
    normalized = question.strip().lower()
    has_memory = bool(memory_context and memory_context.get("turnCount"))
    follow_up_markers = {
        "这个", "那个", "它", "他们", "这些", "那些", "上面", "刚才", "继续",
        "this", "that", "it", "they", "them", "those", "above", "previous",
    }
    if has_memory and any(marker in normalized or marker in question for marker in follow_up_markers):
        return True, "auto:memory-follow-up"
    if has_memory and len(normalized) <= 24:
        return True, "auto:short-follow-up"
    if len(normalized) <= 10:
        return True, "auto:short-query"
    return False, "auto:standalone-query"


def _should_remote_rerank(preliminary: list[dict[str, Any]]) -> tuple[bool, str]:
    mode = settings.rag_remote_rerank_mode
    if mode == "always":
        return True, "mode:always"
    if mode == "never":
        return False, "mode:never"
    if not settings.dashscope_rerank_api_key:
        return False, "auto:no-api-key"
    if len(preliminary) < 2:
        return False, "auto:single-candidate"
    top = float(preliminary[0].get("rerankScore", preliminary[0].get("score", 0.0)) or 0.0)
    second = float(preliminary[1].get("rerankScore", preliminary[1].get("score", 0.0)) or 0.0)
    margin = top - second
    if top < settings.rag_remote_rerank_min_score:
        return True, f"auto:low-local-score:{top:.3f}"
    if margin < settings.rag_remote_rerank_margin:
        return True, f"auto:close-local-margin:{margin:.3f}"
    return False, f"auto:local-confident:{top:.3f}/{margin:.3f}"
