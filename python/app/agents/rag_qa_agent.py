from __future__ import annotations

import json

from app.infra.llm import llm_client
from app.rag.cache import build_answer_cache_key, rag_answer_cache
from app.rag.context import optimize_context_docs
from app.rag.evaluation import evaluate_rag
from app.rag.memory import build_memory_context, conversation_memory
from app.rag.observation import save_rag_observation
from app.rag.retriever import retrieve_blog_context
from app.rag.trace import finish_trace, new_trace


def ask_blog_knowledge(
    question: str,
    user_id: int | None,
    role: str,
    visible_scopes: list[str],
    session_id: str | None = None,
    save_observation: bool = True,
) -> dict:
    memory_context = build_memory_context(session_id, user_id)
    trace = new_trace(question)
    docs = retrieve_blog_context(question, user_id, role, visible_scopes, memory_context=memory_context, trace=trace)
    docs, context_report = optimize_context_docs(docs)
    if not docs:
        result = {
            "answer": "No sufficiently relevant content was found in the blog knowledge base.",
            "citations": [],
            "confidence": 0.0,
            "memory": memory_context,
            "contextOptimization": context_report,
            "retrievalTrace": finish_trace(trace, []),
            "evaluation": {"citationCount": 0, "hasCitations": False},
        }
        if save_observation:
            save_rag_observation(question, user_id, role, result)
        return result

    context = _build_context(docs)
    citations = _build_citations(docs)
    cache_key = build_answer_cache_key(question, role, visible_scopes, docs)
    cached = rag_answer_cache.get_answer(cache_key, question, role, visible_scopes, docs)
    if cached:
        result = {
            **cached,
            "memory": memory_context,
            "contextOptimization": context_report,
            "retrievalTrace": finish_trace(trace, docs),
            "cache": {
                "hit": True,
                "key": cache_key,
                "backend": rag_answer_cache.backend,
                "match": cached.get("cacheMatch"),
            },
        }
        memory_saved = conversation_memory.append(session_id, question, result.get("answer", ""), citations, user_id)
        result["memoryPersistence"] = {
            "saved": memory_saved,
            "backend": conversation_memory.backend,
        }
        if save_observation:
            save_rag_observation(question, user_id, role, result)
        return result

    answer = llm_client.complete(
        (
            "You are a blog knowledge-base RAG agent. Answer only from the provided context. "
            "If the context is insufficient, say so. Use citation markers like [1], [2]."
        ),
        f"Conversation memory:\n{memory_context.get('summary', '')}\n\nQuestion: {question}\n\nContext:\n{context}",
    )
    result = {
        "answer": answer,
        "citations": citations,
        "confidence": docs[0].get("rerankScore", docs[0]["score"]),
        "queryRewrite": docs[0].get("queryRewrite"),
        "memory": memory_context,
        "contextOptimization": context_report,
        "retrievalTrace": finish_trace(trace, docs),
        "evaluation": evaluate_rag(question, answer, docs),
        "cache": {"hit": False, "key": cache_key, "backend": rag_answer_cache.backend},
    }
    rag_answer_cache.set(
        cache_key,
        {
            "answer": result["answer"],
            "citations": result["citations"],
            "confidence": result["confidence"],
            "queryRewrite": result.get("queryRewrite"),
            "evaluation": result["evaluation"],
        },
        question,
        role,
        visible_scopes,
        docs,
    )
    memory_saved = conversation_memory.append(session_id, question, answer, citations, user_id)
    result["memoryPersistence"] = {
        "saved": memory_saved,
        "backend": conversation_memory.backend,
    }
    if save_observation:
        save_rag_observation(question, user_id, role, result)
    return result


