from __future__ import annotations

import json
import re
from typing import Any, TypedDict

from app.config import settings
from app.infra import mysql
from app.infra.llm import llm_client, llm_factory
from app.tools.sql_tool import (
    execute_readonly_sql,
    get_admin_analytics_tools,
    sql_safety_check_tool,
    validate_readonly_sql,
)


SCHEMA_CONTEXT = """
Allowed MySQL schema:
- blog(id, userId, title, coverImg, content, thumbCount, summary, tags, embeddingStatus, auditStatus, createTime, updateTime)
- comments(id, blogId, userId, content, parentId, createdAt, updatedAt, sentimentScore, isFlagged, isDeleted)
- thumb(id, userId, blogId, createTime)
Rules:
- Only SELECT is allowed.
- Always add LIMIT <= 100.
- Never query password, token, secret, or private credentials.
"""

INTENT_LABELS = {
    "HOT_ARTICLE": "Hot articles by thumb count",
    "LOW_INTERACTION": "Recent articles with low interaction",
    "COMMENT_QUALITY": "Comment sentiment and flagged comment analysis",
    "CONTENT_GROWTH": "Article publishing trend",
    "TAG_DISTRIBUTION": "Tag distribution",
    "RECENT_CONTENT": "Recent article list",
    "CUSTOM_SQL": "Custom safe SQL analysis",
}
TEMPLATE_INTENTS = {
    "HOT_ARTICLE",
    "LOW_INTERACTION",
    "COMMENT_QUALITY",
    "CONTENT_GROWTH",
    "TAG_DISTRIBUTION",
    "RECENT_CONTENT",
}
TEMPLATE_CONFIDENCE_THRESHOLD = 0.75


class AnalyticsState(TypedDict, total=False):
    question: str
    role: str
    user_id: int | None
    intent: str
    intent_payload: dict[str, Any]
    intent_confidence: float
    sql: str | None
    sql_list: list[str]
    sql_source: str | None
    safety: dict[str, Any] | None
    safety_results: list[dict[str, Any]]
    data: list[dict[str, Any]]
    query_results: list[dict[str, Any]]
    analysis_plan: dict[str, Any]
    chart: dict[str, Any]
    report: dict[str, Any]
    result: dict[str, Any]
    status: str
    error: str | None
    execution_plan: dict[str, Any]


def analyze_operation(question: str, role: str, user_id: int | None = None) -> dict:
    state: AnalyticsState = {
        "question": question,
        "role": role,
        "user_id": user_id,
        "status": "RUNNING",
        "error": None,
        "execution_plan": new_execution_plan(question),
        "data": [],
        "sql_list": [],
        "query_results": [],
        "safety_results": [],
    }
    try:
        graph = build_analytics_graph()
        state = graph.invoke(state) if graph else run_fallback_graph(state)
        result = state.get("result") or finalize_result(state)
        _save_analysis_log(question, role, user_id, result)
        return result
    except Exception as exc:
        add_step(state["execution_plan"], "agent_failure", "FAILED", str(exc))
        result = _failed_result(question, state.get("intent", "CUSTOM_SQL"), state["execution_plan"], state.get("sql"), str(exc), state.get("safety"))
        _save_analysis_log(question, role, user_id, result)
        return result


def build_analytics_graph() -> Any:
    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return None

    graph = StateGraph(AnalyticsState)
    graph.add_node("permission", permission_node)
    graph.add_node("intent", intent_node)
    graph.add_node("analysis_plan", analysis_plan_node)
    graph.add_node("sql_generation", sql_generation_node)
    graph.add_node("safety_tool", safety_tool_node)
    graph.add_node("sql_tool", sql_tool_node)
    graph.add_node("report", report_node)
    graph.add_node("denied", denied_node)
    graph.add_node("blocked", blocked_node)
    graph.add_edge("permission", "intent")
    graph.add_conditional_edges(
        "intent",
        route_after_permission,
        {"denied": "denied", "blocked": "blocked", "continue": "analysis_plan"},
    )
    graph.add_edge("analysis_plan", "sql_generation")
    graph.add_edge("sql_generation", "safety_tool")
    graph.add_conditional_edges("safety_tool", route_after_safety, {"blocked": "blocked", "continue": "sql_tool"})
    graph.add_edge("sql_tool", "report")
    graph.add_edge("report", END)
    graph.add_edge("denied", END)
    graph.add_edge("blocked", END)
    graph.set_entry_point("permission")
    return graph.compile()


