from __future__ import annotations

import re
from typing import Any

from app.rag.parser import ParsedBlock, parse_blog_content


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def build_blog_chunks(
    title: str,
    content: str,
    summary: str = "",
    tags: str = "",
    chunk_size: int = 900,
    overlap: int = 120,
) -> list[dict[str, Any]]:
    blocks = parse_blog_content(title, summary, tags, content)
    chunks: list[dict[str, Any]] = []
    for block in blocks:
        if block.block_type in {"code", "image"}:
            chunks.append(_chunk_payload(block.text, block, 0))
            continue
        for index, piece in enumerate(split_text(block.text, chunk_size=chunk_size, overlap=overlap)):
            chunks.append(_chunk_payload(piece, block, index))
    return chunks


def _chunk_payload(text: str, block: ParsedBlock, block_chunk_index: int) -> dict[str, Any]:
    return {
        "text": clean_text(text),
        "chunkType": block.block_type,
        "heading": block.metadata.get("heading"),
        "language": block.metadata.get("language"),
        "imageAlt": block.metadata.get("imageAlt"),
        "imageSrc": block.metadata.get("imageSrc"),
        "blockChunkIndex": block_chunk_index,
    }
