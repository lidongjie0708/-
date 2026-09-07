from __future__ import annotations

import json
import threading
from typing import Any

from app.config import settings
from app.infra import mysql
from app.infra.llm import llm_client


SUMMARY_SYSTEM_PROMPT = """你负责维护 RAG 会话的长期记忆。只依据给出的旧摘要和新增对话，输出一个完整 JSON 对象：
{
  "conversationGoal": "当前长期目标，最多 160 字",
  "confirmedFacts": ["已由用户或可信回答确认的事实，最多 8 条"],
  "preferences": ["用户明确表达的稳定偏好，最多 5 条"],
  "openQuestions": ["仍未解决的问题，最多 6 条"],
  "importantEntities": ["项目、技术或对象，最多 10 个"],
  "summary": "面向后续模型的简洁会话摘要"
}
不要编造事实；不要保存敏感信息；不要把一次性猜测写成用户偏好。只输出 JSON。"""

_worker_stop = threading.Event()
_worker_thread: threading.Thread | None = None


def enqueue_summary_task(session_id: str, user_id: int | None, target_turn_id: int) -> None:
    """Persist work first; the background worker can safely continue after a restart."""
    if not settings.rag_long_term_memory_enabled or not settings.rag_memory_summary_async_enabled:
        return
    try:
        with mysql.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO rag_memory_summary_task (session_id, user_key, user_id, target_turn_id, status)
                    VALUES (%s, %s, %s, %s, 'PENDING')
                    ON DUPLICATE KEY UPDATE
                        target_turn_id = GREATEST(target_turn_id, VALUES(target_turn_id)),
                        status = IF(status = 'PROCESSING', status, 'PENDING'),
                        error_message = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (session_id, _user_key(user_id), user_id, target_turn_id),
                )
    except Exception:
        # A summary is an optimization. The durable raw turn has already been saved.
        return


def start_memory_summary_worker() -> None:
    global _worker_thread
    if not settings.rag_memory_summary_async_enabled or (_worker_thread and _worker_thread.is_alive()):
        return
    _worker_stop.clear()
    _worker_thread = threading.Thread(target=_worker_loop, name="rag-memory-summary", daemon=True)
    _worker_thread.start()


def stop_memory_summary_worker() -> None:
    _worker_stop.set()
    if _worker_thread:
        _worker_thread.join(timeout=2)


def _worker_loop() -> None:
    while not _worker_stop.is_set():
        for _ in range(max(settings.rag_memory_summary_worker_batch_size, 1)):
            if not process_next_summary_task():
                break
        _worker_stop.wait(max(settings.rag_memory_summary_worker_poll_seconds, 1))


