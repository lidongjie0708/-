from __future__ import annotations

import hashlib
import json
from typing import Any

from app.rag.chunker import build_blog_chunks
from app.rag.store import get_blog_vector_store


def upsert_blog_document(
    article_id: str,
    title: str,
    content: str,
    summary: str = "",
    tags: str | list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> int:
    tag_text = ",".join(tags) if isinstance(tags, list) else (tags or "")
    parsed_chunks = build_blog_chunks(title=title, content=content, summary=summary, tags=tag_text)
    base_metadata = {
        "articleId": article_id,
        "title": title,
        "url": f"/blog/{article_id}",
        "tags": tag_text,
        "visibility": "PUBLIC",
        "status": "PUBLISHED",
    }
    if metadata:
        base_metadata.update({key: value for key, value in metadata.items() if value is not None})
    vector_store = get_blog_vector_store()
    existing = {
        item["id"]: item
        for item in vector_store.scroll_documents({"articleId": article_id}, limit=1000)
    }
    chunks = []
    for index, chunk in enumerate(parsed_chunks):
        chunk_id = f"blog-{article_id}-{index}"
        content_hash = _content_hash({"text": chunk["text"], "metadata": base_metadata, "index": index})
        if existing.get(chunk_id, {}).get("metadata", {}).get("contentHash") == content_hash:
            continue
        chunks.append(
            {
                "id": chunk_id,
                "text": chunk["text"],
                "metadata": {
                    **base_metadata,
                    "chunkIndex": index,
                    "contentHash": content_hash,
                    "chunkType": chunk["chunkType"],
                    "heading": chunk.get("heading"),
                    "language": chunk.get("language"),
                    "imageAlt": chunk.get("imageAlt"),
                    "imageSrc": chunk.get("imageSrc"),
                },
            }
        )
    desired_ids = {f"blog-{article_id}-{index}" for index in range(len(parsed_chunks))}
    stale_ids = set(existing) - desired_ids
    for chunk_id in stale_ids:
        vector_store.delete(chunk_id=chunk_id)
    vector_store.upsert_many(chunks)
    return len(parsed_chunks)


def sync_blog_incremental(
    article: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    article_id = str(article.get("id") or article.get("articleId") or article.get("contentId"))
    vector_store = get_blog_vector_store()
    before = vector_store.scroll_documents({"articleId": article_id}, limit=1000)
    chunk_count = upsert_blog_document(
        article_id=article_id,
        title=article.get("title") or "",
        content=article.get("content") or "",
        summary=article.get("summary") or "",
        tags=article.get("tags"),
        metadata=metadata or article.get("metadata") or {},
    )
    after = vector_store.scroll_documents({"articleId": article_id}, limit=1000)
    before_hashes = {item["id"]: item.get("metadata", {}).get("contentHash") for item in before}
    after_hashes = {item["id"]: item.get("metadata", {}).get("contentHash") for item in after}
    changed = [chunk_id for chunk_id, value in after_hashes.items() if before_hashes.get(chunk_id) != value]
    deleted = [chunk_id for chunk_id in before_hashes if chunk_id not in after_hashes]
    return {
        "articleId": article_id,
        "chunkCount": chunk_count,
        "changedChunkIds": changed,
        "deletedChunkIds": deleted,
        "syncMode": "incremental",
    }


def _content_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
