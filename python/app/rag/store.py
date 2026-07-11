from __future__ import annotations

from typing import Any

from app.config import settings


def get_blog_vector_store() -> Any:
    if settings.vector_store.lower() == "qdrant":
        from app.rag.qdrant_store import qdrant_store

        return qdrant_store

    from app.rag.vector_store import vector_store

    return vector_store
