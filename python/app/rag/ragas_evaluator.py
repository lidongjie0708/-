from __future__ import annotations

import sys
import math
from types import ModuleType
from typing import Any

from app.config import settings
from app.infra.llm import build_openai_compatible_clients, llm_factory
from app.rag.evaluation import evaluate_rag
from app.rag.embeddings import embedding_client


RAGAS_METRIC_NAMES = [
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
]


def evaluate_with_ragas(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate RAG rows with RAGAS when installed, otherwise return lite metrics.

    ``rows`` use this shape:
    question, answer, contexts, ground_truth/reference.
    """
    if settings.rag_eval_framework.lower() != "ragas":
        return evaluate_with_lite(rows, reason="RAG_EVAL_FRAMEWORK is not ragas")
    try:
        return _evaluate_with_ragas_package(rows)
    except Exception as exc:
        lite = evaluate_with_lite(rows, reason=str(exc))
        lite["framework"] = "lite-fallback"
        lite["requestedFramework"] = "ragas"
        return lite


def _evaluate_with_ragas_package(rows: list[dict[str, Any]]) -> dict[str, Any]:
    _ensure_ragas_langchain_compatibility()
    from datasets import Dataset
    from ragas import evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

    clients = build_openai_compatible_clients()
    evaluator_llm = llm_factory(
        model=settings.evaluator_llm_model,
        client=clients["llm_client"],
        max_tokens=settings.evaluator_max_tokens,
    )
    evaluator_embeddings = DashScopeRagasEmbeddings()
    if evaluator_llm is None or evaluator_embeddings is None:
        raise RuntimeError("RAGAS evaluator LLM or embeddings are not configured")

    dataset = Dataset.from_list(
        [
            {
                "question": row["question"],
                "answer": row["answer"],
                "contexts": row["contexts"],
                "ground_truth": row.get("ground_truth") or row.get("reference") or "",
                "reference": row.get("reference") or row.get("ground_truth") or "",
            }
            for row in rows
        ]
    )
    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=LangchainLLMWrapper(evaluator_llm),
        embeddings=LangchainEmbeddingsWrapper(evaluator_embeddings),
    )
    scores = [_sanitize_score_row(row) for row in result.to_pandas().to_dict(orient="records")]
    return {
        "framework": "ragas",
        "llmModel": settings.evaluator_llm_model,
        "embeddingModel": settings.evaluator_embedding_model,
        "metrics": RAGAS_METRIC_NAMES,
        "scores": scores,
        "summary": _average_scores(scores),
    }


class DashScopeRagasEmbeddings:
    """LangChain-compatible adapter backed by the application's tested embedder.

    DashScope's native compatible endpoint rejects the payload emitted by
    ``OpenAIEmbeddings`` in this environment. Reusing the document/query
    embedding client keeps RAGAS and online retrieval on the same model/API path.
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return embedding_client.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return embedding_client.embed_query(text)


def _ensure_ragas_langchain_compatibility() -> None:
    """Bridge a RAGAS import still referencing LangChain Community's removed Vertex module.

    RAGAS imports ``ChatVertexAI`` only for an ``isinstance`` check. BlogsLike
    evaluates with OpenAI-compatible DeepSeek, so a marker class is sufficient
    until the upstream dependency removes this stale import.
    """
    try:
        from langchain_community.chat_models.vertexai import ChatVertexAI  # noqa: F401
    except ModuleNotFoundError as exc:
        if exc.name != "langchain_community.chat_models.vertexai":
            raise
        module_name = "langchain_community.chat_models.vertexai"
        if module_name not in sys.modules:
            compatibility_module = ModuleType(module_name)
            compatibility_module.ChatVertexAI = type("ChatVertexAI", (), {})
            sys.modules[module_name] = compatibility_module


def evaluate_with_lite(rows: list[dict[str, Any]], reason: str | None = None) -> dict[str, Any]:
    scores = []
    for row in rows:
        docs = [{"text": text, "metadata": {}, "score": 1.0} for text in row.get("contexts", [])]
        metrics = evaluate_rag(row["question"], row["answer"], docs)
        expected = row.get("expected_keywords") or []
        hits = [keyword for keyword in expected if keyword.lower() in row["answer"].lower()]
        metrics["keywordHitRate"] = round(len(hits) / max(len(expected), 1), 4) if expected else None
        metrics["hitKeywords"] = hits
        scores.append({"question": row["question"], **metrics})
    return {
        "framework": "lite",
        "fallbackReason": reason,
        "metrics": ["contextPrecisionLite", "answerGroundingLite", "hasCitations", "keywordHitRate"],
        "scores": scores,
        "summary": _average_scores(scores),
    }


def _average_scores(scores: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for row in scores:
        for key, value in row.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
                totals[key] = totals.get(key, 0.0) + float(value)
                counts[key] = counts.get(key, 0) + 1
    return {key: round(total / counts[key], 4) for key, total in totals.items() if counts.get(key)}


def _sanitize_score_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: None if isinstance(value, float) and not math.isfinite(value) else value
        for key, value in row.items()
    }