def run_fallback_graph(state: AnalyticsState) -> AnalyticsState:
    state = permission_node(state)
    state = intent_node(state)
    route = route_after_permission(state)
    if route == "denied":
        return denied_node(state)
    if route == "blocked":
        return blocked_node(state)
    state = analysis_plan_node(state)
    state = sql_generation_node(state)
    state = safety_tool_node(state)
    if route_after_safety(state) == "blocked":
        return blocked_node(state)
    state = sql_tool_node(state)
    return report_node(state)


def permission_node(state: AnalyticsState) -> AnalyticsState:
    if state["role"].upper() != "ADMIN":
        state["status"] = "DENIED"
        state["error"] = "NO_PERMISSION"
        add_step(state["execution_plan"], "permission_check", "FAILED", "Role is not ADMIN")
        return state
    add_step(state["execution_plan"], "permission_check", "SUCCESS", "Admin role accepted")
    return state


def intent_node(state: AnalyticsState) -> AnalyticsState:
    if state.get("status") == "DENIED":
        return state
    if is_write_or_destructive_request(state["question"]):
        state["status"] = "FAILED"
        state["error"] = "WRITE_OR_DESTRUCTIVE_ACTION_NOT_ALLOWED"
        state["intent"] = "BLOCKED_WRITE_ACTION"
        add_step(
            state["execution_plan"],
            "request_safety_check",
            "FAILED",
            "Write or destructive operations are not allowed for analytics Agent",
        )
        return state
    payload = detect_intent(state["question"])
    intent = normalize_intent(payload.get("intent"))
    confidence = _bounded_float(payload.get("confidence"), 0.35)
    state["intent_payload"] = payload
    state["intent"] = intent
    state["intent_confidence"] = confidence
    add_step(
        state["execution_plan"],
        "intent_detection",
        "SUCCESS",
        payload.get("reason", "Intent detected"),
        {"intent": intent, "confidence": confidence, "candidates": payload.get("candidates", [])},
    )
    return state


def analysis_plan_node(state: AnalyticsState) -> AnalyticsState:
    intent = state.get("intent", "CUSTOM_SQL")
    fallback = build_fallback_analysis_plan(state["question"], intent)
    if _template_path_enabled(state):
        state["analysis_plan"] = fallback
        add_step(
            state["execution_plan"],
            "analysis_plan",
            "SKIPPED",
            "Template analytics path uses a local plan to reduce LLM tokens",
            {"analysisPlan": fallback, "costMode": "low"},
        )
        return state
    plan = llm_client.complete_json(
        (
            "Create a concise multi-step admin analytics plan. Return JSON with goal, steps, "
            "requiredMetrics, dimensions, timeRange, sqlCount. sqlCount must be 1-3."
        ),
        f"{SCHEMA_CONTEXT}\nQuestion: {state['question']}\nIntent: {state.get('intent_payload')}",
        fallback,
    )
    plan = normalize_analysis_plan(plan, fallback)
    state["analysis_plan"] = plan
    add_step(state["execution_plan"], "analysis_plan", "SUCCESS", "Multi-step analysis plan generated", {"analysisPlan": plan})
    return state


