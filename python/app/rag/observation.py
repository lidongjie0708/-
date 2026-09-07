from __future__ import annotations

import json
import math
import uuid
from typing import Any

from app.infra import mysql
from app.config import settings


def save_rag_observation(
    question: str,
    user_id: int | None,
    role: str,
    result: dict[str, Any],
) -> None:
    evaluation = result.get("evaluation") or {}
    citations = result.get("citations") or []
    sql = """
        INSERT INTO rag_observation_log (
            question,
            answer,
            user_id,
            role,
            confidence,
            citation_count,
            context_precision_lite,
            answer_grounding_lite,
            has_citations,
            query_rewrite_json,
            citations_json,
            context_optimization_json,
            retrieval_trace_json,
            cache_json,
            evaluation_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    params = (
        question,
        result.get("answer"),
        user_id,
        role,
        result.get("confidence"),
        evaluation.get("citationCount", len(citations)),
        evaluation.get("contextPrecisionLite"),
        evaluation.get("answerGroundingLite"),
        1 if evaluation.get("hasCitations") else 0,
        _json(result.get("queryRewrite")),
        _json(citations),
        _json(result.get("contextOptimization")),
        _json(result.get("retrievalTrace")),
        _json(result.get("cache")),
        _json(evaluation),
    )
    try:
        with mysql.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
    except Exception:
        # Observability must not break the user-facing RAG answer path.
        return


def _json(value: Any) -> str:
    return json.dumps(_json_safe(value or {}), ensure_ascii=False, allow_nan=False)


def _json_safe(value: Any) -> Any:
    """Make evaluator output safe for MySQL JSON columns.

    RAGAS may return NaN for an individual metric when one judge call fails.
    JSON columns reject NaN, so retain the run and persist that metric as null.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def create_evaluation_run(
    requested_framework: str,
    case_count: int,
    user_id: int | None,
    role: str,
    visible_scopes: list[str],
) -> str:
    run_id = str(uuid.uuid4())
    config = {
        "answerModel": settings.llm_model,
        "embeddingModel": settings.dashscope_embedding_model,
        "rerankModel": settings.dashscope_rerank_model,
        "vectorStore": settings.vector_store,
        "collection": settings.qdrant_collection if settings.vector_store == "qdrant" else None,
    }
    try:
        with mysql.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO rag_eval_run (
                        id, requested_framework, status, case_count, user_id, role,
                        visible_scopes_json, config_json
                    ) VALUES (%s, %s, 'RUNNING', %s, %s, %s, %s, %s)
                    """,
                    (run_id, requested_framework, case_count, user_id, role, _json(visible_scopes), _json(config)),
                )
        return run_id
    except Exception:
        # Evaluation may still be returned to the caller when observability storage is unavailable.
        return run_id


def save_evaluation_case_result(run_id: str, case_index: int, item: dict[str, Any], score: dict[str, Any]) -> None:
    evaluation = score or {}
    try:
        with mysql.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO rag_eval_case_result (
                        run_id, case_index, question, ground_truth, reference_answer,
                        expected_keywords_json, answer, contexts_json, citations_json,
                        faithfulness, answer_relevancy, context_precision, context_recall,
                        context_precision_lite, answer_grounding_lite, keyword_hit_rate,
                        has_citations, evaluation_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        run_id, case_index, item["question"], item.get("groundTruth"), item.get("reference"),
                        _json(item.get("expectedKeywords", [])), item.get("answer"), _json(item.get("contexts", [])),
                        _json(item.get("citations", [])), evaluation.get("faithfulness"),
                        evaluation.get("answer_relevancy"), evaluation.get("context_precision"),
                        evaluation.get("context_recall"), evaluation.get("contextPrecisionLite"),
                        evaluation.get("answerGroundingLite"), evaluation.get("keywordHitRate"),
                        1 if evaluation.get("hasCitations") else 0, _json(evaluation),
                    ),
                )
    except Exception:
        return


def finish_evaluation_run(run_id: str, evaluation: dict[str, Any], error_message: str | None = None) -> None:
    status = "FAILED" if error_message else "COMPLETED"
    try:
        with mysql.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE rag_eval_run
                    SET framework = %s, status = %s, summary_json = %s, fallback_reason = %s,
                        error_message = %s, finished_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (
                        evaluation.get("framework"), status, _json(evaluation.get("summary", {})),
                        evaluation.get("fallbackReason"), error_message, run_id,
                    ),
                )
    except Exception:
        return