def stream_blog_knowledge(
    question: str,
    user_id: int | None,
    role: str,
    visible_scopes: list[str],
    session_id: str | None = None,
):
    memory_context = build_memory_context(session_id, user_id)
    trace = new_trace(question)
    yield _sse("status", {"stage": "retrieving", "message": "Retrieving blog context", "memory": memory_context})
    docs = retrieve_blog_context(question, user_id, role, visible_scopes, memory_context=memory_context, trace=trace)
    docs, context_report = optimize_context_docs(docs)
    if not docs:
        result = {
            "answer": "No sufficiently relevant content was found in the blog knowledge base.",
            "citations": [],
            "confidence": 0.0,
            "memory": memory_context,
            "contextOptimization": context_report,
            "retrievalTrace": finish_trace(trace, []),
            "evaluation": {"citationCount": 0, "hasCitations": False},
        }
        save_rag_observation(question, user_id, role, result)
        yield _sse("token", {"content": result["answer"]})
        yield _sse("done", result)
        return

    context = _build_context(docs)
    citations = _build_citations(docs)
    cache_key = build_answer_cache_key(question, role, visible_scopes, docs)
    cached = rag_answer_cache.get_answer(cache_key, question, role, visible_scopes, docs)
    if cached:
        result = {
            **cached,
            "memory": memory_context,
            "contextOptimization": context_report,
            "retrievalTrace": finish_trace(trace, docs),
            "cache": {
                "hit": True,
                "key": cache_key,
                "backend": rag_answer_cache.backend,
                "match": cached.get("cacheMatch"),
            },
        }
        memory_saved = conversation_memory.append(session_id, question, result.get("answer", ""), citations, user_id)
        result["memoryPersistence"] = {
            "saved": memory_saved,
            "backend": conversation_memory.backend,
        }
        save_rag_observation(question, user_id, role, result)
        yield _sse(
            "citations",
            {
                "citations": result.get("citations", []),
                "queryRewrite": result.get("queryRewrite"),
                "contextOptimization": context_report,
                "retrievalTrace": result.get("retrievalTrace"),
                "cache": result.get("cache"),
            },
        )
        yield _sse("token", {"content": result.get("answer", "")})
        yield _sse("done", result)
        return

    yield _sse(
        "citations",
        {
            "citations": citations,
            "queryRewrite": docs[0].get("queryRewrite"),
            "contextOptimization": context_report,
            "retrievalTrace": finish_trace(trace, docs),
        },
    )

    answer_parts: list[str] = []
    for token in llm_client.stream_complete(
        (
            "You are a blog knowledge-base RAG agent. Answer only from the provided context. "
            "If the context is insufficient, say so. Use citation markers like [1], [2]."
        ),
        f"Conversation memory:\n{memory_context.get('summary', '')}\n\nQuestion: {question}\n\nContext:\n{context}",
    ):
        answer_parts.append(token)
        yield _sse("token", {"content": token})

    answer = "".join(answer_parts)
    result = {
        "answer": answer,
        "citations": citations,
        "confidence": docs[0].get("rerankScore", docs[0]["score"]),
        "queryRewrite": docs[0].get("queryRewrite"),
        "memory": memory_context,
        "contextOptimization": context_report,
        "retrievalTrace": finish_trace(trace, docs),
        "evaluation": evaluate_rag(question, answer, docs),
        "cache": {"hit": False, "key": cache_key, "backend": rag_answer_cache.backend},
    }
    rag_answer_cache.set(
        cache_key,
        {
            "answer": result["answer"],
            "citations": result["citations"],
            "confidence": result["confidence"],
            "queryRewrite": result.get("queryRewrite"),
            "evaluation": result["evaluation"],
        },
        question,
        role,
        visible_scopes,
        docs,
    )
    memory_saved = conversation_memory.append(session_id, question, answer, citations, user_id)
    result["memoryPersistence"] = {
        "saved": memory_saved,
        "backend": conversation_memory.backend,
    }
    save_rag_observation(question, user_id, role, result)
    yield _sse("done", result)


def _build_context(docs: list[dict]) -> str:
    return "\n\n".join(
        f"[{index + 1}] title={doc['metadata'].get('title')} "
        f"heading={doc['metadata'].get('heading')} type={doc['metadata'].get('chunkType')} "
        f"tokens={doc.get('estimatedTokens')}\n{doc['text']}"
        for index, doc in enumerate(docs)
    )


def _build_citations(docs: list[dict]) -> list[dict]:
    return [
        {
            "articleId": doc["metadata"].get("articleId"),
            "title": doc["metadata"].get("title"),
            "url": doc["metadata"].get("url"),
            "snippet": doc["text"][:180],
            "score": doc["score"],
            "rerankScore": doc.get("rerankScore"),
            "rerankModel": doc.get("rerankModel"),
            "chunkType": doc["metadata"].get("chunkType"),
            "heading": doc["metadata"].get("heading"),
            "source": doc.get("source"),
            "estimatedTokens": doc.get("estimatedTokens"),
        }
        for doc in docs
    ]


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
