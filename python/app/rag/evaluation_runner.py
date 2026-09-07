from __future__ import annotations

from typing import Any

from app.agents.rag_qa_agent import ask_blog_knowledge
from app.rag.eval_dataset import RagEvalCaseItem, normalize_eval_cases
from app.rag.observation import create_evaluation_run, finish_evaluation_run, save_evaluation_case_result
from app.rag.ragas_evaluator import evaluate_with_lite, evaluate_with_ragas


def run_rag_evaluation(
    cases: list[dict[str, Any]] | None,
    user_id: int | None,
    role: str,
    visible_scopes: list[str],
    framework: str = "ragas",
) -> dict[str, Any]:
    eval_cases = normalize_eval_cases(cases)
    run_id = create_evaluation_run(framework, len(eval_cases), user_id, role, visible_scopes)
    try:
        rows = []
        results = []
        for case in eval_cases:
            rag_result = ask_blog_knowledge(case.question, user_id, role, visible_scopes, save_observation=False)
            # RAGAS must judge the chunks actually supplied to generation, not a
            # caller-provided reference context or the 180-character UI snippets.
            contexts = rag_result.get("evaluationContexts") or [
                citation.get("snippet", "") for citation in rag_result.get("citations", [])
            ]
            rows.append(_to_ragas_row(case, rag_result, contexts))
            results.append(
                {
                    "question": case.question,
                    "answer": rag_result.get("answer", ""),
                    "citations": rag_result.get("citations", []),
                    "expectedKeywords": case.expected_keywords,
                    "groundTruth": case.ground_truth,
                    "reference": case.reference,
                    "contexts": contexts,
                    "rag": rag_result,
                }
            )
        evaluation = evaluate_with_ragas(rows) if framework == "ragas" else evaluate_with_lite(rows)
        for index, (item, score) in enumerate(zip(results, evaluation.get("scores", []))):
            item["evaluation"] = score
            save_evaluation_case_result(run_id, index, item, score)
        response = {
            "runId": run_id,
            "framework": evaluation.get("framework"),
            "requestedFramework": framework,
            "summary": evaluation.get("summary", {}),
            "metrics": evaluation.get("metrics", []),
            "fallbackReason": evaluation.get("fallbackReason"),
            "results": results,
        }
        finish_evaluation_run(run_id, evaluation)
        return response
    except Exception as exc:
        failure = {"framework": None, "summary": {}, "fallbackReason": None}
        finish_evaluation_run(run_id, failure, error_message=str(exc))
        raise


def _to_ragas_row(case: RagEvalCaseItem, rag_result: dict[str, Any], contexts: list[str]) -> dict[str, Any]:
    return {
        "question": case.question,
        "answer": rag_result.get("answer", ""),
        "contexts": [context for context in contexts if context],
        "ground_truth": case.ground_truth,
        "reference": case.reference or case.ground_truth,
        "expected_keywords": case.expected_keywords,
    }