def sql_generation_node(state: AnalyticsState) -> AnalyticsState:
    intent = state.get("intent", "CUSTOM_SQL")
    confidence = float(state.get("intent_confidence", 0.0) or 0.0)
    template_allowed = intent in TEMPLATE_INTENTS and confidence >= TEMPLATE_CONFIDENCE_THRESHOLD
    template_sql = sql_from_template(intent, state["question"]) if template_allowed else None
    sql_list = [template_sql] if template_sql else sqls_from_tool_calling_llm(state)
    sql_list = [sql for sql in sql_list if sql][: settings.analytics_max_sql_count]
    if not sql_list:
        sql_list = [sql_from_template("RECENT_CONTENT", state["question"]) or "SELECT id, title, thumbCount, createTime FROM blog ORDER BY createTime DESC LIMIT 10"]
    state["sql_list"] = sql_list
    state["sql"] = sql_list[0]
    state["sql_source"] = "template" if template_sql else "llm_tool_calling"
    add_step(
        state["execution_plan"],
        "sql_generation",
        "SUCCESS",
        f"SQL generated from {state['sql_source']}",
        {"sqlSource": state["sql_source"], "sql": state["sql"], "sqlList": sql_list},
    )
    return state


def safety_tool_node(state: AnalyticsState) -> AnalyticsState:
    safety_results = []
    for index, sql in enumerate(state.get("sql_list") or [state.get("sql") or ""]):
        tool_call = {"tool": "sql_safety_check", "arguments": {"sql": sql}}
        tool_result = invoke_tool("sql_safety_check", sql=sql) or sql_safety_check_tool(sql)
        safety_results.append({"index": index, "sql": sql, **tool_result, "toolCall": tool_call})
    state["safety_results"] = safety_results
    state["safety"] = safety_results[0] if safety_results else {"safe": False, "reason": "No SQL generated"}
    all_safe = all(item.get("safe") for item in safety_results)
    add_step(
        state["execution_plan"],
        "sql_safety_check_tool_call",
        "SUCCESS" if all_safe else "FAILED",
        "All SQL statements passed safety checks" if all_safe else "One or more SQL statements were blocked",
        {"toolResults": safety_results},
    )
    return state


def sql_tool_node(state: AnalyticsState) -> AnalyticsState:
    sql_list = state.get("sql_list") or [state.get("sql") or ""]
    try:
        query_results = []
        for index, sql in enumerate(sql_list):
            data = invoke_tool("readonly_sql_query", sql=sql)
            if data is None:
                data = execute_readonly_sql(sql)
            query_results.append({"index": index, "sql": sql, "rowCount": len(data), "data": data})
        state["query_results"] = query_results
        state["data"] = query_results[0]["data"] if query_results else []
        add_step(
            state["execution_plan"],
            "readonly_sql_query_tool_call",
            "SUCCESS",
            "SQL statements executed through tool-calling",
            {"queryResults": [{"index": item["index"], "sql": item["sql"], "rowCount": item["rowCount"]} for item in query_results]},
        )
    except Exception as exc:
        state["status"] = "FAILED"
        state["error"] = str(exc)
        add_step(state["execution_plan"], "readonly_sql_query_tool_call", "FAILED", str(exc))
    return state


def report_node(state: AnalyticsState) -> AnalyticsState:
    if state.get("status") == "FAILED":
        state["result"] = _failed_result(
            state["question"],
            state.get("intent", "CUSTOM_SQL"),
            state["execution_plan"],
            state.get("sql"),
            state.get("error") or "Query failed",
            state.get("safety"),
        )
        return state
    data = state.get("data", [])
    intent = state.get("intent", "CUSTOM_SQL")
    state["chart"] = build_chart(intent, data)
    state["report"] = generate_report(
        state["question"],
        intent,
        state.get("sql") or "",
        data,
        state.get("query_results") or [],
        state.get("analysis_plan") or {},
        state.get("sql_source"),
    )
    add_step(state["execution_plan"], "report_generation", "SUCCESS", "Report generated")
    state["status"] = "SUCCESS"
    state["result"] = finalize_result(state)
    return state


def denied_node(state: AnalyticsState) -> AnalyticsState:
    state["result"] = _denied_result(state["question"], state["role"], state.get("user_id"), state["execution_plan"])
    return state


