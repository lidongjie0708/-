from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _llm_provider() -> str:
    return os.getenv("AGENT_LLM_PROVIDER", "deepseek").strip().lower()


def _llm_model() -> str:
    if _llm_provider() == "dashscope":
        return os.getenv("AGENT_MODEL", "qwen-plus").strip()
    return os.getenv("AGENT_MODEL", "deepseek-chat").strip()


def _llm_api_key() -> str:
    if _llm_provider() == "dashscope":
        return os.getenv("DASHSCOPE_API_KEY", "").strip()
    return os.getenv("DEEPSEEK_API_KEY", "").strip()


def _llm_base_url() -> str:
    if _llm_provider() == "dashscope":
        return os.getenv(
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ).rstrip("/")
    return os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("AGENT_APP_NAME", "BlogsLike Agent Service")
    debug: bool = _bool("AGENT_DEBUG", True)
    cors_origins: str = os.getenv("AGENT_CORS_ORIGINS", "*")

    jwt_secret: str = os.getenv("JWT_SECRET", "").strip()
    ai_token_required: bool = _bool("AI_TOKEN_REQUIRED", True)
    internal_agent_token: str = os.getenv("INTERNAL_AGENT_TOKEN", "").strip()
    internal_agent_token_required: bool = _bool("INTERNAL_AGENT_TOKEN_REQUIRED", True)

    model: str = os.getenv("AGENT_MODEL", "deepseek-chat")
    temperature: float = _float("AGENT_TEMPERATURE", 0.2)

    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "").strip()
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "").rstrip("/")
    llm_provider: str = _llm_provider()
    llm_model: str = _llm_model()
    llm_api_key: str = _llm_api_key()
    llm_base_url: str = _llm_base_url()
    llm_timeout: int = _int("AGENT_LLM_TIMEOUT_SECONDS", 60)
    evaluator_llm_model: str = os.getenv(
        "RAGAS_EVALUATOR_LLM_MODEL",
        "qwen-plus" if _llm_provider() == "dashscope" else "deepseek-chat",
    )
    evaluator_embedding_model: str = os.getenv("RAGAS_EVALUATOR_EMBEDDING_MODEL", "text-embedding-v3")
    evaluator_max_tokens: int = _int(
        "RAGAS_EVALUATOR_MAX_TOKENS",
        8192 if _llm_provider() == "dashscope" else 384000,
    )
    rag_eval_framework: str = os.getenv("RAG_EVAL_FRAMEWORK", "ragas")

    mysql_host: str = os.getenv("MYSQL_HOST", "localhost")
    mysql_port: int = _int("MYSQL_PORT", 3306)
    mysql_user: str = os.getenv("MYSQL_USER", "root")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "")
    mysql_database: str = os.getenv("MYSQL_DATABASE", "thumb_db")

    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6380/0")
    conversation_ttl_seconds: int = _int("CONVERSATION_TTL_SECONDS", 86400)

    vector_store: str = os.getenv("VECTOR_STORE", "memory")
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "blog_chunks")

    rag_top_k: int = _int("RAG_TOP_K", 5)
    rag_min_score: float = _float("RAG_MIN_SCORE", 0.15)
    rag_vector_top_k: int = _int("RAG_VECTOR_TOP_K", 15)
    rag_bm25_top_k: int = _int("RAG_BM25_TOP_K", 15)
    rag_rrf_k: int = _int("RAG_RRF_K", 60)
    # Bound the payload sent to a remote reranker after multi-query fusion.
    rag_rrf_candidate_top_k: int = _int("RAG_RRF_CANDIDATE_TOP_K", 40)
    # Four focused chunks normally cover a multi-hop answer while avoiding low-ranked noise.
    rag_rerank_top_k: int = _int("RAG_RERANK_TOP_K", 4)
    rag_context_token_budget: int = _int("RAG_CONTEXT_TOKEN_BUDGET", 2800)
    rag_max_chunks_per_article: int = _int("RAG_MAX_CHUNKS_PER_ARTICLE", 2)
    rag_memory_turns: int = _int("RAG_MEMORY_TURNS", 6)
    rag_trace_sample_docs: int = _int("RAG_TRACE_SAMPLE_DOCS", 8)
    rag_query_rewrite_mode: str = os.getenv("RAG_QUERY_REWRITE_MODE", "auto").strip().lower()
    rag_remote_rerank_mode: str = os.getenv("RAG_REMOTE_RERANK_MODE", "auto").strip().lower()
    rag_remote_rerank_margin: float = _float("RAG_REMOTE_RERANK_MARGIN", 0.08)
    rag_remote_rerank_min_score: float = _float("RAG_REMOTE_RERANK_MIN_SCORE", 0.45)
    rag_remote_min_score: float = _float("RAG_REMOTE_MIN_SCORE", 0.10)
    rag_remote_score_ratio: float = _float("RAG_REMOTE_SCORE_RATIO", 0.35)
    rag_answer_cache_enabled: bool = _bool("RAG_ANSWER_CACHE_ENABLED", True)
    rag_answer_cache_ttl_seconds: int = _int("RAG_ANSWER_CACHE_TTL_SECONDS", 1800)
    rag_semantic_cache_enabled: bool = _bool("RAG_SEMANTIC_CACHE_ENABLED", True)
    rag_semantic_cache_threshold: float = _float("RAG_SEMANTIC_CACHE_THRESHOLD", 0.88)
    rag_semantic_cache_max_entries: int = _int("RAG_SEMANTIC_CACHE_MAX_ENTRIES", 200)
    rag_semantic_cache_backend: str = os.getenv("RAG_SEMANTIC_CACHE_BACKEND", "redis8").strip().lower()
    rag_semantic_cache_vector_dim: int = _int("RAG_SEMANTIC_CACHE_VECTOR_DIM", 1024)
    rag_semantic_cache_vector_candidates: int = _int("RAG_SEMANTIC_CACHE_VECTOR_CANDIDATES", 8)
    rag_long_term_memory_enabled: bool = _bool("RAG_LONG_TERM_MEMORY_ENABLED", True)
    rag_memory_summary_every_turns: int = _int("RAG_MEMORY_SUMMARY_EVERY_TURNS", 6)
    rag_memory_summary_max_chars: int = _int("RAG_MEMORY_SUMMARY_MAX_CHARS", 1600)
    rag_memory_summary_async_enabled: bool = _bool("RAG_MEMORY_SUMMARY_ASYNC_ENABLED", True)
    rag_memory_summary_worker_poll_seconds: int = _int("RAG_MEMORY_SUMMARY_WORKER_POLL_SECONDS", 5)
    rag_memory_summary_worker_batch_size: int = _int("RAG_MEMORY_SUMMARY_WORKER_BATCH_SIZE", 2)

    analytics_max_join_count: int = _int("ANALYTICS_MAX_JOIN_COUNT", 2)
    analytics_max_group_by_fields: int = _int("ANALYTICS_MAX_GROUP_BY_FIELDS", 3)
    analytics_max_sql_count: int = _int("ANALYTICS_MAX_SQL_COUNT", 3)
    analytics_max_tool_rounds: int = _int("ANALYTICS_MAX_TOOL_ROUNDS", 5)
    analytics_low_cost_mode: bool = _bool("ANALYTICS_LOW_COST_MODE", True)
    analytics_tool_loop_enabled: bool = _bool("ANALYTICS_TOOL_LOOP_ENABLED", True)
    analytics_llm_report_enabled: bool = _bool("ANALYTICS_LLM_REPORT_ENABLED", False)
    analytics_memory_enabled: bool = _bool("ANALYTICS_MEMORY_ENABLED", True)
    analytics_memory_llm_consolidation: bool = _bool("ANALYTICS_MEMORY_LLM_CONSOLIDATION", True)
    analytics_short_memory_turns: int = _int("ANALYTICS_SHORT_MEMORY_TURNS", 6)
    analytics_long_memory_top_k: int = _int("ANALYTICS_LONG_MEMORY_TOP_K", 5)
    analytics_long_memory_min_importance: float = _float("ANALYTICS_LONG_MEMORY_MIN_IMPORTANCE", 0.5)
    analytics_context_l1_budget: int = _int("ANALYTICS_CONTEXT_L1_BUDGET", 600)
    analytics_context_l2_budget: int = _int("ANALYTICS_CONTEXT_L2_BUDGET", 800)
    analytics_template_verify: bool = _bool("ANALYTICS_TEMPLATE_VERIFY", True)
    analytics_template_verify_timeout: int = _int("ANALYTICS_TEMPLATE_VERIFY_TIMEOUT", 8)

    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "").strip()
    dashscope_base_url: str = os.getenv(
        "DASHSCOPE_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ).rstrip("/")
    dashscope_embedding_model: str = os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v4")
    dashscope_embedding_timeout: int = _int("DASHSCOPE_EMBEDDING_TIMEOUT", 30)

    dashscope_rerank_api_key: str = (
        os.getenv("DASHAPI")
        or os.getenv("dashapi")
        or os.getenv("DASHSCOPE_RERANK_API_KEY")
        or dashscope_api_key
    ).strip()
    dashscope_rerank_base_url: str = os.getenv(
        "DASHSCOPE_RERANK_BASE_URL",
        "https://dashscope.aliyuncs.com",
    ).rstrip("/")
    dashscope_rerank_model: str = os.getenv("DASHSCOPE_RERANK_MODEL", "Qwen3-Reranker-4B")
    dashscope_rerank_timeout: int = _int("DASHSCOPE_RERANK_TIMEOUT", 30)


settings = Settings()
