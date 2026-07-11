from __future__ import annotations

import json
from typing import Any

from app.infra import mysql


def save_rag_observation(
    question: str,
    user_id: int | None,
    role: str,
    result: dict[str, Any],
    keyword_hit_rate: float | None = None,
) -> None:
    evaluation = result.get("evaluation") or {}
    citations = result.get("citations") or []
    sql = """
        INSERT INTO rag_eval_log (
            question,
            answer,
            user_id,
            role,
            confidence,
            citation_count,
            context_precision_lite,
            answer_grounding_lite,
            has_citations,
            keyword_hit_rate,
            query_rewrite_json,
            citations_json,
            evaluation_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        keyword_hit_rate,
        _json(result.get("queryRewrite")),
        _json(citations),
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
    return json.dumps(value or {}, ensure_ascii=False)
