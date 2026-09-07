"""Short-term (Redis) and long-term (MySQL) memory for the operations agent.

The store keeps the most recent structured turns in Redis for cheap inline
recall and persists durable facts in ``ops_memory_entry``.  Context assembly
follows the L0-L4 layering described in ``prompts/context_layering.md``.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any

from app.config import settings
from app.infra import mysql
from app.infra.llm import llm_client

SHORT_MEMORY_DEFAULT_TURNS = 6
LONG_MEMORY_TOP_K = 5
LONG_MEMORY_MIN_IMPORTANCE = 0.5
L1_TOKEN_BUDGET = 600
L2_TOKEN_BUDGET = 800
CONSOLIDATE_EVERY_TURNS = 4


class OpsMemoryStore:
    """Redis short-term turns + MySQL long-term entries."""

    def __init__(self) -> None:
        self._redis = self._create_redis_client()

    def _create_redis_client(self):
        try:
            from redis import Redis

            return Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
                health_check_interval=30,
            )
        except Exception:
            return None

    @property
    def available(self) -> bool:
        if self._redis is None:
            return False
        try:
            return bool(self._redis.ping())
        except Exception:
            return False

    def _short_key(self, user_id: int | None, session_id: str | None) -> str:
        return f"ops:short:memory:{user_id or 'anon'}:{session_id or 'default'}"

    # ---------- short-term memory (Redis) ----------
    def get_short_turns(self, user_id: int | None, session_id: str | None) -> list[dict[str, Any]]:
        if self._redis is None:
            return []
        try:
            items = self._redis.lrange(self._short_key(user_id, session_id), 0, -1)
            return [item for item in (json.loads(value) for value in items) if isinstance(item, dict)]
        except Exception:
            return []

    def append_short_turn(
        self,
        user_id: int | None,
        session_id: str | None,
        turn: dict[str, Any],
        keep: int = SHORT_MEMORY_DEFAULT_TURNS,
    ) -> bool:
        if self._redis is None:
            return False
        try:
            normalized = {
                "question": str(turn.get("question") or "")[:500],
                "intent": str(turn.get("intent") or ""),
                "declaration": str(turn.get("declaration") or "")[:200],
                "sql": str(turn.get("sql") or "")[:300],
                "rowCount": int(turn.get("rowCount") or 0),
                "conclusion": str(turn.get("conclusion") or "")[:400],
                "ts": datetime.now().isoformat(timespec="seconds"),
            }
            key = self._short_key(user_id, session_id)
            pipeline = self._redis.pipeline(transaction=True)
            pipeline.rpush(key, json.dumps(normalized, ensure_ascii=False))
            pipeline.ltrim(key, -keep, -1)
            pipeline.expire(key, settings.conversation_ttl_seconds)
            pipeline.execute()
            return True
        except Exception:
            return False

    def compress_short_memory(self, user_id: int | None, session_id: str | None, keep: int = 4) -> dict[str, Any]:
        """Trim tool noise and merge the oldest turns into one compressed summary."""
        turns = self.get_short_turns(user_id, session_id)
        if len(turns) <= keep:
            return {"turns": turns, "compressed": False, "compressedSummary": ""}
        oldest, recent = turns[: len(turns) - keep], turns[len(turns) - keep :]
        compressed_summary = "；".join(
            f"{item.get('question', '')[:60]} → {item.get('conclusion', '')[:80]}" for item in oldest if item.get("question")
        )[:600]
        compact_recent = [
            {
                "question": item.get("question", ""),
                "intent": item.get("intent", ""),
                "declaration": item.get("declaration", ""),
                "rowCount": item.get("rowCount", 0),
                "conclusion": item.get("conclusion", ""),
            }
            for item in recent
        ]
        if self._redis is not None:
            try:
                key = self._short_key(user_id, session_id)
                pipeline = self._redis.pipeline(transaction=True)
                pipeline.delete(key)
                if compact_recent:
                    pipeline.rpush(key, *[json.dumps(item, ensure_ascii=False) for item in compact_recent])
                    pipeline.expire(key, settings.conversation_ttl_seconds)
                pipeline.execute()
            except Exception:
                pass
        return {"turns": compact_recent, "compressed": True, "compressedSummary": compressed_summary}

    # ---------- long-term memory (MySQL) ----------
    def recall_long_term(
        self,
        user_id: int | None,
        question: str,
        top_k: int = LONG_MEMORY_TOP_K,
        min_importance: float = LONG_MEMORY_MIN_IMPORTANCE,
    ) -> list[dict[str, Any]]:
        if not settings.analytics_memory_enabled:
            return []
        try:
            rows = mysql.query(
                """
                SELECT scope, user_id, session_id, memory_key, content, importance, tags_json
                FROM ops_memory_entry
                WHERE (scope = 'GLOBAL' OR scope = 'USER' AND user_id <=> %s)
                  AND importance >= %s
                  AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY importance DESC, updated_at DESC
                LIMIT 40
                """,
                (user_id, min_importance),
            )
        except Exception:
            return []
        scored = sorted(
            ({"scope": row["scope"], "key": row["memory_key"], "content": row["content"], "importance": float(row["importance"] or 0)} for row in rows),
            key=lambda item: (_keyword_score(question, item["content"]) + float(item["importance"]) * 0.4),
            reverse=True,
        )
        return scored[:top_k]

    def upsert_long_term(
        self,
        scope: str,
        key: str,
        content: str,
        importance: float,
        tags: list[str] | None = None,
        user_id: int | None = None,
        session_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> bool:
        if not settings.analytics_memory_enabled:
            return False
        scope = scope.upper() if scope.upper() in {"GLOBAL", "USER", "SESSION"} else "USER"
        try:
            with mysql.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO ops_memory_entry
                            (scope, user_id, session_id, memory_key, content, importance, tags_json, expires_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            content = VALUES(content),
                            importance = VALUES(importance),
                            tags_json = VALUES(tags_json),
                            expires_at = VALUES(expires_at),
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (
                            scope,
                            user_id if scope in {"USER", "SESSION"} else None,
                            session_id if scope == "SESSION" else None,
                            str(key)[:160],
                            str(content)[:500],
                            round(min(max(float(importance), 0.0), 1.0), 2),
                            json.dumps(tags or [], ensure_ascii=False),
                            expires_at,
                        ),
                    )
            return True
        except Exception:
            return False

    def list_session_memory(self, user_id: int | None, session_id: str | None) -> list[dict[str, Any]]:
        try:
            rows = mysql.query(
                """
                SELECT memory_key, content, importance, tags_json
                FROM ops_memory_entry
                WHERE scope = 'SESSION' AND user_id <=> %s AND session_id = %s
                ORDER BY importance DESC, updated_at DESC
                """,
                (user_id, session_id),
            )
            return [
                {"key": row["memory_key"], "content": row["content"], "importance": float(row["importance"] or 0)}
                for row in rows
            ]
        except Exception:
            return []


ops_memory = OpsMemoryStore()


def _keyword_score(question: str, content: str) -> float:
    """Cheap lexical relevance for long-term recall; embeddings are optional."""
    tokens = {token for token in re.split(r"[\s,，。.!！?？、;；:：]+", str(question)) if len(token) >= 2}
    if not tokens:
        return 0.0
    hits = sum(1 for token in tokens if token in content)
    return hits / max(len(tokens), 1)


def render_prompt(name: str, **kwargs: Any) -> str:
    """Load a prompt file from ``python/app/agents/prompts`` and fill ``{{var}}``."""
    from pathlib import Path

    path = Path(__file__).resolve().parent / "prompts" / f"{name}.md"
    try:
        template = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    for key, value in kwargs.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


def build_layered_context(
    *,
    system_prompt: str,
    long_term: list[dict[str, Any]],
    short_turns: list[dict[str, Any]],
    question: str,
    analysis_spec: dict[str, Any],
    analysis_plan: dict[str, Any],
    referential_hint: str = "",
    supervisor_task: str = "",
    output_format: str = "",
    l1_budget: int = L1_TOKEN_BUDGET,
    l2_budget: int = L2_TOKEN_BUDGET,
) -> dict[str, Any]:
    """Assemble L0-L4 context and report any trimming (``context_layering.md``)."""
    trimmed: list[dict[str, str]] = []
    long_text = _render_long_memory(long_term, l1_budget)
    if long_term and not long_text:
        trimmed.append({"layer": "L1", "reason": "long-term memory exceeded token budget", "saved": str(l1_budget)})
    short_text = _render_short_memory(short_turns, l2_budget)
    if short_turns and not short_text:
        trimmed.append({"layer": "L2", "reason": "short-term memory exceeded token budget", "saved": str(l2_budget)})
    layers = [
        f'<layer name="system">\n{system_prompt}\n</layer>',
        f'<layer name="long_memory">\n{long_text}\n</layer>' if long_text else "",
        f'<layer name="short_memory">\n{short_text}\n</layer>' if short_text else "",
        f'<layer name="immediate">\nQuestion: {question}\nAnalysis spec: {json.dumps(analysis_spec, ensure_ascii=False)}\nPlan: {json.dumps(analysis_plan, ensure_ascii=False)}\n</layer>',
        f'<layer name="supervisor_task">\n{supervisor_task}\n</layer>' if supervisor_task else "",
        f'<layer name="referential">\n{referential_hint}\n</layer>' if referential_hint else "",
        f'<layer name="output_format">\n{output_format}\n</layer>' if output_format else "",
    ]
    return {
        "system": system_prompt,
        "user": "\n\n".join(layer for layer in layers if layer),
        "longTerm": long_text,
        "shortTerm": short_text,
        "trimmed": trimmed,
        "budgets": {"L1": l1_budget, "L2": l2_budget},
    }


def _render_long_memory(entries: list[dict[str, Any]], budget: int) -> str:
    lines = []
    used = 0
    for item in entries:
        line = f"- [{item.get('scope')}] {item.get('content', '')}"
        used += len(line)
        if used > budget:
            break
        lines.append(line)
    return "\n".join(lines)


def _render_short_memory(turns: list[dict[str, Any]], budget: int) -> str:
    lines = []
    used = 0
    for index, turn in enumerate(turns, start=1):
        line = (
            f"{index}. Q: {turn.get('question', '')} | intent: {turn.get('intent', '')} "
            f"| declaration: {turn.get('declaration', '')} | rows: {turn.get('rowCount', 0)} "
            f"| conclusion: {turn.get('conclusion', '')}"
        )
        used += len(line)
        if used > budget:
            break
        lines.append(line)
    return "\n".join(lines)


def consolidate_session_memory(
    user_id: int | None,
    session_id: str | None,
    turns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract durable facts from a session and write them to long-term memory.

    Uses the ``memory_consolidator.md`` prompt when the LLM is available and a
    deterministic fallback otherwise.  Never blocks the request path on a
    remote call.
    """
    entries: list[dict[str, Any]] = []
    if not turns:
        return entries
    if settings.analytics_memory_llm_consolidation and llm_client.enabled:
        try:
            payload = {
                "turns": [
                    {
                        "question": item.get("question", ""),
                        "intent": item.get("intent", ""),
                        "declaration": item.get("declaration", ""),
                        "rowCount": item.get("rowCount", 0),
                        "conclusion": item.get("conclusion", ""),
                    }
                    for item in turns
                ]
            }
            generated = llm_client.complete_json(
                render_prompt("memory_consolidator"),
                json.dumps(payload, ensure_ascii=False),
                {"entries": []},
            )
            raw_entries = generated.get("entries") if isinstance(generated, dict) else []
            for item in raw_entries if isinstance(raw_entries, list) else []:
                if not isinstance(item, dict):
                    continue
                content = str(item.get("content") or "").strip()
                if not content:
                    continue
                entries.append(
                    {
                        "scope": str(item.get("scope") or "SESSION").upper(),
                        "key": str(item.get("key") or f"auto.{len(entries)}"),
                        "content": content[:500],
                        "importance": _bounded_importance(item.get("importance"), 0.55),
                        "tags": [str(tag) for tag in (item.get("tags") or []) if str(tag).strip()][:5],
                    }
                )
        except Exception:
            entries = []
    if not entries:
        entries = _fallback_consolidate(turns)
    for item in entries:
        scope = item["scope"] if item["scope"] in {"GLOBAL", "USER", "SESSION"} else "SESSION"
        key = _dedupe_key(scope, user_id, session_id, str(item["key"]), str(item["content"]))
        ops_memory.upsert_long_term(
            scope=scope,
            key=key,
            content=str(item["content"])[:500],
            importance=float(item["importance"]),
            tags=item.get("tags") or [],
            user_id=user_id,
            session_id=session_id if scope == "SESSION" else None,
            expires_at=datetime.now() + timedelta(days=90) if scope == "SESSION" else None,
        )
    return entries


