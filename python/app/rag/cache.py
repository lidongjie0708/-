from __future__ import annotations

import hashlib
import json
import math
from array import array
import time
from typing import Any

from app.config import settings
from app.rag.embeddings import embedding_client


class RagAnswerCache:
    VECTOR_INDEX_NAME = "idx:blogslike:rag:semantic"
    VECTOR_DOC_PREFIX = "blogslike:rag:semantic:doc:"

    def __init__(self) -> None:
        self._redis = self._create_redis_client()
        self._redis_vector = self._create_redis_client(decode_responses=False)
        self._vector_index_ready = False

    def _create_redis_client(self, decode_responses: bool = True):
        try:
            from redis import Redis

            return Redis.from_url(
                settings.redis_url,
                decode_responses=decode_responses,
                socket_connect_timeout=1,
                socket_timeout=1,
                health_check_interval=30,
            )
        except Exception:
            return None

    def get(self, key: str) -> dict[str, Any] | None:
        if not settings.rag_answer_cache_enabled or self._redis is None:
            return None
        try:
            raw = self._redis.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def get_answer(
        self,
        key: str,
        question: str,
        role: str,
        visible_scopes: list[str],
        docs: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        exact = self.get(key)
        if exact:
            exact["cacheMatch"] = {"type": "exact", "score": 1.0}
            return exact
        return self.semantic_get(question, role, visible_scopes, docs)

    def set(
        self,
        key: str,
        value: dict[str, Any],
        question: str | None = None,
        role: str | None = None,
        visible_scopes: list[str] | None = None,
        docs: list[dict[str, Any]] | None = None,
    ) -> bool:
        if not settings.rag_answer_cache_enabled or self._redis is None:
            return False
        try:
            self._redis.setex(
                key,
                settings.rag_answer_cache_ttl_seconds,
                json.dumps(value, ensure_ascii=False, default=str),
            )
            if question and role and visible_scopes is not None and docs is not None:
                self.semantic_set(key, question, role, visible_scopes, docs)
            return True
        except Exception:
            return False

    def semantic_get(
        self,
        question: str,
        role: str,
        visible_scopes: list[str],
        docs: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if (
            not settings.rag_answer_cache_enabled
            or not settings.rag_semantic_cache_enabled
            or self._redis is None
        ):
            return None
        try:
            namespace = build_semantic_cache_namespace(role, visible_scopes, docs)
            query_vector = embedding_client.embed_query(_normalize_question(question))
            stack_match = self._redis_stack_vector_get(namespace, query_vector)
            if stack_match:
                return stack_match
            index_key = f"blogslike:rag:semantic:index:{namespace}"
            candidate_keys = self._redis.zrevrange(index_key, 0, max(settings.rag_semantic_cache_max_entries - 1, 0))
            best: tuple[float, str, dict[str, Any]] | None = None
            for candidate_key in candidate_keys:
                raw_meta = self._redis.get(f"{candidate_key}:semantic")
                raw_value = self._redis.get(candidate_key)
                if not raw_meta or not raw_value:
                    self._redis.zrem(index_key, candidate_key)
                    continue
                meta = json.loads(raw_meta)
                score = _cosine(query_vector, meta.get("questionVector") or [])
                if score >= settings.rag_semantic_cache_threshold and (best is None or score > best[0]):
                    best = (score, candidate_key, json.loads(raw_value))
            if not best:
                return None
            score, candidate_key, value = best
            value["cacheMatch"] = {
                "type": "semantic",
                "score": round(score, 6),
                "matchedKey": candidate_key,
            }
            return value
        except Exception:
            return None

    def semantic_set(
        self,
        key: str,
        question: str,
        role: str,
        visible_scopes: list[str],
        docs: list[dict[str, Any]],
    ) -> bool:
        if (
            not settings.rag_answer_cache_enabled
            or not settings.rag_semantic_cache_enabled
            or self._redis is None
        ):
            return False
        try:
            namespace = build_semantic_cache_namespace(role, visible_scopes, docs)
            vector = embedding_client.embed_query(_normalize_question(question))
            self._redis_stack_vector_set(key, namespace, question, role, visible_scopes, docs, vector)
            index_key = f"blogslike:rag:semantic:index:{namespace}"
            meta_key = f"{key}:semantic"
            meta = {
                "question": question,
                "questionVector": vector,
                "role": role.upper(),
                "visibleScopes": sorted(scope.upper() for scope in visible_scopes),
                "docFingerprint": build_doc_fingerprint(docs),
                "createdAt": int(time.time()),
            }
            pipeline = self._redis.pipeline(transaction=True)
            pipeline.setex(
                meta_key,
                settings.rag_answer_cache_ttl_seconds,
                json.dumps(meta, ensure_ascii=False, default=str),
            )
            pipeline.zadd(index_key, {key: time.time()})
            pipeline.expire(index_key, settings.rag_answer_cache_ttl_seconds)
            overflow = settings.rag_semantic_cache_max_entries
            if overflow > 0:
                pipeline.zremrangebyrank(index_key, 0, -(overflow + 1))
            pipeline.execute()
            return True
        except Exception:
            return False

    def _redis_stack_vector_get(self, namespace: str, query_vector: list[float]) -> dict[str, Any] | None:
        if (
            settings.rag_semantic_cache_backend not in {"redis8", "redis", "redis-stack", "stack", "auto"}
            or self._redis is None
            or self._redis_vector is None
            or len(query_vector) != settings.rag_semantic_cache_vector_dim
        ):
            return None
        if not self._ensure_vector_index():
            return None
        try:
            from redis.commands.search.query import Query

            top_k = max(settings.rag_semantic_cache_vector_candidates, 1)
            query = (
                Query(
                    f"(@namespace:{{{_escape_tag_value(namespace)}}})=>"
                    f"[KNN {top_k} @question_vector $query_vector AS distance]"
                )
                .sort_by("distance")
                .return_fields("answer_key", "distance")
                .paging(0, top_k)
                .dialect(2)
            )
            result = self._redis_vector.ft(self.VECTOR_INDEX_NAME).search(
                query,
                query_params={"query_vector": _vector_bytes(query_vector)},
            )
            best: tuple[float, str, dict[str, Any]] | None = None
            for doc in result.docs:
                answer_key = _decode(getattr(doc, "answer_key", ""))
                raw_distance = getattr(doc, "distance", None)
                if not answer_key or raw_distance is None:
                    continue
                similarity = 1.0 - float(raw_distance)
                raw_value = self._redis.get(answer_key)
                if raw_value and similarity >= settings.rag_semantic_cache_threshold:
                    value = json.loads(raw_value)
                    if best is None or similarity > best[0]:
                        best = (similarity, answer_key, value)
            if not best:
                return None
            similarity, answer_key, value = best
            value["cacheMatch"] = {
                "type": "semantic-vector",
                "backend": "redis8",
                "score": round(similarity, 6),
                "matchedKey": answer_key,
            }
            return value
        except Exception:
            return None

    def _redis_stack_vector_set(
        self,
        key: str,
        namespace: str,
        question: str,
        role: str,
        visible_scopes: list[str],
        docs: list[dict[str, Any]],
        vector: list[float],
    ) -> bool:
        if (
            settings.rag_semantic_cache_backend not in {"redis8", "redis", "redis-stack", "stack", "auto"}
            or self._redis_vector is None
            or len(vector) != settings.rag_semantic_cache_vector_dim
        ):
            return False
        if not self._ensure_vector_index():
            return False
        try:
            doc_key = f"{self.VECTOR_DOC_PREFIX}{_cache_key_digest(key)}"
            mapping = {
                "namespace": namespace,
                "answer_key": key,
                "question": question,
                "role": role.upper(),
                "visible_scopes": json.dumps(sorted(scope.upper() for scope in visible_scopes), ensure_ascii=False),
                "doc_fingerprint": json.dumps(build_doc_fingerprint(docs), ensure_ascii=False, default=str),
                "created_at": str(int(time.time())),
                "question_vector": _vector_bytes(vector),
            }
            pipeline = self._redis_vector.pipeline(transaction=True)
            pipeline.hset(doc_key, mapping=mapping)
            pipeline.expire(doc_key, settings.rag_answer_cache_ttl_seconds)
            pipeline.execute()
            return True
        except Exception:
            return False

    def _ensure_vector_index(self) -> bool:
        if self._vector_index_ready:
            return True
        if self._redis_vector is None:
            return False
        try:
            try:
                self._redis_vector.ft(self.VECTOR_INDEX_NAME).info()
                self._vector_index_ready = True
                return True
            except Exception:
                pass
            from redis.commands.search.field import TagField, TextField, VectorField
            from redis.commands.search.indexDefinition import IndexDefinition, IndexType

            schema = (
                TagField("namespace"),
                TextField("answer_key"),
                TextField("question"),
                TagField("role"),
                VectorField(
                    "question_vector",
                    "FLAT",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": settings.rag_semantic_cache_vector_dim,
                        "DISTANCE_METRIC": "COSINE",
                    },
                ),
            )
            definition = IndexDefinition(prefix=[self.VECTOR_DOC_PREFIX], index_type=IndexType.HASH)
            self._redis_vector.ft(self.VECTOR_INDEX_NAME).create_index(schema, definition=definition)
            self._vector_index_ready = True
            return True
        except Exception:
            return False

    @property
    def backend(self) -> str:
        if self._redis is not None:
            try:
                if self._redis.ping():
                    return "redis"
            except Exception:
                pass
        return "disabled"


rag_answer_cache = RagAnswerCache()


def build_answer_cache_key(
    question: str,
    role: str,
    visible_scopes: list[str],
    docs: list[dict[str, Any]],
) -> str:
    payload = {
        "question": _normalize_question(question),
        "role": role.upper(),
        "visibleScopes": sorted(scope.upper() for scope in visible_scopes),
        "docs": build_doc_fingerprint(docs),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()
    return f"blogslike:rag:answer:{digest}"


def build_semantic_cache_namespace(role: str, visible_scopes: list[str], docs: list[dict[str, Any]]) -> str:
    payload = {
        "role": role.upper(),
        "visibleScopes": sorted(scope.upper() for scope in visible_scopes),
        "docs": build_doc_fingerprint(docs),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def build_doc_fingerprint(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": doc.get("id"),
            "hash": doc.get("metadata", {}).get("contentHash"),
            "score": round(float(doc.get("rerankScore", doc.get("score", 0.0)) or 0.0), 4),
        }
        for doc in docs[: settings.rag_rerank_top_k]
    ]


def _normalize_question(question: str) -> str:
    return " ".join(question.lower().split())


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def _vector_bytes(vector: list[float]) -> bytes:
    return array("f", (float(value) for value in vector)).tobytes()


def _escape_tag_value(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace(",", "\\,")
        .replace(" ", "\\ ")
    )


def _decode(value: Any) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def _cache_key_digest(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
