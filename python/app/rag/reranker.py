from __future__ import annotations

import requests

from app.config import settings
from app.rag.bm25 import tokenize


def rerank(query: str, documents: list[dict], top_k: int, use_remote: bool = True) -> list[dict]:
    if use_remote and settings.dashscope_rerank_api_key and documents:
        try:
            return _dashscope_rerank(query, documents, top_k)
        except Exception:
            return _local_rerank(query, documents, top_k)
    return _local_rerank(query, documents, top_k)


def _dashscope_rerank(query: str, documents: list[dict], top_k: int) -> list[dict]:
    response = requests.post(
        f"{settings.dashscope_rerank_base_url}/api/v1/services/rerank/text-rerank/text-rerank",
        headers={
            "Authorization": f"Bearer {settings.dashscope_rerank_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.dashscope_rerank_model,
            "input": {
                "query": query,
                "documents": [_document_text(doc) for doc in documents],
            },
            "parameters": {
                "top_n": top_k,
                "return_documents": False,
            },
        },
        timeout=settings.dashscope_rerank_timeout,
    )
    response.raise_for_status()
    results = _extract_results(response.json())
    ranked = []
    for item in results:
        index = int(item.get("index", item.get("document_index", -1)))
        if index < 0 or index >= len(documents):
            continue
        score = float(item.get("relevance_score", item.get("score", 0.0)))
        ranked.append({**documents[index], "rerankScore": round(score, 6), "rerankModel": settings.dashscope_rerank_model})
    return sorted(ranked, key=lambda row: row["rerankScore"], reverse=True)[:top_k]


def _extract_results(payload: dict) -> list[dict]:
    output = payload.get("output", payload)
    if isinstance(output, dict) and isinstance(output.get("results"), list):
        return output["results"]
    if isinstance(payload.get("results"), list):
        return payload["results"]
    data = payload.get("data")
    if isinstance(data, list):
        return data
    return []


def _local_rerank(query: str, documents: list[dict], top_k: int) -> list[dict]:
    query_terms = set(tokenize(query))
    ranked = []
    for doc in documents:
        doc_terms = set(tokenize(doc.get("text", "")))
        overlap = len(query_terms & doc_terms) / max(len(query_terms), 1)
        type_boost = 0.04 if doc.get("metadata", {}).get("chunkType") in {"code", "image"} else 0.0
        final_score = float(doc.get("score", 0.0)) + overlap + type_boost
        ranked.append({**doc, "rerankScore": round(final_score, 6), "rerankModel": "local-lite"})
    return sorted(ranked, key=lambda row: row["rerankScore"], reverse=True)[:top_k]


def _document_text(doc: dict) -> str:
    metadata = doc.get("metadata", {})
    return "\n".join(
        str(part)
        for part in [
            metadata.get("title", ""),
            metadata.get("heading", ""),
            metadata.get("chunkType", ""),
            metadata.get("language", ""),
            metadata.get("imageAlt", ""),
            doc.get("text", ""),
        ]
        if part
    )