def blocked_node(state: AnalyticsState) -> AnalyticsState:
    state["status"] = "FAILED"
    if not state.get("error"):
        failed = [item for item in state.get("safety_results", []) if not item.get("safe")]
        failed_reason = "; ".join(f"#{item.get('index')}: {item.get('reason')}" for item in failed)
        state["error"] = f"Unsafe SQL blocked: {failed_reason or (state.get('safety') or {}).get('reason')}"
    state["result"] = _failed_result(
        state["question"],
        state.get("intent", "CUSTOM_SQL"),
        state["execution_plan"],
        state.get("sql"),
        state["error"] or "Unsafe SQL blocked",
        state.get("safety"),
    )
    return state


def route_after_permission(state: AnalyticsState) -> str:
    if state.get("status") == "DENIED":
        return "denied"
    if state.get("status") == "FAILED":
        return "blocked"
    return "continue"


def route_after_safety(state: AnalyticsState) -> str:
    safety_results = state.get("safety_results") or [state.get("safety") or {}]
    return "continue" if all(item.get("safe") for item in safety_results) else "blocked"


def invoke_tool(name: str, **kwargs: Any) -> Any:
    for item in get_admin_analytics_tools():
        if getattr(item, "name", "") == name:
            return item.invoke(kwargs)
    return None


def sqls_from_tool_calling_llm(state: AnalyticsState) -> list[str]:
    fallback = sql_from_template("RECENT_CONTENT", state["question"]) or "SELECT id, title, thumbCount, createTime FROM blog ORDER BY createTime DESC LIMIT 10"
    if settings.analytics_low_cost_mode:
        return _extract_sql_list(
            sql_from_llm(state["question"], state.get("intent_payload", {}), state.get("analysis_plan", {}), fallback),
            fallback,
        )
    model = llm_factory()
    tools = get_admin_analytics_tools()
    if model and tools:
        try:
            response = model.bind_tools(tools).invoke(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are an admin analytics planner. Produce a safe SELECT SQL for the requested analysis. "
                            "You may call sql_safety_check before finalizing. Return JSON with sqlList, 1 to 3 SQL statements."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"{SCHEMA_CONTEXT}\nQuestion: {state['question']}\nIntent: {state.get('intent_payload')}\n"
                            f"Analysis plan: {state.get('analysis_plan')}"
                        ),
                    },
                ]
            )
            content = getattr(response, "content", "")
            parsed = _json_from_text(str(content), {"sqlList": [fallback]})
            return _extract_sql_list(parsed, fallback)
        except Exception:
            pass
    return _extract_sql_list(sql_from_llm(state["question"], state.get("intent_payload", {}), state.get("analysis_plan", {}), fallback), fallback)


def build_fallback_analysis_plan(question: str, intent: str) -> dict[str, Any]:
    templates = {
        "HOT_ARTICLE": ["Find top articles by thumb count", "Summarize common tags and publish timing", "Generate follow-up actions"],
        "LOW_INTERACTION": ["Find low-interaction articles", "Compare content metadata", "Recommend optimization actions"],
        "COMMENT_QUALITY": ["Aggregate comment count and flagged comments", "Identify risky content", "Suggest moderation actions"],
        "CONTENT_GROWTH": ["Analyze publishing trend", "Identify peak and low days", "Suggest content cadence"],
        "TAG_DISTRIBUTION": ["Aggregate tag distribution", "Find over/under represented tags", "Suggest topic planning"],
    }
    return {
        "goal": question,
        "intent": intent,
        "steps": templates.get(intent, ["Generate safe SQL", "Execute readonly query", "Summarize result and suggestions"]),
        "requiredMetrics": [],
        "dimensions": [],
        "timeRange": None,
        "sqlCount": 1,
    }


