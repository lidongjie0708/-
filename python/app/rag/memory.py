from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.infra import mysql


class ConversationMemoryStore:
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

    def get(self, session_id: str | None, user_id: int | None = None) -> list[dict[str, Any]]:
        if not session_id:
            return []
        key = _memory_key(session_id, user_id)
        if self._redis is not None:
            try:
                items = self._redis.lrange(key, 0, settings.rag_memory_turns - 1)
                return [json.loads(item) for item in items]
            except Exception:
                pass
        return self._get_recent_turns_from_db(session_id, user_id)

    def get_summary(self, session_id: str | None, user_id: int | None = None) -> str:
        if not session_id or not settings.rag_long_term_memory_enabled:
            return ""
        try:
            rows = mysql.query(
                """
                SELECT summary_text
                FROM rag_conversation_summary
                WHERE session_id = %s AND user_key = %s
                LIMIT 1
                """,
                (session_id, _user_key(user_id)),
            )
            return str(rows[0].get("summary_text") or "") if rows else ""
        except Exception:
            return ""

    def append(
        self,
        session_id: str | None,
        question: str,
        answer: str,
        citations: list[dict[str, Any]],
        user_id: int | None = None,
    ) -> bool:
        if not session_id:
            return False
        key = _memory_key(session_id, user_id)
        turn = {
            "question": question,
            "answer": answer[:1200],
            "citationTitles": [item.get("title") for item in citations[:5] if item.get("title")],
            "citationArticleIds": [item.get("articleId") for item in citations[:5] if item.get("articleId")],
        }
        self._append_to_db(session_id, user_id, turn)
        if self._redis is not None:
            try:
                pipeline = self._redis.pipeline(transaction=True)
                pipeline.rpush(key, json.dumps(turn, ensure_ascii=False, default=str))
                pipeline.ltrim(key, -settings.rag_memory_turns, -1)
                pipeline.expire(key, settings.conversation_ttl_seconds)
                pipeline.execute()
                return True
            except Exception:
                pass
        return False

    def delete(self, session_id: str | None, user_id: int | None = None) -> None:
        if not session_id:
            return
        key = _memory_key(session_id, user_id)
        if self._redis is not None:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        if settings.rag_long_term_memory_enabled:
            try:
                with mysql.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "DELETE FROM rag_conversation_turn WHERE session_id = %s AND user_id <=> %s",
                            (session_id, user_id),
                        )
                        cursor.execute(
                            "DELETE FROM rag_conversation_summary WHERE session_id = %s AND user_key = %s",
                            (session_id, _user_key(user_id)),
                        )
            except Exception:
                pass

    @property
    def backend(self) -> str:
        if self._redis is not None:
            try:
                if self._redis.ping():
                    return "redis"
            except Exception:
                pass
        return "stateless"

    def _append_to_db(self, session_id: str, user_id: int | None, turn: dict[str, Any]) -> None:
        if not settings.rag_long_term_memory_enabled:
            return
        try:
            with mysql.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO rag_conversation_turn (
                            session_id, user_id, question, answer, citation_titles_json, citation_article_ids_json
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            session_id,
                            user_id,
                            turn.get("question", ""),
                            turn.get("answer", ""),
                            json.dumps(turn.get("citationTitles") or [], ensure_ascii=False, default=str),
                            json.dumps(turn.get("citationArticleIds") or [], ensure_ascii=False, default=str),
                        ),
                    )
                    cursor.execute(
                        """
                        SELECT COUNT(*) AS total
                        FROM rag_conversation_turn
                        WHERE session_id = %s AND user_id <=> %s
                        """,
                        (session_id, user_id),
                    )
                    total = int((cursor.fetchone() or {}).get("total") or 0)
            if total and total % max(settings.rag_memory_summary_every_turns, 1) == 0:
                self._refresh_summary(session_id, user_id, total)
        except Exception:
            return

    def _get_recent_turns_from_db(self, session_id: str, user_id: int | None) -> list[dict[str, Any]]:
        if not settings.rag_long_term_memory_enabled:
            return []
        try:
            rows = mysql.query(
                """
                SELECT question, answer, citation_titles_json, citation_article_ids_json
                FROM rag_conversation_turn
                WHERE session_id = %s AND user_id <=> %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (session_id, user_id, settings.rag_memory_turns),
            )
            turns = []
            for row in reversed(rows):
                turns.append(
                    {
                        "question": row.get("question") or "",
                        "answer": row.get("answer") or "",
                        "citationTitles": _json_list(row.get("citation_titles_json")),
                        "citationArticleIds": _json_list(row.get("citation_article_ids_json")),
                    }
                )
            return turns
        except Exception:
            return []

    def _refresh_summary(self, session_id: str, user_id: int | None, turn_count: int) -> None:
        rows = mysql.query(
            """
            SELECT question, answer, citation_titles_json
            FROM rag_conversation_turn
            WHERE session_id = %s AND user_id <=> %s
            ORDER BY id DESC
            LIMIT %s
            """,
            (session_id, user_id, max(settings.rag_memory_summary_every_turns, 1)),
        )
        prior = self.get_summary(session_id, user_id)
        summary = _build_local_summary(prior, list(reversed(rows)))
        with mysql.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO rag_conversation_summary (
                        session_id, user_key, user_id, summary_text, turn_count
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        summary_text = VALUES(summary_text),
                        turn_count = VALUES(turn_count),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (session_id, _user_key(user_id), user_id, summary, turn_count),
                )


conversation_memory = ConversationMemoryStore()


def build_memory_context(session_id: str | None, user_id: int | None = None) -> dict[str, Any]:
    backend = conversation_memory.backend
    turns = conversation_memory.get(session_id, user_id)
    long_term_summary = conversation_memory.get_summary(session_id, user_id)
    if not turns:
        return {
            "sessionId": session_id,
            "turnCount": 0,
            "summary": long_term_summary,
            "longTermSummary": long_term_summary,
            "recentTurns": [],
            "backend": backend,
            "storageAvailable": backend == "redis",
            "longTermStorage": "mysql" if long_term_summary else "none",
        }
    summary_lines = []
    for index, turn in enumerate(turns[-settings.rag_memory_turns :], start=1):
        titles = ", ".join(turn.get("citationTitles") or [])
        summary_lines.append(
            f"{index}. Q: {turn.get('question', '')}\nA: {turn.get('answer', '')[:240]}\nCitations: {titles}"
        )
    return {
        "sessionId": session_id,
        "turnCount": len(turns),
        "summary": "\n".join([part for part in [long_term_summary, "\n".join(summary_lines)] if part]),
        "longTermSummary": long_term_summary,
        "recentTurns": turns,
        "backend": backend,
        "storageAvailable": backend == "redis",
        "longTermStorage": "mysql" if long_term_summary else "none",
    }


def _memory_key(session_id: str, user_id: int | None) -> str:
    return f"blogslike:conversation:{_user_key(user_id)}:{session_id}"


def _user_key(user_id: int | None) -> str:
    return str(user_id) if user_id is not None else "anonymous"


def _json_list(raw: Any) -> list[Any]:
    try:
        value = json.loads(raw or "[]")
        return value if isinstance(value, list) else []
    except Exception:
        return []


def _build_local_summary(prior_summary: str, rows: list[dict[str, Any]]) -> str:
    lines = [prior_summary.strip()] if prior_summary.strip() else []
    for row in rows:
        titles = ", ".join(_json_list(row.get("citation_titles_json"))[:3])
        lines.append(
            " ".join(
                part
                for part in [
                    f"Q: {row.get('question', '')}",
                    f"A: {str(row.get('answer', ''))[:260]}",
                    f"Citations: {titles}" if titles else "",
                ]
                if part
            )
        )
    summary = "\n".join(lines)
    if len(summary) <= settings.rag_memory_summary_max_chars:
        return summary
    return summary[-settings.rag_memory_summary_max_chars :]
