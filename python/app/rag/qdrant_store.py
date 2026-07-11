from __future__ import annotations

from typing import Any
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.config import settings
from app.rag.embeddings import embedding_client


class QdrantVectorStore:
    def __init__(self) -> None:
        # Qdrant is a local infrastructure dependency. Ignoring system proxy
        # variables prevents localhost requests from being sent to a proxy,
        # which otherwise surfaces as an empty 502 response on Windows.
        self.client = QdrantClient(
            url=settings.qdrant_url,
            prefer_grpc=False,
            trust_env=False,
        )
        self.collection = settings.qdrant_collection

    def upsert_many(self, chunks: list[dict[str, Any]]) -> None:
        if not chunks:
            return
        vectors = embedding_client.embed_documents([chunk["text"] for chunk in chunks])
        self._ensure_collection(len(vectors[0]))
        points = []
        for chunk, vector in zip(chunks, vectors):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk["id"]))
            payload = {**chunk["metadata"], "text": chunk["text"], "chunkId": chunk["id"]}
            points.append(models.PointStruct(id=point_id, vector=vector, payload=payload))
        self.client.upsert(collection_name=self.collection, points=points)

    def delete(self, article_id: str | None = None, chunk_id: str | None = None) -> None:
        conditions = []
        if article_id is not None:
            conditions.append(models.FieldCondition(key="articleId", match=models.MatchValue(value=str(article_id))))
        if chunk_id is not None:
            conditions.append(models.FieldCondition(key="chunkId", match=models.MatchValue(value=chunk_id)))
        if not conditions:
            return
        self._ensure_collection()
        self.client.delete(
            collection_name=self.collection,
            points_selector=models.FilterSelector(filter=models.Filter(must=conditions)),
        )

    def vector_search(self, query: str, top_k: int, filters: dict[str, Any]) -> list[dict[str, Any]]:
        vector = embedding_client.embed_query(query)
        self._ensure_collection(len(vector))
        hits = self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            query_filter=self._to_qdrant_filter(filters),
            limit=top_k,
            with_payload=True,
        )
        return [self._hit_to_doc(hit, "vector") for hit in hits]

    def scroll_documents(self, filters: dict[str, Any], limit: int = 1000) -> list[dict[str, Any]]:
        self._ensure_collection()
        points, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=self._to_qdrant_filter(filters),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return [self._point_to_doc(point, "bm25") for point in points]

    def _ensure_collection(self, vector_size: int | None = None) -> None:
        existing = {item.name for item in self.client.get_collections().collections}
        if self.collection in existing:
            return
        if vector_size is None:
            vector_size = len(embedding_client.embed_query("collection init"))
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )

    def _to_qdrant_filter(self, filters: dict[str, Any]) -> models.Filter:
        must: list[models.FieldCondition] = []
        if filters.get("status"):
            must.append(models.FieldCondition(key="status", match=models.MatchAny(any=filters["status"])))
        if filters.get("visibleScopes"):
            must.append(models.FieldCondition(key="visibility", match=models.MatchAny(any=filters["visibleScopes"])))
        if filters.get("articleId"):
            must.append(models.FieldCondition(key="articleId", match=models.MatchValue(value=str(filters["articleId"]))))
        return models.Filter(must=must)

    def _hit_to_doc(self, hit: Any, source: str) -> dict[str, Any]:
        payload = hit.payload or {}
        return {
            "id": payload.get("chunkId", str(hit.id)),
            "text": payload.get("text", ""),
            "metadata": {key: value for key, value in payload.items() if key != "text"},
            "score": float(hit.score or 0.0),
            "source": source,
        }

    def _point_to_doc(self, point: Any, source: str) -> dict[str, Any]:
        payload = point.payload or {}
        return {
            "id": payload.get("chunkId", str(point.id)),
            "text": payload.get("text", ""),
            "metadata": {key: value for key, value in payload.items() if key != "text"},
            "score": 0.0,
            "source": source,
        }


qdrant_store = QdrantVectorStore()