def process_next_summary_task() -> bool:
    """Claim and process one task. Kept public to make a dedicated worker deployment possible."""
    try:
        rows = mysql.query(
            """
            SELECT id, session_id, user_key, user_id, target_turn_id
            FROM rag_memory_summary_task
            WHERE status = 'PENDING'
            ORDER BY updated_at, id
            LIMIT 1
            """
        )
        if not rows:
            return False
        task = rows[0]
        with mysql.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE rag_memory_summary_task
                       SET status = 'PROCESSING', attempt_count = attempt_count + 1, locked_at = CURRENT_TIMESTAMP
                       WHERE id = %s AND status = 'PENDING'""",
                    (task["id"],),
                )
                if cursor.rowcount != 1:
                    return True
        _summarize_task(task)
        return True
    except Exception:
        return False


def _summarize_task(task: dict[str, Any]) -> None:
    try:
        summary_rows = mysql.query(
            """SELECT summary_json, last_summarized_turn_id, version
               FROM rag_conversation_summary
               WHERE session_id = %s AND user_key = %s LIMIT 1""",
            (task["session_id"], task["user_key"]),
        )
        existing = summary_rows[0] if summary_rows else {}
        last_turn_id = int(existing.get("last_summarized_turn_id") or 0)
        rows = mysql.query(
            """SELECT id, question, answer, citation_titles_json
               FROM rag_conversation_turn
               WHERE session_id = %s AND user_id <=> %s AND id > %s AND id <= %s
               ORDER BY id ASC""",
            (task["session_id"], task["user_id"], last_turn_id, task["target_turn_id"]),
        )
        if not rows:
            _finish_task(task["id"], "DONE")
            return
        prior = _json_object(existing.get("summary_json"))
        fallback = _local_structured_summary(prior, rows)
        generated = llm_client.complete_json(SUMMARY_SYSTEM_PROMPT, _summary_prompt(prior, rows), fallback)
        summary = normalize_summary(generated, fallback)
        summary_text = render_summary(summary, settings.rag_memory_summary_max_chars)
        _save_summary(task, existing, summary, summary_text, rows[-1]["id"], len(rows), llm_client.degraded)
    except Exception as exc:
        _finish_task(task["id"], "PENDING", str(exc)[:1000])


def _save_summary(
    task: dict[str, Any],
    existing: dict[str, Any],
    summary: dict[str, Any],
    text: str,
    last_turn_id: int,
    summarized_turn_count: int,
    degraded: bool,
) -> None:
    with mysql.get_connection() as conn:
        with conn.cursor() as cursor:
            if existing:
                cursor.execute(
                    """UPDATE rag_conversation_summary
                       SET summary_text = %s, summary_json = %s, last_summarized_turn_id = %s,
                           turn_count = turn_count + %s, version = version + 1,
                           status = %s, updated_at = CURRENT_TIMESTAMP
                       WHERE session_id = %s AND user_key = %s AND version = %s""",
                    (text, json.dumps(summary, ensure_ascii=False), last_turn_id, summarized_turn_count,
                     "DEGRADED" if degraded else "READY",
                     task["session_id"], task["user_key"], existing.get("version", 1)),
                )
                if cursor.rowcount != 1:
                    _finish_task(task["id"], "PENDING", "summary-version-conflict")
                    return
            else:
                cursor.execute(
                    """INSERT INTO rag_conversation_summary
                       (session_id, user_key, user_id, summary_text, summary_json, last_summarized_turn_id, turn_count, version, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s)""",
                    (task["session_id"], task["user_key"], task["user_id"], text, json.dumps(summary, ensure_ascii=False),
                     last_turn_id, summarized_turn_count, "DEGRADED" if degraded else "READY"),
                )
    _finish_processed_task(task)


def _finish_task(task_id: int, status: str, error: str | None = None) -> None:
    with mysql.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """UPDATE rag_memory_summary_task SET status = %s, error_message = %s,
                   locked_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = %s""",
                (status, error, task_id),
            )


def _finish_processed_task(task: dict[str, Any]) -> None:
    """Keep a coalesced task pending when newer turns arrived while it was running."""
    with mysql.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """UPDATE rag_memory_summary_task
                   SET status = IF(target_turn_id > %s, 'PENDING', 'DONE'), error_message = NULL,
                       locked_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = %s""",
                (task["target_turn_id"], task["id"]),
            )


def normalize_summary(value: Any, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    fallback = fallback or _empty_summary()
    raw = value if isinstance(value, dict) else {}
    result: dict[str, Any] = {}
    for key, limit in (("confirmedFacts", 8), ("preferences", 5), ("openQuestions", 6), ("importantEntities", 10)):
        items = raw.get(key, fallback.get(key, []))
        result[key] = [str(item).strip()[:240] for item in items if str(item).strip()][:limit] if isinstance(items, list) else fallback.get(key, [])
    for key, limit in (("conversationGoal", 160), ("summary", 900)):
        result[key] = str(raw.get(key) or fallback.get(key) or "").strip()[:limit]
    return result


def render_summary(summary: dict[str, Any], max_chars: int) -> str:
    parts = [
        f"会话目标：{summary.get('conversationGoal', '')}",
        f"已确认事实：{'；'.join(summary.get('confirmedFacts', []))}",
        f"用户偏好：{'；'.join(summary.get('preferences', []))}",
        f"待解决问题：{'；'.join(summary.get('openQuestions', []))}",
        f"关键实体：{'、'.join(summary.get('importantEntities', []))}",
        f"摘要：{summary.get('summary', '')}",
    ]
    return "\n".join(part for part in parts if part.split("：", 1)[-1]).strip()[:max_chars]


def _local_structured_summary(prior: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = normalize_summary(prior, _empty_summary())
    snippets = [f"Q: {row.get('question', '')[:180]} A: {row.get('answer', '')[:220]}" for row in rows]
    summary["summary"] = (summary.get("summary", "") + " " + " ".join(snippets)).strip()[-900:]
    summary["openQuestions"] = list(dict.fromkeys(summary.get("openQuestions", []) + [str(row.get("question", ""))[:160] for row in rows[-2:]]))[:6]
    return summary


def _summary_prompt(prior: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    turns = []
    for row in rows:
        citations = _json_list(row.get("citation_titles_json"))[:3]
        turns.append({"id": row["id"], "question": row.get("question", "")[:800], "answer": row.get("answer", "")[:1200], "citations": citations})
    return json.dumps({"oldSummary": prior, "newTurns": turns}, ensure_ascii=False)


def _empty_summary() -> dict[str, Any]:
    return {"conversationGoal": "", "confirmedFacts": [], "preferences": [], "openQuestions": [], "importantEntities": [], "summary": ""}


def _json_object(raw: Any) -> dict[str, Any]:
    try:
        return json.loads(raw) if isinstance(raw, str) else (raw if isinstance(raw, dict) else {})
    except (TypeError, json.JSONDecodeError):
        return {}


def _json_list(raw: Any) -> list[Any]:
    try:
        value = json.loads(raw or "[]") if isinstance(raw, str) else raw
        return value if isinstance(value, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _user_key(user_id: int | None) -> str:
    return str(user_id) if user_id is not None else "anonymous"
