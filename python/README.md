# BlogsLike Agent Service

FastAPI service for the blog AI Agent features:

- RAG question answering over blog content
- Writing assistant
- SEO optimizer
- Content audit
- Admin analytics with safe SQL
- LangGraph multi-agent article workflow

## Run

```bash
cd python
uv sync
copy .env .env
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Java can call the compatible endpoint:

```text
POST http://localhost:8001/api/agent/execute
```

New feature endpoints are available under `/api/agent/*`.

## Split Java/Python Streaming

Keep normal business traffic on Java and send streaming AI traffic directly to Python:

```text
Normal business:
frontend -> Java Spring Boot

Non-streaming background AI:
Java Spring Boot -> Python FastAPI

Streaming AI:
frontend -> Python FastAPI
```

Java issues a short-lived AI token after the user logs in:

```text
POST /api/agent/token
Authorization: Bearer <java-login-jwt>
```

Use the returned token to call the Python SSE endpoint:

```text
POST http://localhost:8001/api/agent/rag/ask/stream
Authorization: Bearer <ai-token>
Content-Type: application/json

{"question":"...", "visibleScopes":["PUBLIC"]}
```

The stream emits SSE events:

```text
event: status
event: citations
event: token
event: done
```

Python verifies the Java-issued AI token with the shared base64 `JWT_SECRET`.

## RAG Pipeline

The current RAG flow is:

```text
blog title/summary/tags/content
 -> parse Markdown/HTML images and fenced code blocks
 -> structure-aware chunking
 -> DashScope text-embedding-v4
 -> Qdrant on http://localhost:6333
 -> session memory assisted query rewrite
 -> vector retrieval + BM25 keyword retrieval
 -> RRF fusion
 -> rerank
 -> duplicate removal + per-article chunk limit + token budget control
 -> answer with citations
 -> RAGAS/lite evaluation and retrieval trace logging
```

Important endpoints:

```text
POST /api/agent/execute          action=embed syncs a blog into Qdrant
POST /api/agent/rag/ask          asks the blog knowledge base
POST /api/agent/rag/evaluate     evaluates a small list of RAG test cases
```

Configure local `.env`:

```text
VECTOR_STORE=qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=blog_chunks
DASHSCOPE_API_KEY=your-local-key
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4
DASHAPI=your-local-rerank-key
DASHSCOPE_RERANK_MODEL=Qwen3-Reranker-4B
RAG_CONTEXT_TOKEN_BUDGET=2800
RAG_MAX_CHUNKS_PER_ARTICLE=2
RAG_MEMORY_TURNS=6
RAG_TRACE_SAMPLE_DOCS=8
ANALYTICS_MAX_JOIN_COUNT=2
ANALYTICS_MAX_GROUP_BY_FIELDS=3
ANALYTICS_MAX_SQL_COUNT=3
```

## Agent Engineering Optimizations

RAG Agent:

- Optional `sessionId` enables multi-turn conversation memory.
- Conversation memory is used during query rewrite to resolve follow-up questions.
- Retrieval trace records query rewrite, vector search, BM25, RRF, rerank, and score filtering.
- Context optimization removes duplicate chunks, limits chunks per article, and controls token budget before LLM generation.
- RAGAS evaluation remains the primary evaluation path with lite fallback.

Operations Agent:

- LangGraph nodes now include permission check, intent detection, analysis planning, SQL generation, safety tool call, SQL tool call, and report generation.
- A structured `analysisPlan` is generated before SQL execution.
- The agent supports multiple readonly SQL statements per analysis, capped by `ANALYTICS_MAX_SQL_COUNT`.
- SQL safety checks include optional `sqlglot` AST validation, table/field allowlists, `LIMIT`, `SELECT *` blocking, JOIN limits, and GROUP BY limits.

`requirements.txt` is kept only for compatibility. Prefer `uv sync` and `uv run`.