def _dedupe_key(scope: str, user_id: int | None, session_id: str | None, proposed_key: str, content: str) -> str:
    """Reuse an existing key when the same normalized content already exists."""
    if not settings.analytics_memory_enabled:
        return proposed_key[:160]
    normalized = _normalize_text(content)
    if not normalized:
        return proposed_key[:160]
    try:
        rows = mysql.query(
            """
            SELECT memory_key, content
            FROM ops_memory_entry
            WHERE scope = %s AND user_id <=> %s AND session_id <=> %s
            ORDER BY updated_at DESC
            LIMIT 200
            """,
            (scope, user_id, session_id if scope == "SESSION" else None),
        )
    except Exception:
        return proposed_key[:160]
    for row in rows:
        if _normalize_text(str(row.get("content") or "")) == normalized:
            return str(row["memory_key"])[:160]
    return proposed_key[:160]


def _normalize_text(text: str) -> str:
    return re.sub(r"[\s，。！？、；：,.!?;:（）()「」『』《》\"'“”‘’\-—]+", "", text)[:120]


def _fallback_consolidate(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic extraction when the LLM is unavailable."""
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for turn in reversed(turns[-CONSOLIDATE_EVERY_TURNS:]):
        question = str(turn.get("question") or "").strip()
        conclusion = str(turn.get("conclusion") or "").strip()
        if not question or not conclusion:
            continue
        fact = f"{question} → {conclusion[:200]}"
        key = f"auto.q{len(entries)}"
        if key in seen:
            continue
        seen.add(key)
        entries.append({"scope": "SESSION", "key": key, "content": fact, "importance": 0.55, "tags": ["auto"]})
    return entries[:8]


def _bounded_importance(value: Any, default: float) -> float:
    try:
        return min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError):
        return default
