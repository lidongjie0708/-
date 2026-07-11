from __future__ import annotations

from app.infra.llm import llm_client


def rewrite_query(question: str, memory_context: dict | None = None) -> dict:
    fallback = {
        "original": question,
        "rewritten": question.strip(),
        "keywords": [part for part in question.replace("?", " ").replace("，", " ").split() if part][:8],
        "usedMemory": bool(memory_context and memory_context.get("turnCount")),
    }
    user_prompt = question
    if memory_context and memory_context.get("summary"):
        user_prompt = (
            "Conversation memory:\n"
            f"{memory_context['summary']}\n\n"
            f"Current question: {question}\n\n"
            "Rewrite the current question into a standalone retrieval query. Resolve pronouns like it/that/these."
        )
    return llm_client.complete_json(
        "Rewrite the user query for blog RAG retrieval. Return JSON with original, rewritten, keywords, usedMemory.",
        user_prompt,
        fallback,
    )
