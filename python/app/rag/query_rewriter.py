from __future__ import annotations

from app.infra.llm import llm_client


def rewrite_query(question: str, memory_context: dict | None = None) -> dict:
    fallback = {
        "original": question,
        "rewritten": question.strip(),
        "keywords": [part for part in question.replace("?", " ").replace("？", " ").replace("，", " ").split() if part][:8],
        "retrievalQueries": _fallback_retrieval_queries(question),
        "usedMemory": bool(memory_context and memory_context.get("turnCount")),
    }
    user_prompt = question
    if memory_context and memory_context.get("summary"):
        user_prompt = (
            "Conversation memory:\n"
            f"{memory_context['summary']}\n\n"
            f"Current question: {question}\n\n"
            "Rewrite the current question into standalone retrieval queries. Resolve pronouns like it/that/these."
        )
    return llm_client.complete_json(
        (
            "Plan retrieval for a blog RAG system. Return JSON with original, rewritten, keywords, "
            "retrievalQueries, usedMemory. retrievalQueries must be a deduplicated list of 1-4 short "
            "standalone search queries. For a question that combines components or asks whether one "
            "mechanism guarantees another outcome, make one query per required evidence facet. Preserve "
            "the user's terminology; do not invent products or facts."
        ),
        user_prompt,
        fallback,
    )


def is_complex_question(question: str) -> bool:
    """Whether independent evidence is likely needed to answer this question."""
    normalized = question.lower()
    markers = ("是否", "能否", "为什么", "但", "以及", "还是", "并发", "保证")
    return any(marker in question or marker in normalized for marker in markers)


def normalize_retrieval_queries(plan: dict, question: str) -> list[str]:
    """Validate model output and retain a deterministic fallback for degraded LLMs."""
    values = plan.get("retrievalQueries") if isinstance(plan, dict) else None
    model_queries = values if isinstance(values, list) else []
    candidates = [question.strip(), *[str(item).strip() for item in model_queries], *_fallback_retrieval_queries(question)]
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = " ".join(candidate.lower().split())
        if key and key not in seen:
            unique.append(candidate)
            seen.add(key)
    return unique[:4]


def _fallback_retrieval_queries(question: str) -> list[str]:
    """Cover common cross-component boundaries without relying on an LLM call."""
    normalized = question.lower()
    queries = [question.strip()]
    if "depends" in normalized and any(term in question for term in ("私有", "草稿", "权限", "管理员", "可见")):
        queries.append("私有草稿 权限过滤 角色 可见范围 向量检索 Qdrant")
    if "rabbitmq" in normalized and any(term in question for term in ("摘要", "索引", "并发", "向量")):
        queries.extend(("RabbitMQ 消费者 异步 耗时任务 发布解耦", "摘要 索引 依赖 顺序 并发 asyncio"))
    if "create_task" in normalized and any(term in question for term in ("摘要", "索引", "向量", "完成")):
        queries.append("asyncio create_task await 摘要 索引 依赖 顺序")
    return queries
