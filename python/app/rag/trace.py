from __future__ import annotations

import time
import uuid
from copy import deepcopy
from typing import Any

from app.config import settings


def new_trace(question: str) -> dict[str, Any]:
    return {
        "traceId": f"rag-{uuid.uuid4().hex[:12]}",
        "question": question,
        "startedAt": time.time(),
        "stages": [],
    }


def add_trace_stage(trace: dict[str, Any] | None, stage: str, payload: dict[str, Any]) -> None:
    if trace is None:
        return
    trace.setdefault("stages", []).append({"stage": stage, "ts": time.time(), **payload})


def finish_trace(trace: dict[str, Any] | None, docs: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    if trace is None:
        return None
    snapshot = deepcopy(trace)
    snapshot["latencyMs"] = round((time.time() - snapshot.get("startedAt", time.time())) * 1000, 2)
    if docs is not None:
        snapshot["finalDocs"] = summarize_docs(docs)
    return snapshot


def summarize_docs(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sample = []
    for doc in docs[: settings.rag_trace_sample_docs]:
        metadata = doc.get("metadata", {})
        sample.append(
            {
                "id": doc.get("id"),
                "articleId": metadata.get("articleId"),
                "title": metadata.get("title"),
                "chunkIndex": metadata.get("chunkIndex"),
                "chunkType": metadata.get("chunkType"),
                "score": doc.get("score"),
                "rerankScore": doc.get("rerankScore"),
                "source": doc.get("source"),
            }
        )
    return sample