def normalize_analysis_plan(plan: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    steps = plan.get("steps") if isinstance(plan.get("steps"), list) else fallback["steps"]
    sql_count = plan.get("sqlCount", fallback.get("sqlCount", 1))
    try:
        sql_count = min(max(int(sql_count), 1), settings.analytics_max_sql_count)
    except (TypeError, ValueError):
        sql_count = 1
    return {
        "goal": str(plan.get("goal") or fallback["goal"]),
        "intent": str(plan.get("intent") or fallback.get("intent", "CUSTOM_SQL")),
        "steps": [str(item) for item in steps[:6]],
        "requiredMetrics": plan.get("requiredMetrics") if isinstance(plan.get("requiredMetrics"), list) else [],
        "dimensions": plan.get("dimensions") if isinstance(plan.get("dimensions"), list) else [],
        "timeRange": plan.get("timeRange"),
        "sqlCount": sql_count,
    }


def detect_intent(question: str) -> dict[str, Any]:
    candidates = rule_intent_candidates(question)
    fallback_intent = candidates[0]["intent"] if candidates else "CUSTOM_SQL"
    fallback_confidence = candidates[0]["confidence"] if candidates else 0.35
    fallback = {
        "intent": fallback_intent,
        "confidence": fallback_confidence,
        "metrics": [],
        "dimension": "unknown",
        "timeRange": None,
        "reason": "Fallback intent classification",
        "candidates": candidates,
    }
    if (
        settings.analytics_low_cost_mode
        and fallback_intent in TEMPLATE_INTENTS
        and fallback_confidence >= TEMPLATE_CONFIDENCE_THRESHOLD
    ):
        fallback["reason"] = "Rule intent matched template path; LLM classification skipped"
        fallback["llmSkipped"] = True
        return fallback
    result = llm_client.complete_json(
        (
            "Classify the admin analytics question. Return JSON with intent, confidence, metrics, "
            "dimension, timeRange, reason. Use only these intents: "
            f"{list(INTENT_LABELS)}. If unsure, use CUSTOM_SQL with confidence below 0.75."
        ),
        f"{SCHEMA_CONTEXT}\nRule candidates: {candidates}\nQuestion: {question}",
        fallback,
    )
    result["intent"] = normalize_intent(result.get("intent"))
    result["confidence"] = _bounded_float(result.get("confidence"), fallback_confidence)
    result["candidates"] = candidates
    return result


def rule_intent_candidates(question: str) -> list[dict[str, Any]]:
    lowered = question.lower()
    rules = [
        ("HOT_ARTICLE", ["hot", "top", "popular", "thumb", "like", "likes", "点赞", "热门", "最高"], 0.82),
        ("LOW_INTERACTION", ["low interaction", "few likes", "点赞少", "互动低", "低互动"], 0.82),
        ("COMMENT_QUALITY", ["comment", "comments", "sentiment", "flagged", "audit", "评论", "情感", "违规", "审核"], 0.82),
        ("CONTENT_GROWTH", ["growth", "trend", "publish", "new posts", "新增", "增长", "趋势", "发布"], 0.78),
        ("TAG_DISTRIBUTION", ["tag", "tags", "category", "topic", "标签", "分类", "主题"], 0.78),
        ("RECENT_CONTENT", ["recent", "latest", "newest", "最近", "最新", "近期"], 0.76),
    ]
    candidates = [
        {"intent": intent, "confidence": confidence, "matched": True}
        for intent, keywords, confidence in rules
        if any(keyword in lowered or keyword in question for keyword in keywords)
    ]
    return sorted(candidates, key=lambda item: item["confidence"], reverse=True)


def is_write_or_destructive_request(question: str) -> bool:
    lowered = question.lower()
    keywords = {
        "delete",
        "drop",
        "update",
        "insert",
        "truncate",
        "alter",
        "remove",
        "ban",
        "删除",
        "清空",
        "修改",
        "更新",
        "插入",
        "新增",
        "封禁",
        "下架",
        "隐藏",
    }
    return any(keyword in lowered or keyword in question for keyword in keywords)


def sql_from_template(intent: str, question: str) -> str | None:
    limit = _extract_limit(question, default=10)
    if intent == "HOT_ARTICLE":
        return f"SELECT id, title, thumbCount, tags, createTime FROM blog ORDER BY thumbCount DESC LIMIT {limit}"
    if intent == "LOW_INTERACTION":
        return f"SELECT id, title, thumbCount, tags, createTime FROM blog ORDER BY thumbCount ASC, createTime DESC LIMIT {limit}"
    if intent == "COMMENT_QUALITY":
        return (
            "SELECT blogId, COUNT(*) AS commentCount, AVG(sentimentScore) AS avgSentiment, SUM(isFlagged) AS flaggedCount "
            "FROM comments WHERE isDeleted = 0 GROUP BY blogId ORDER BY flaggedCount DESC, commentCount DESC "
            f"LIMIT {limit}"
        )
    if intent == "CONTENT_GROWTH":
        return f"SELECT DATE(createTime) AS day, COUNT(*) AS articleCount FROM blog GROUP BY DATE(createTime) ORDER BY day DESC LIMIT {min(max(limit, 7), 30)}"
    if intent == "TAG_DISTRIBUTION":
        return f"SELECT tags, COUNT(*) AS articleCount FROM blog WHERE tags IS NOT NULL AND tags <> '' GROUP BY tags ORDER BY articleCount DESC LIMIT {limit}"
    if intent == "RECENT_CONTENT":
        return f"SELECT id, title, thumbCount, tags, createTime FROM blog ORDER BY createTime DESC LIMIT {limit}"
    return None


def sql_from_llm(
    question: str,
    intent_payload: dict[str, Any],
    analysis_plan: dict[str, Any],
    fallback: str,
) -> dict[str, Any]:
    result = llm_client.complete_json(
        (
            'You are a safe MySQL analyst. Return JSON only: {"sqlList":["SELECT ... LIMIT 10"]}. '
            "Use only allowed schema. Do not invent tables or fields. Generate at most 3 SQL statements."
        ),
        f"{SCHEMA_CONTEXT}\nIntent payload: {intent_payload}\nAnalysis plan: {analysis_plan}\nQuestion: {question}",
        {"sqlList": [fallback]},
    )
    return result


def _extract_sql_list(payload: dict[str, Any], fallback: str) -> list[str]:
    sql_list = payload.get("sqlList") or payload.get("sql_list")
    if isinstance(sql_list, str):
        sql_list = [sql_list]
    if not isinstance(sql_list, list):
        single = payload.get("sql")
        sql_list = [single] if single else [fallback]
    cleaned = []
    for item in sql_list:
        sql = str(item or "").strip()
        if sql:
            cleaned.append(sql)
    return cleaned[: settings.analytics_max_sql_count] or [fallback]


def build_chart(intent: str, data: list[dict[str, Any]]) -> dict[str, Any]:
    if intent in {"HOT_ARTICLE", "LOW_INTERACTION"}:
        return {"type": "bar", "xField": "title", "yField": "thumbCount", "data": data}
    if intent == "COMMENT_QUALITY":
        return {"type": "bar", "xField": "blogId", "yField": "flaggedCount", "data": data}
    if intent == "CONTENT_GROWTH":
        return {"type": "line", "xField": "day", "yField": "articleCount", "data": list(reversed(data))}
    if intent == "TAG_DISTRIBUTION":
        return {"type": "bar", "xField": "tags", "yField": "articleCount", "data": data}
    return {"type": "table", "data": data}


def generate_report(
    question: str,
    intent: str,
    sql: str,
    data: list[dict[str, Any]],
    query_results: list[dict[str, Any]] | None = None,
    analysis_plan: dict[str, Any] | None = None,
    sql_source: str | None = None,
) -> dict[str, Any]:
    fallback = fallback_report(intent, data)
    if not data:
        return fallback
    if settings.analytics_low_cost_mode and (
        not settings.analytics_llm_report_enabled or sql_source == "template"
    ):
        return fallback
    result_summary = [
        {
            "index": item.get("index"),
            "sql": item.get("sql"),
            "rowCount": item.get("rowCount"),
            "sample": (item.get("data") or [])[:5],
        }
        for item in (query_results or [])
    ]
    report = llm_client.complete_json(
        (
            "You are an operations analytics Agent. Return JSON with summary, insights, suggestions. "
            "suggestions must be objects with action, reason, priority. Mention concrete numbers from data."
        ),
        (
            f"Question: {question}\nIntent: {intent}\nPrimary SQL: {sql}\n"
            f"Analysis plan: {analysis_plan or {}}\nQuery results: {result_summary or data[:20]}"
        ),
        fallback,
    )
    return normalize_report(report, fallback)


def fallback_report(intent: str, data: list[dict[str, Any]]) -> dict[str, Any]:
    if not data:
        return {
            "summary": "No matching data was found. Try expanding the time range or changing the analysis dimension.",
            "insights": [],
            "suggestions": [{"action": "expand_time_range", "reason": "The query returned no rows.", "priority": "MEDIUM"}],
        }
    suggestions_by_intent = {
        "HOT_ARTICLE": [{"action": "write_followup", "reason": "Top articles indicate proven audience interest.", "priority": "HIGH"}],
        "LOW_INTERACTION": [{"action": "improve_cta", "reason": "Low thumb count suggests weak interaction prompts.", "priority": "HIGH"}],
        "COMMENT_QUALITY": [{"action": "manual_review", "reason": "Flagged comments require moderation attention.", "priority": "HIGH"}],
    }
    return {
        "summary": f"Analytics completed for {INTENT_LABELS.get(intent, intent)} with {len(data)} rows.",
        "insights": [f"Returned {len(data)} rows for intent {intent}."],
        "suggestions": suggestions_by_intent.get(intent, [{"action": "review_rows", "reason": "Use returned rows for follow-up analysis.", "priority": "LOW"}]),
    }


def normalize_report(report: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") or fallback["summary"]
    insights = report.get("insights") if isinstance(report.get("insights"), list) else fallback["insights"]
    suggestions = report.get("suggestions") if isinstance(report.get("suggestions"), list) else fallback["suggestions"]
    normalized = []
    for item in suggestions:
        if isinstance(item, dict):
            normalized.append({"action": str(item.get("action", "review")), "reason": str(item.get("reason", "")), "priority": str(item.get("priority", "MEDIUM")).upper()})
        else:
            normalized.append({"action": "review", "reason": str(item), "priority": "MEDIUM"})
    return {"summary": str(summary), "insights": insights, "suggestions": normalized}


def _template_path_enabled(state: AnalyticsState) -> bool:
    intent = state.get("intent", "CUSTOM_SQL")
    confidence = float(state.get("intent_confidence", 0.0) or 0.0)
    return (
        settings.analytics_low_cost_mode
        and intent in TEMPLATE_INTENTS
        and confidence >= TEMPLATE_CONFIDENCE_THRESHOLD
    )


def finalize_result(state: AnalyticsState) -> dict[str, Any]:
    data = state.get("data", [])
    sql = state.get("sql")
    intent = state.get("intent", "CUSTOM_SQL")
    confidence = estimate_confidence(sql or "", data, state.get("sql_source") or "unknown", float(state.get("intent_confidence", 0.0) or 0.0))
    report = state.get("report") or fallback_report(intent, data)
    return {
        "intent": intent,
        "intentLabel": INTENT_LABELS.get(intent, intent),
        "intentConfidence": state.get("intent_confidence", 0.0),
        "sql": sql,
        "sqlList": state.get("sql_list") or ([sql] if sql else []),
        "sqlSource": state.get("sql_source"),
        "data": data,
        "queryResults": state.get("query_results") or [],
        "analysisPlan": state.get("analysis_plan") or {},
        "chart": state.get("chart") or build_chart(intent, data),
        "report": report,
        "insight": report.get("summary", ""),
        "suggestions": report.get("suggestions", []),
        "confidence": confidence,
        "status": state.get("status", "SUCCESS"),
        "error": state.get("error"),
        "safety": state.get("safety"),
        "executionPlan": state.get("execution_plan"),
        "plan": state.get("execution_plan"),
    }


def estimate_confidence(sql: str, data: list[dict[str, Any]], sql_source: str, intent_confidence: float) -> float:
    score = 0.4 + min(max(intent_confidence, 0.0), 1.0) * 0.25
    if sql_source == "template":
        score += 0.2
    if data:
        score += 0.1
    if sql and validate_readonly_sql(sql)[0]:
        score += 0.05
    return round(min(score, 0.98), 2)


def new_execution_plan(question: str) -> dict[str, Any]:
    return {"goal": question, "framework": "langgraph", "toolCalling": True, "intent": None, "steps": []}


def add_step(execution_plan: dict[str, Any], name: str, status: str, detail: str, extra: dict[str, Any] | None = None) -> None:
    step = {"name": name, "status": status, "detail": detail}
    if extra:
        step.update(extra)
    execution_plan["steps"].append(step)
    if name == "intent_detection" and extra and extra.get("intent"):
        execution_plan["intent"] = extra["intent"]


def normalize_intent(value: Any) -> str:
    intent = str(value or "CUSTOM_SQL").upper()
    return intent if intent in INTENT_LABELS else "CUSTOM_SQL"


def _bounded_float(value: Any, default: float) -> float:
    try:
        return min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError):
        return default


def _extract_limit(question: str, default: int) -> int:
    match = re.search(r"(\d+)", question)
    if not match:
        return default
    return min(max(int(match.group(1)), 1), 100)


def _json_from_text(text: str, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end >= start:
            return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        pass
    return fallback


def _denied_result(question: str, role: str, user_id: int | None, execution_plan: dict[str, Any]) -> dict:
    report = fallback_report("DENIED", [])
    return {
        "intent": "DENIED",
        "intentConfidence": 0.0,
        "sql": None,
        "sqlSource": None,
        "data": [],
        "chart": {"type": "table", "data": []},
        "report": report,
        "insight": report["summary"],
        "suggestions": report["suggestions"],
        "confidence": 0.0,
        "status": "DENIED",
        "error": "NO_PERMISSION",
        "safety": None,
        "executionPlan": execution_plan,
        "plan": {"question": question, "role": role, "userId": user_id},
    }


def _failed_result(question: str, intent: str, execution_plan: dict[str, Any], sql: str | None, error: str, safety: dict[str, Any] | None) -> dict:
    report = fallback_report(intent, [])
    return {
        "intent": intent,
        "intentConfidence": 0.0,
        "sql": sql,
        "sqlSource": None,
        "data": [],
        "chart": {"type": "table", "data": []},
        "report": report,
        "insight": "The analytics query failed or was blocked by safety rules.",
        "suggestions": [{"action": "fix_query", "reason": error, "priority": "HIGH"}],
        "confidence": 0.0,
        "status": "FAILED",
        "error": error,
        "safety": safety,
        "executionPlan": execution_plan,
        "plan": execution_plan,
    }


def _save_analysis_log(question: str, role: str, user_id: int | None, result: dict[str, Any]) -> None:
    sql = """
        INSERT INTO agent_analysis_log (
            question, intent, user_id, role, sql_text, status, row_count, confidence,
            chart_json, result_json, insight, suggestions_json, plan_json, error_message
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    data = result.get("data") or []
    params = (
        question,
        result.get("intent"),
        user_id,
        role,
        result.get("sql"),
        result.get("status", "SUCCESS"),
        len(data),
        result.get("confidence"),
        json.dumps(result.get("chart") or {}, ensure_ascii=False, default=str),
        json.dumps(data[:50], ensure_ascii=False, default=str),
        result.get("insight"),
        json.dumps(result.get("suggestions") or [], ensure_ascii=False, default=str),
        json.dumps(result.get("executionPlan") or {}, ensure_ascii=False, default=str),
        result.get("error"),
    )
    try:
        with mysql.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
    except Exception:
        return
