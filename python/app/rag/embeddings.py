from __future__ import annotations

from collections import Counter
import math
import re

import requests

from app.config import settings


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())


def _hash_embedding(text: str, dim: int = 1024) -> list[float]:
    counts = Counter(_tokens(text))
    vector = [0.0] * dim
    for token, count in counts.items():
        vector[hash(token) % dim] += float(count)
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


class DashScopeEmbeddingClient:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not settings.dashscope_api_key:
            return [_hash_embedding(text) for text in texts]

        response = requests.post(
            f"{settings.dashscope_base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {settings.dashscope_api_key}",
                "Content-Type": "application/json",
            },
            json={"model": settings.dashscope_embedding_model, "input": texts},
            timeout=settings.dashscope_embedding_timeout,
        )
        response.raise_for_status()
        data = response.json()["data"]
        return [item["embedding"] for item in sorted(data, key=lambda row: row["index"])]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


embedding_client = DashScopeEmbeddingClient()
