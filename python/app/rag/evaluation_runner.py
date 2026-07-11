from __future__ import annotations

from typing import Any

from app.agents.rag_qa_agent import ask_blog_knowledge
from app.rag.eval_dataset import RagEvalCaseItem, normalize_eval_cases
from app.rag.observation import save_rag_observation
from app.rag.ragas_evaluator import evaluate_with_lite, evaluate_with_ragas


def run_rag_evaluation(
    cases: list[dict[str, Any]] | None,
    user_id: int | None,
    role: str,
    visible_scopes: list[str],
    framework: str = "ragas",
) -> dict[str, Any]:
    eval_cases = normalize_eval_cases(cases)
    rows = []
    results = []
    for case in eval_cases:
        rag_result = ask_blog_knowledge(case.question, user_id, role, visible_scopes, save_observation=False)
        contexts = case.contexts or [citation.get("snippet", "") for citation in rag_result.get("citations", [])]
        row = _to_ragas_row(case, rag_result, contexts)
        rows.append(row)
        results.append(
            {
                "question": case.question,
                "answer": rag_result.get("answer", ""),
                "citations": rag_result.get("citations", []),
                "expectedKeywords": case.expected_keywords,
                "groundTruth": case.ground_truth,
                "reference": case.reference,
                "rag": rag_result,
            }
        )
    evaluation = evaluate_with_ragas(rows) if framework == "ragas" else evaluate_with_lite(rows)
    for item, score in zip(results, evaluation.get("scores", [])):
        item["evaluation"] = score
        save_rag_observation(
            item["question"],
            user_id,
            role,
            {"answer": item["answer"], "citations": item["citations"], "evaluation": score},
            keyword_hit_rate=score.get("keywordHitRate"),
        )
    return {
        "framework": evaluation.get("framework"),
        "requestedFramework": framework,
        "summary": evaluation.get("summary", {}),
        "metrics": evaluation.get("metrics", []),
        "fallbackReason": evaluation.get("fallbackReason"),
        "results": results,
    }


def _to_ragas_row(case: RagEvalCaseItem, rag_result: dict[str, Any], contexts: list[str]) -> dict[str, Any]:
    return {
        "question": case.question,
        "answer": rag_result.get("answer", ""),
        "contexts": [context for context in contexts if context],
        "ground_truth": case.ground_truth,
        "reference": case.reference or case.ground_truth,
        "expected_keywords": case.expected_keywords,
    }
