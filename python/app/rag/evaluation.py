from __future__ import annotations

from app.rag.bm25 import tokenize


def evaluate_rag(question: str, answer: str, docs: list[dict]) -> dict:
    query_terms = set(tokenize(question))
    answer_terms = set(tokenize(answer))
    context = " ".join(doc.get("text", "") for doc in docs)
    context_terms = set(tokenize(context))
    citation_count = len(docs)
    context_precision = len(query_terms & context_terms) / max(len(query_terms), 1)
    answer_grounding = len(answer_terms & context_terms) / max(len(answer_terms), 1)
    return {
        "citationCount": citation_count,
        "contextPrecisionLite": round(context_precision, 4),
        "answerGroundingLite": round(answer_grounding, 4),
        "hasCitations": citation_count > 0,
    }
