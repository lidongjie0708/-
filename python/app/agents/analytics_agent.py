from __future__ import annotations

import json
import re
import threading
from typing import Any, TypedDict

from app.config import settings
from app.infra import mysql
from app.infra.llm import llm_client, llm_factory
from app.agents.analytics_memory import (
    build_layered_context,
    consolidate_session_memory,
    ops_memory,
    render_prompt,
)
from app.ops_metrics import run_metric_diagnostics
from app.ops_metrics.registry import get_metric_definition
from app.tools.sql_tool import (
    execute_readonly_sql,
    get_admin_analytics_tools,
    get_safe_analytics_tools,
    safe_readonly_sql_query,
    sql_safety_check_tool,
    validate_readonly_sql,
)


SCHEMA_CONTEXT = """
Allowed MySQL schema:
- blog(id, userId, title, coverImg, content, thumbCount, summary, tags, embedding_status, audit_status, createTime, updateTime, content_format)
- comments(id, blog_id, user_id, content, parent_id, created_at, updated_at, sentiment_score, is_flagged, is_deleted)
- thumb(id, user_id, blog_id, create_time)
Rules:
- Only SELECT is allowed.
- Always add LIMIT <= 100.
- Never query password, token, secret, or private credentials.
"""

INTENT_LABELS = {
    "OVERVIEW": "Content overview counts",
    "HOT_ARTICLE": "Hot articles by thumb count",
    "LOW_INTERACTION": "Recent articles with low interaction",
    "COMMENT_QUALITY": "Comment sentiment and flagged comment analysis",
    "CONTENT_GROWTH": "Article publishing trend",
    "TAG_DISTRIBUTION": "Tag distribution",
    "RECENT_CONTENT": "Recent article list",
    "CUSTOM_SQL": "Custom safe SQL analysis",
}
TEMPLATE_INTENTS = {
    "OVERVIEW",
    "HOT_ARTICLE",
    "LOW_INTERACTION",
    "COMMENT_QUALITY",
    "CONTENT_GROWTH",
    "TAG_DISTRIBUTION",
    "RECENT_CONTENT",
}
TEMPLATE_CONFIDENCE_THRESHOLD = 0.75
DEFAULT_ANALYTICS_LIMIT = 10
MAX_ANALYTICS_LIMIT = 100


class AnalyticsState(TypedDict, total=False):
    question: str
    role: str
    user_id: int | None
    session_id: str | None
    memory: dict[str, Any]
    intent: str
    intent_payload: dict[str, Any]
    intent_confidence: float
    analysis_spec: dict[str, Any]
    use_template_path: bool
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
    tool_loop: dict[str, Any]
    execution_mode: str
    messages: list[Any]
    pending_tool_calls: list[dict[str, Any]]
    loop_round: int
    loop_completed: bool
    loop_stop_reason: str | None
    loop_tool_history: list[dict[str, Any]]
    loop_query_results: list[dict[str, Any]]
    loop_sqls: list[str]
    diagnostics: list[dict[str, Any]]
    diagnostic_keys: list[str]
    forced_intent: str | None
    clarification: dict[str, Any] | None
    supervisor: dict[str, Any]


def analyze_operation(
    question: str,
    role: str,
    user_id: int | None = None,
    forced_intent: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Run the full analytics pipeline and return the final result dict."""
    result = None
    for kind, payload in stream_analyze_operation(
        question,
        role,
        user_id,
        forced_intent,
        session_id,
    ):
        if kind == "result":
            result = payload
    if result is None:
        return _failed_result(
            question,
            "CUSTOM_SQL",
            new_execution_plan(question),
            None,
            "Agent did not produce a result",
            None,
        )
    return result


def stream_analyze_operation(
    question: str,
    role: str,
    user_id: int | None = None,
    forced_intent: str | None = None,
    session_id: str | None = None,
):
    """Run the analytics pipeline and yield ("event", payload) tuples live.

    Event kinds:
    - "status": a LangGraph node completed (user-facing progress message).
    - "plan":   the supervisor declaration of what will be queried.
    - "sql":    a readonly SQL statement that was executed (with row count).

    The final item is always ("result", result_dict), so callers can either
    stream events to a client or simply take the last value.
    """
    yield ("status", {"stage": "memory", "message": "正在载入上下文记忆…"})
    state: AnalyticsState = {
        "question": question,
        "role": role,
        "user_id": user_id,
        "session_id": session_id,
        "forced_intent": forced_intent,
        "status": "RUNNING",
        "error": None,
        "execution_plan": new_execution_plan(question),
        "data": [],
        "sql_list": [],
        "query_results": [],
        "safety_results": [],
        "memory": _load_memory_context(user_id, session_id, question),
    }
    emitted: dict[str, Any] = {"plan": False, "sqls": set()}
    try:
        graph = build_analytics_graph()
        if graph is not None:
            for update in graph.stream(state, stream_mode="updates"):
                for node_name, node_update in update.items():
                    yield from _iter_node_events(node_name, node_update, emitted)
                    state.update(node_update)
        else:
            # Degraded path without LangGraph: emit coarse progress events.
            buffered: list[tuple[str, dict]] = [
                ("status", {"stage": "fallback", "message": "正在执行分析（降级模式）…"}),
            ]
            state = run_fallback_graph(state)
            buffered.append(("status", {"stage": "report", "message": "正在生成结论与建议…"}))
            for item in buffered:
                yield item
        result = state.get("result") or finalize_result(state)
        yield ("status", {"stage": "persist", "message": "正在保存分析记录…"})
        _save_analysis_log(question, role, user_id, result)
        _remember_turn(state, result)
        yield ("result", result)
    except Exception as exc:
        add_step(state["execution_plan"], "agent_failure", "FAILED", str(exc))
        result = _failed_result(question, state.get("intent", "CUSTOM_SQL"), state["execution_plan"], state.get("sql"), str(exc), state.get("safety"))
        yield ("status", {"stage": "persist", "message": "正在保存分析记录…"})
        _save_analysis_log(question, role, user_id, result)
        _remember_turn(state, result)
        yield ("result", result)


NODE_STATUS_MESSAGES: dict[str, str] = {
    "permission": "正在校验权限…",
    "intent": "正在理解问题、识别意图…",
    "supervisor": "正在制定分析计划…",
    "analysis_plan": "正在细化分析步骤…",
    "template_sql_generation": "正在生成查询 SQL…",
    "agent_loop_init": "正在初始化自主分析循环…",
    "agent_decide": "正在思考下一步查询…",
    "safe_query_executor": "正在执行查询…",
    "finalize_agent_loop": "正在汇总查询结果…",
    "safety_tool": "正在进行 SQL 安全检查…",
    "sql_tool": "正在执行查询…",
    "diagnostic": "正在诊断运营指标…",
    "report": "正在生成结论与建议…",
    "denied": "权限校验未通过，请求已拒绝",
    "blocked": "请求已被安全策略拦截",
    "clarify": "意图不明确，需要确认方向",
}


def _iter_node_events(
    node_name: str,
    node_update: dict[str, Any],
    emitted: dict[str, Any],
):
    """Yield user-facing event tuples for a completed LangGraph node."""
    if not isinstance(node_update, dict):
        return
    message = NODE_STATUS_MESSAGES.get(node_name)
    if message:
        yield ("status", {"stage": node_name, "message": message})
    if not emitted.get("plan"):
        supervisor = node_update.get("supervisor")
        if isinstance(supervisor, dict):
            declaration = supervisor.get("declaration")
            if declaration:
                emitted["plan"] = True
                yield ("plan", {"declaration": str(declaration)[:200]})
    for sql, row_count in _extract_executed_sqls(node_update):
        if sql and sql not in emitted["sqls"]:
            emitted["sqls"].add(sql)
            yield ("sql", {"sql": sql, "rowCount": row_count})


def _extract_executed_sqls(node_update: dict[str, Any]):
    """Yield (sql, rowCount) pairs from query results in a node update."""
    seen: set[str] = set()
    for item in node_update.get("query_results") or []:
        if not isinstance(item, dict):
            continue
        sql = str(item.get("sql") or "").strip()
        if sql and sql not in seen:
            seen.add(sql)
            yield sql, int(item.get("rowCount") or 0)
    for item in node_update.get("loop_query_results") or []:
        if not isinstance(item, dict) or not item.get("ok"):
            continue
        sql = str(item.get("sql") or "").strip()
        if sql and sql not in seen:
            seen.add(sql)
            yield sql, int(item.get("rowCount") or 0)


def build_analytics_graph() -> Any:
    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return None

    graph = StateGraph(AnalyticsState)
    graph.add_node("permission", permission_node)
    graph.add_node("intent", intent_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("analysis_plan", analysis_plan_node)
    graph.add_node("template_sql_generation", template_sql_generation_node)
    graph.add_node("agent_loop_init", agent_loop_init_node)
    graph.add_node("agent_decide", agent_decide_node)
    graph.add_node("safe_query_executor", safe_query_executor_node)
    graph.add_node("finalize_agent_loop", finalize_agent_loop_node)
    graph.add_node("safety_tool", safety_tool_node)
    graph.add_node("sql_tool", sql_tool_node)
    graph.add_node("diagnostic", diagnostic_node)
    graph.add_node("report", report_node)
    graph.add_node("denied", denied_node)
    graph.add_node("blocked", blocked_node)
    graph.add_node("clarify", clarify_node)
    graph.add_edge("permission", "intent")
    graph.add_conditional_edges(
        "intent",
        route_after_intent,
        {"clarify": "clarify", "blocked": "blocked", "supervisor": "supervisor", "diagnostic": "diagnostic"},
    )
    graph.add_edge("supervisor", "analysis_plan")
    graph.add_conditional_edges("analysis_plan", route_after_analysis_plan, {"template": "template_sql_generation", "agent_loop": "agent_loop_init"})
    graph.add_edge("template_sql_generation", "safety_tool")
    graph.add_conditional_edges("safety_tool", route_after_safety, {"blocked": "blocked", "continue": "sql_tool"})
    graph.add_edge("sql_tool", "report")
    graph.add_edge("agent_loop_init", "agent_decide")
    graph.add_conditional_edges("agent_decide", route_after_agent_decide, {"tools": "safe_query_executor", "finalize": "finalize_agent_loop", "blocked": "blocked"})
    graph.add_edge("safe_query_executor", "agent_decide")
    graph.add_edge("finalize_agent_loop", "report")
    graph.add_edge("report", END)
    graph.add_edge("diagnostic", END)
    graph.add_edge("denied", END)
    graph.add_edge("blocked", END)
    graph.add_edge("clarify", END)
    graph.set_entry_point("permission")
    return graph.compile()


def run_fallback_graph(state: AnalyticsState) -> AnalyticsState:
    state = permission_node(state)
    state = intent_node(state)
    if state.get("status") == "NEEDS_CLARIFICATION":
        return clarify_node(state)
    route = route_after_permission(state)
    if route == "denied":
        return denied_node(state)
    if route == "blocked":
        return blocked_node(state)
    if route_after_intent(state) == "diagnostic":
        return diagnostic_node(state)
    state = supervisor_node(state)
    state = analysis_plan_node(state)
    if route_after_analysis_plan(state) == "template":
        state = template_sql_generation_node(state)
        state = safety_tool_node(state)
        if route_after_safety(state) == "blocked":
            return blocked_node(state)
        state = sql_tool_node(state)
    else:
        state = agent_loop_init_node(state)
        while True:
            state = agent_decide_node(state)
            route = route_after_agent_decide(state)
            if route == "tools":
                state = safe_query_executor_node(state)
                continue
            if route == "blocked":
                return blocked_node(state)
            state = finalize_agent_loop_node(state)
            break
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
    if is_sensitive_data_request(state["question"]):
        state["status"] = "FAILED"
        state["error"] = "SENSITIVE_DATA_ACCESS_NOT_ALLOWED"
        state["intent"] = "BLOCKED_SENSITIVE_DATA"
        add_step(
            state["execution_plan"],
            "request_safety_check",
            "FAILED",
            "Sensitive data access (password/token/secret) is not allowed for analytics Agent",
        )
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
    forced = state.get("forced_intent")
    if forced:
        payload = {
            "intent": normalize_intent(forced),
            "confidence": 0.95,
            "metrics": [],
            "dimension": "article",
            "reason": "Forced intent from daily report; intent detection skipped",
            "candidates": [],
            "limit": extract_requested_limit(state["question"]),
            "timeRange": extract_time_range(state["question"]),
            "filters": {},
            "llmSkipped": True,
        }
    else:
        payload = detect_intent(state["question"])
    referential_title = _referential_title(state["question"], state.get("memory", {}).get("short_turns") or [])
    if referential_title:
        # A referential question targets a concrete article; the generic intent
        # label must not drive the report wording. Route as custom analysis.
        payload = {
            "intent": "CUSTOM_SQL",
            "confidence": 0.9,
            "metrics": [],
            "dimension": "article",
            "reason": f"Referential question resolved to article《{referential_title}》",
            "candidates": [],
            "limit": 10,
            "timeRange": None,
            "filters": {},
            "llmSkipped": False,
            "referentialTitle": referential_title,
        }
    diagnostic_keys = metric_diagnostic_keys(state["question"])
    if diagnostic_keys:
        state["diagnostic_keys"] = diagnostic_keys
    if not forced:
        if state.get("diagnostic_keys"):
            # An anomaly/comparison question must go to the governed diagnostics
            # sub-agent; never ask for clarification on a well-defined metric.
            add_step(
                state["execution_plan"],
                "intent_detection",
                "SUCCESS",
                "Anomaly/comparison question routed to diagnostics",
                {"intent": "CUSTOM_SQL", "metrics": diagnostic_keys, "useTemplatePath": False},
            )
            return state
        clarification = _clarification_payload(state["question"], payload)
        if clarification:
            state["status"] = "NEEDS_CLARIFICATION"
            state["error"] = "INTENT_NEEDS_CLARIFICATION"
            state["clarification"] = clarification
            add_step(
                state["execution_plan"],
                "intent_clarification",
                "NEEDS_CLARIFICATION",
                clarification["message"],
                {"options": clarification["options"]},
            )
            return state
    intent = normalize_intent(payload.get("intent"))
    confidence = _bounded_float(payload.get("confidence"), 0.35)
    state["intent_payload"] = payload
    state["intent"] = intent
    state["intent_confidence"] = confidence
    state["analysis_spec"] = normalize_analysis_spec(payload, state["question"], intent)
    state["use_template_path"] = template_path_enabled(state["analysis_spec"], confidence)
    add_step(
        state["execution_plan"],
        "intent_detection",
        "SUCCESS",
        payload.get("reason", "Intent detected"),
        {
            "intent": intent,
            "confidence": confidence,
            "candidates": payload.get("candidates", []),
            "analysisSpec": state["analysis_spec"],
            "useTemplatePath": state["use_template_path"],
            "templateVerify": payload.get("templateVerify"),
        },
    )
    return state


def route_after_intent(state: AnalyticsState) -> str:
    if state.get("status") == "NEEDS_CLARIFICATION":
        return "clarify"
    if state.get("status") in {"DENIED", "FAILED"}:
        return "blocked"
    if state.get("diagnostic_keys"):
        return "diagnostic"
    return "supervisor"


def clarify_node(state: AnalyticsState) -> AnalyticsState:
    state["result"] = _clarification_result(
        state["question"],
        state["execution_plan"],
        state.get("clarification") or {},
    )
    return state


def _clarification_result(question: str, execution_plan: dict, clarification: dict) -> dict:
    message = str(clarification.get("message") or "请先选择分析方向。")
    return {
        "status": "NEEDS_CLARIFICATION",
        "error": "INTENT_NEEDS_CLARIFICATION",
        "intent": "NEEDS_CLARIFICATION",
        "intentConfidence": 0.0,
        "sql": None,
        "sqlList": [],
        "sqlSource": None,
        "data": [],
        "chart": {"type": "table", "data": []},
        "report": {"summary": message, "insights": [], "suggestions": []},
        "insight": message,
        "suggestions": [],
        "clarification": clarification,
        "confidence": 0.0,
        "executionPlan": execution_plan,
        "plan": execution_plan,
    }


CLARIFICATION_OPTIONS = [
    {"value": "HOT_ARTICLE", "label": "热门内容"},
    {"value": "LOW_INTERACTION", "label": "低互动内容"},
    {"value": "COMMENT_QUALITY", "label": "评论风险/质量"},
    {"value": "CONTENT_GROWTH", "label": "发布趋势"},
    {"value": "TAG_DISTRIBUTION", "label": "标签分布"},
    {"value": "RECENT_CONTENT", "label": "最近内容"},
    {"value": "CUSTOM_SQL", "label": "自定义分析（描述具体想看的数据）"},
]

AMBIGUOUS_MARKERS = ("怎么样", "看看", "情况", "数据怎么样", "分析一下", "整体", "简单说", "总结一下", "汇总一下")


def _is_ambiguous_question(question: str) -> bool:
    stripped = question.strip()
    if len(stripped) <= 12:
        return True
    return any(marker in question for marker in AMBIGUOUS_MARKERS)


def _clarification_payload(question: str, payload: dict) -> dict | None:
    intent = normalize_intent(payload.get("intent"))
    confidence = _bounded_float(payload.get("confidence"), 0.35)
    if intent in TEMPLATE_INTENTS and confidence >= TEMPLATE_CONFIDENCE_THRESHOLD:
        return None
    if intent == "CUSTOM_SQL" and not _is_ambiguous_question(question):
        return None
    candidates = [item.get("intent") for item in rule_intent_candidates(question)]
    options = [item for item in CLARIFICATION_OPTIONS if item["value"] in candidates]
    # Always offer a useful set of directions, not a single custom-SQL fallback.
    core = [item for item in CLARIFICATION_OPTIONS if item["value"] in {"HOT_ARTICLE", "COMMENT_QUALITY", "CONTENT_GROWTH", "RECENT_CONTENT"}]
    for item in core:
        if item not in options:
            options.append(item)
    if not any(item["value"] == "CUSTOM_SQL" for item in options):
        options.append(CLARIFICATION_OPTIONS[-1])
    return {
        "question": question,
        "message": "你的问题有点模糊，先确认一下想看哪个方向？",
        "options": options,
        "reason": f"detected intent={intent}, confidence={confidence}",
    }


def supervisor_node(state: AnalyticsState) -> AnalyticsState:
    """Supervisor Agent: declare the plan and dispatch to the right sub-agent.

    Template and diagnostic routes stay deterministic for latency; only
    complex/custom questions spend one LLM call to produce a concrete
    declaration and task spec for the data-qa sub-agent.
    """
    intent = state.get("intent", "CUSTOM_SQL")
    question = state["question"]
    if state.get("diagnostic_keys"):
        keys = [_metric_key(item) if isinstance(item, dict) else item for item in state["diagnostic_keys"]]
        declaration = f"我将诊断：{' / '.join(filter(None, keys)) or '运营健康指标'}（当前 vs 基线对比）"
        state["supervisor"] = {
            "declaration": declaration,
            "route": "anomaly_diagnosis",
            "mode": "deterministic",
            "reason": "anomaly/comparison question routed to governed diagnostics",
        }
        add_step(
            state["execution_plan"],
            "supervisor",
            "SUCCESS",
            "Supervisor dispatched to anomaly diagnosis sub-agent",
            {"route": "anomaly_diagnosis", "declaration": declaration},
        )
        return state
    if _template_path_enabled(state):
        declaration = build_declaration(intent, state.get("analysis_spec"), [])
        state["supervisor"] = {
            "declaration": declaration,
            "route": "data_qa_template",
            "mode": "deterministic",
            "reason": "template path keeps low latency; no LLM dispatch needed",
        }
        add_step(
            state["execution_plan"],
            "supervisor",
            "SUCCESS",
            "Supervisor dispatched to data-qa template path",
            {"route": "data_qa_template", "declaration": declaration},
        )
        return state
    fallback_declaration = build_declaration(intent, state.get("analysis_spec"), [])
    memory = state.get("memory") or {}
    long_term = memory.get("long_term") or []
    short_turns = memory.get("short_turns") or []
    memory_context = "\n".join(
        [f"- {item.get('content', '')}" for item in long_term[:3]]
        + [f"- 上一轮: {turn.get('question', '')} → {turn.get('conclusion', '')[:80]}" for turn in short_turns[-2:]]
    )
    payload = llm_client.complete_json(
        render_prompt("supervisor") or "You are an operations assistant supervisor.",
        (
            f"{SCHEMA_CONTEXT}\n"
            f"用户问题：{question}\n"
            f"识别意图：{intent}\n"
            f"分析规格：{state.get('analysis_spec') or {}}\n"
            f"可用记忆：\n{memory_context or '（无）'}\n\n"
            "请输出 JSON：{\"declaration\": \"我将查询：...（一句话，具体到指标和范围）\", "
            "\"taskSpec\": {\"goal\": \"...\", \"steps\": [\"...\"]}}"
        ),
        {
            "declaration": fallback_declaration,
            "taskSpec": {"goal": question, "steps": ["Generate safe SQL", "Execute readonly query", "Summarize result"]},
        },
    )
    declaration = str(payload.get("declaration") or fallback_declaration)[:200]
    task_spec = payload.get("taskSpec") if isinstance(payload.get("taskSpec"), dict) else {}
    state["supervisor"] = {
        "declaration": declaration,
        "route": "data_qa_agent",
        "mode": "llm",
        "taskSpec": task_spec,
        "reason": "complex/custom question dispatched to data-qa agent loop",
    }
    add_step(
        state["execution_plan"],
        "supervisor",
        "SUCCESS",
        "Supervisor dispatched to data-qa sub-agent with concrete declaration",
        {"route": "data_qa_agent", "declaration": declaration, "taskSpec": task_spec, "mode": "llm"},
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
            "You are the supervisor of an operations assistant. Create a concise multi-step admin "
            "analytics plan. Return JSON with goal, steps, requiredMetrics, dimensions, timeRange, "
            "sqlCount. sqlCount must be 1-3."
        ),
        f"{SCHEMA_CONTEXT}\nQuestion: {state['question']}\nAnalysis spec: {state.get('analysis_spec')}",
        fallback,
    )
    plan = normalize_analysis_plan(plan, fallback)
    plan["analysisSpec"] = state.get("analysis_spec", {})
    state["analysis_plan"] = plan
    add_step(state["execution_plan"], "analysis_plan", "SUCCESS", "Multi-step analysis plan generated", {"analysisPlan": plan})
    return state


def template_sql_generation_node(state: AnalyticsState) -> AnalyticsState:
    intent = state.get("intent", "CUSTOM_SQL")
    sql = sql_from_template(intent, state.get("analysis_spec", {}))
    if not sql:
        state["status"] = "FAILED"
        state["error"] = "TEMPLATE_SQL_NOT_AVAILABLE"
        return state
    state["execution_mode"] = "template"
    state["sql_list"] = [sql]
    state["sql"] = sql
    state["sql_source"] = "template"
    add_step(
        state["execution_plan"],
        "sql_generation",
        "SUCCESS",
        "SQL generated from template",
        {
            "sqlSource": state["sql_source"],
            "sql": state["sql"],
            "sqlList": state["sql_list"],
        },
    )
    return state


def route_after_analysis_plan(state: AnalyticsState) -> str:
    return "template" if _template_path_enabled(state) else "agent_loop"


def agent_loop_init_node(state: AnalyticsState) -> AnalyticsState:
    state.update({
        "execution_mode": "agent_loop", "pending_tool_calls": [], "loop_round": 0,
        "loop_completed": False, "loop_stop_reason": None, "loop_tool_history": [],
        "loop_query_results": [], "loop_sqls": [],
    })
    memory = state.get("memory") or {}
    referential_hint = _referential_hint(state["question"], memory.get("short_turns") or [])
    referential_title = _referential_title(state["question"], memory.get("short_turns") or [])
    system_prompt = (
        render_prompt(
            "data_qa_agent",
            analytics_max_sql_count=settings.analytics_max_sql_count,
        )
        or "You are an admin analytics agent. You may use only safe_readonly_sql_query."
    )
    if referential_title:
        # Highest-priority instruction: the user references a concrete article
        # from an earlier turn; query that article directly by title.
        system_prompt += (
            f"\n\n【最高优先级指令】用户指代的具体文章是《{referential_title}》。"
            f"你必须直接查询这篇文章的具体字段（如 tags、createTime），用标题《{referential_title}》作为 WHERE 条件，"
            "禁止重新执行热门排行/概览等通用分析。\n" + referential_hint
        )
    llm_question = state["question"]
    if referential_title:
        llm_question = (
            f"{state['question']}（指代已解析：目标文章是《{referential_title}》，"
            f"请查询该文章的 tags 等字段）"
        )
    supervisor = state.get("supervisor") or {}
    supervisor_task = ""
    task_spec = supervisor.get("taskSpec") if isinstance(supervisor.get("taskSpec"), dict) else {}
    if task_spec:
        steps = task_spec.get("steps") if isinstance(task_spec.get("steps"), list) else []
        step_text = "\n".join(f"{i}. {step}" for i, step in enumerate(steps[:6], 1)) if steps else ""
        supervisor_task = (
            "主管 Agent 下发的任务规格（必须遵守）：\n"
            f"目标：{task_spec.get('goal') or state['question']}\n"
            f"{'步骤：\n' + step_text if step_text else ''}"
        ).strip()
    layered = build_layered_context(
        system_prompt=system_prompt + "\n\n" + SCHEMA_CONTEXT,
        long_term=memory.get("long_term") or [],
        short_turns=memory.get("short_turns") or [],
        question=llm_question,
        analysis_spec=state.get("analysis_spec") or {},
        analysis_plan=state.get("analysis_plan") or {},
        referential_hint=referential_hint,
        supervisor_task=supervisor_task,
        output_format=(
            "Hard rules: every SQL MUST end with LIMIT (<=100); a missing LIMIT is rejected. "
            "Propose at most {count} distinct SQL queries and only one query per tool call. "
            "Use conclusions only from tool results. If more data is needed, call the tool again. "
            'When finished return JSON only: {{"done": true}}.'
        ).format(count=settings.analytics_max_sql_count),
        l1_budget=settings.analytics_context_l1_budget,
        l2_budget=settings.analytics_context_l2_budget,
    )
    state["messages"] = [
        {"role": "system", "content": layered["system"]},
        {"role": "user", "content": layered["user"]},
    ]
    add_step(
        state["execution_plan"],
        "agent_loop_init",
        "SUCCESS",
        "Autonomous LangGraph loop initialized with layered context",
        {
            "executionMode": "agent_loop",
            "context": {
                "layers": ["L0", "L3"] + (["L1"] if layered["longTerm"] else []) + (["L2"] if layered["shortTerm"] else []),
                "trimmed": layered["trimmed"],
                "longTermEntries": len(layered["longTerm"].splitlines()) if layered["longTerm"] else 0,
                "shortTurns": len(layered["shortTerm"].splitlines()) if layered["shortTerm"] else 0,
                "referentialHint": referential_hint,
                "referentialTitle": referential_title,
                "supervisorTask": supervisor_task,
            },
        },
    )
    return state


def agent_decide_node(state: AnalyticsState) -> AnalyticsState:
    if state.get("loop_round", 0) >= settings.analytics_max_tool_rounds:
        state["loop_stop_reason"] = "max_tool_rounds_reached"
        add_step(state["execution_plan"], "agent_decide", "FAILED", "Tool-round budget exhausted", {"loopRound": state.get("loop_round")})
        return state
    try:
        model = llm_factory(model=settings.model)
        tools = get_safe_analytics_tools()
        if not model or not tools:
            raise RuntimeError("safe_readonly_sql_query tool or model is unavailable")
        response = model.bind_tools(tools).invoke(state["messages"])
        state["messages"].append(response)
        state["loop_round"] = state.get("loop_round", 0) + 1
        calls = getattr(response, "tool_calls", None) or []
        state["pending_tool_calls"] = list(calls)
        if not calls:
            if _json_from_text(str(getattr(response, "content", "")), {}).get("done") is True:
                state["loop_completed"] = True
                state["loop_stop_reason"] = "model_done"
            else:
                state["loop_stop_reason"] = "invalid_model_termination"
        add_step(state["execution_plan"], "agent_decide", "SUCCESS" if not state.get("loop_stop_reason") or state.get("loop_completed") else "FAILED", "Model decision recorded", {"loopRound": state["loop_round"], "hasToolCalls": bool(calls), "stopReason": state.get("loop_stop_reason")})
    except Exception as exc:
        state["loop_stop_reason"] = "model_error"
        state["error"] = str(exc)
        add_step(state["execution_plan"], "agent_decide", "FAILED", "Model invocation failed", {"loopRound": state.get("loop_round", 0), "stopReason": "model_error"})
    return state


def route_after_agent_decide(state: AnalyticsState) -> str:
    if state.get("pending_tool_calls") and not state.get("loop_stop_reason"):
        return "tools"
    return "finalize" if state.get("loop_completed") else "blocked"


def safe_query_executor_node(state: AnalyticsState) -> AnalyticsState:
    results = state.get("loop_query_results", [])
    sqls = state.get("loop_sqls", [])
    for position, call in enumerate(state.get("pending_tool_calls", [])):
        name, args = str(call.get("name") or ""), call.get("args") or {}
        sql = str(args.get("sql") or "").strip()
        call_id = str(call.get("id") or f"round-{state.get('loop_round')}-{position}")
        if name != "safe_readonly_sql_query":
            result: dict[str, Any] = {"ok": False, "kind": "tool_error", "error": f"tool not allowed: {name}"}
        elif not sql:
            result = {"ok": False, "kind": "tool_error", "error": "sql argument is required"}
        else:
            existing = next((item for item in results if item.get("sql") == sql), None)
            if existing is not None:
                result = {**existing, "reused": True}
            elif len(sqls) >= settings.analytics_max_sql_count:
                result = {"ok": False, "kind": "budget_rejected", "sql": sql, "error": f"SQL budget exceeded: {settings.analytics_max_sql_count}"}
            else:
                sqls.append(sql)
                result = safe_readonly_sql_query(sql)
                results.append(result)
        state["messages"].append(_tool_message(call_id, _compact_tool_result(result)))
        state["loop_tool_history"].append({"round": state.get("loop_round"), "tool": name, "sql": sql, "kind": result.get("kind"), "rowCount": result.get("rowCount"), "reason": (result.get("safety") or {}).get("reason") or result.get("error")})
    state["loop_sqls"], state["loop_query_results"], state["pending_tool_calls"] = sqls, results, []
    add_step(state["execution_plan"], "safe_query_executor", "SUCCESS", "Safe query tool calls processed", {"loopRound": state.get("loop_round"), "tool": "safe_readonly_sql_query", "sqlCount": len(sqls)})
    return state


def finalize_agent_loop_node(state: AnalyticsState) -> AnalyticsState:
    successful = [item for item in state.get("loop_query_results", []) if item.get("ok") and item.get("kind") == "query_result"]
    if not state.get("loop_completed") or not successful:
        state["status"] = "FAILED"
        state["error"] = state.get("error") or ("NO_QUERY_EXECUTED" if state.get("loop_completed") else state.get("loop_stop_reason") or "AGENT_LOOP_FAILED")
        return state
    query_results = [
        {
            "index": index,
            "sql": item["sql"],
            "rowCount": item["rowCount"],
            "data": item["data"],
            "safety": item.get("safety"),
        }
        for index, item in enumerate(successful)
    ]
    failed = [item for item in state.get("loop_query_results", []) if not item.get("ok")]
    safety_items = [
        {
            "sql": item.get("sql"),
            "safe": bool((item.get("safety") or {}).get("safe", item.get("ok"))),
            "reason": (item.get("safety") or {}).get("reason") or item.get("error"),
        }
        for item in state.get("loop_query_results", [])
    ]
    state.update({
        "query_results": query_results,
        "data": query_results[0]["data"],
        "sql_list": [item["sql"] for item in query_results],
        "sql": query_results[0]["sql"],
        "sql_source": "agent_loop",
        "safety": {
            "safe": not failed,
            "total": len(state.get("loop_query_results", [])),
            "passed": len(successful),
            "failed": [
                {"sql": item.get("sql"), "reason": (item.get("safety") or {}).get("reason") or item.get("error")}
                for item in failed
            ],
            "items": safety_items,
        },
    })
    add_step(state["execution_plan"], "finalize_agent_loop", "SUCCESS", "Agent loop normalized for reporting", {"rounds": state.get("loop_round"), "stopReason": state.get("loop_stop_reason"), "sqlCount": len(state.get("loop_sqls", [])), "successfulQueryCount": len(successful), "rejectedQueryCount": len(failed)})
    return state


def safety_tool_node(state: AnalyticsState) -> AnalyticsState:
    safety_results = []
    prior_checks = {
        item.get("sql"): item
        for item in state.get("tool_loop", {}).get("safetyResults", [])
        if item.get("sql")
    }
    for index, sql in enumerate(state.get("sql_list") or [state.get("sql") or ""]):
        tool_call = {"tool": "sql_safety_check", "arguments": {"sql": sql}}
        tool_result = prior_checks.get(sql) or invoke_tool("sql_safety_check", sql=sql) or sql_safety_check_tool(sql)
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
        prior_results = {
            item.get("sql"): item
            for item in state.get("tool_loop", {}).get("queryResults", [])
            if item.get("sql")
        }
        for index, sql in enumerate(sql_list):
            prior = prior_results.get(sql)
            if prior is not None:
                data = prior.get("data", [])
            else:
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
    metric_keys = metric_diagnostic_keys(state["question"])
    if metric_keys:
        # Diagnostics use only registry-owned SELECT templates and the existing
        # safety-wrapped query tool. They never reuse or relax the agent SQL path.
        diagnostics = run_metric_diagnostics(metric_keys, safe_readonly_sql_query)
        state["diagnostics"] = diagnostics
        state["report"]["diagnostics"] = diagnostics
        abnormal = [item for item in diagnostics if item.get("status") in {"SIGNIFICANT_DECLINE", "SIGNIFICANT_INCREASE"}]
        if abnormal:
            state["report"]["summary"] = _diagnostic_summary(abnormal)
        for item in diagnostics:
            if item.get("status") == "SIGNIFICANT_DECLINE" and item.get("finding"):
                state["report"].setdefault("insights", []).append(item["finding"])
        add_step(
            state["execution_plan"],
            "metric_diagnostics",
            "SUCCESS",
            "Governed read-only metric comparisons completed",
            {"metrics": metric_keys, "statuses": [item.get("status") for item in diagnostics]},
        )
    if len(state.get("query_results") or []) > 1:
        state["report"].setdefault("insights", []).append(
            f"The analysis used {len(state['query_results'])} separate SQL result sets; they were kept separate by schema."
        )
    add_step(state["execution_plan"], "report_generation", "SUCCESS", "Report generated")
    state["status"] = "SUCCESS"
    state["result"] = finalize_result(state)
    return state


def diagnostic_node(state: AnalyticsState) -> AnalyticsState:
    """Anomaly-diagnosis sub-agent: governed metrics only, no free-form SQL."""
    keys = state.get("diagnostic_keys") or metric_diagnostic_keys(state.get("question", ""))
    if not keys:
        keys = ["engagement_rate", "content_supply", "negative_comment_rate"]
    diagnostics = run_metric_diagnostics(keys, safe_readonly_sql_query)
    state["diagnostics"] = diagnostics
    state["execution_mode"] = "diagnostic"
    state["sql_source"] = "governed_metric_template"
    state["sql"] = None
    state["sql_list"] = []
    state["report"] = _diagnostic_report(diagnostics)
    state["chart"] = {"type": "table", "data": [_diagnostic_row(item) for item in diagnostics]}
    abnormal = [item for item in diagnostics if item.get("status") in {"SIGNIFICANT_DECLINE", "SIGNIFICANT_INCREASE"}]
    add_step(
        state["execution_plan"],
        "anomaly_diagnosis",
        "SUCCESS" if not abnormal else "ALERT",
        "Governed metric diagnostics completed",
        {
            "metrics": keys,
            "statuses": [item.get("status") for item in diagnostics],
            "abnormalCount": len(abnormal),
            "subAgent": "anomaly_diagnosis",
        },
    )
    state["status"] = "SUCCESS"
    state["result"] = finalize_result(state)
    return state


def _diagnostic_report(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    abnormal = [item for item in diagnostics if item.get("status") in {"SIGNIFICANT_DECLINE", "SIGNIFICANT_INCREASE"}]
    insufficient = [item for item in diagnostics if item.get("status") == "INSUFFICIENT_DATA"]
    rejected = [item for item in diagnostics if item.get("status") not in {"SIGNIFICANT_DECLINE", "SIGNIFICANT_INCREASE", "NO_SIGNIFICANT_DECLINE", "INSUFFICIENT_DATA"}]
    if abnormal:
        summary = _diagnostic_summary(abnormal)
        suggestions = [
            {
                "action": "manual_review",
                "reason": f"{_metric_key(item)} 相对基线出现显著波动，需要人工排查归因。",
                "priority": "HIGH",
            }
            for item in abnormal[:3]
        ]
    elif insufficient:
        summary = "运营指标诊断：当前或基线样本不足，暂不下结论。建议等待更多数据或调整窗口。"
        suggestions = [{"action": "expand_time_range", "reason": "样本量低于指标定义的最小值。", "priority": "MEDIUM"}]
    elif rejected:
        summary = "运营指标诊断：部分指标不可用（未注册或查询失败），无法完成完整诊断。"
        suggestions = [{"action": "review_metric_registry", "reason": "指标不在受控注册表中。", "priority": "LOW"}]
    else:
        summary = "运营指标诊断：全部指标相对基线未见显著异常，处于正常波动范围。"
        suggestions = [{"action": "monitor", "reason": "指标健康，保持例行观察。", "priority": "LOW"}]
    insights = [item.get("finding") for item in diagnostics if item.get("finding")]
    return {
        "summary": summary,
        "insights": insights or [f"完成 {len(diagnostics)} 个受控指标对比。"],
        "suggestions": suggestions,
        "diagnostics": diagnostics,
    }


def _diagnostic_row(item: dict[str, Any]) -> dict[str, Any]:
    evidence = item.get("evidence") or {}
    return {
        "metric": _metric_key(item),
        "status": item.get("status"),
        "current": evidence.get("current"),
        "baseline": evidence.get("baseline"),
        "relativeChange": evidence.get("relativeChange"),
        "confidence": item.get("confidence"),
    }


def _diagnostic_summary(abnormal: list[dict[str, Any]]) -> str:
    parts = []
    for item in abnormal[:3]:
        metric = _metric_key(item)
        evidence = item.get("evidence") or {}
        current = evidence.get("currentValue")
        baseline = evidence.get("baselineMean")
        parts.append(
            f"{metric} 当前 {current:.3f} vs 基线 {baseline:.3f}"
            if current is not None and baseline is not None
            else f"{metric} 出现异常波动"
        )
    return "运营指标异常：" + "；".join(parts) + "，建议优先排查。"


def _metric_key(item: dict[str, Any]) -> str:
    """Return the metric key from a diagnostics item (metric may be str or dict)."""
    metric = item.get("metric") or {}
    if isinstance(metric, dict):
        return str(metric.get("key") or "metric")
    return str(metric or "metric")


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


def _tool_message(tool_call_id: str, result: Any) -> Any:
    content = json.dumps(_compact_tool_result(result), ensure_ascii=False, default=str)
    try:
        from langchain_core.messages import ToolMessage

        return ToolMessage(content=content, tool_call_id=tool_call_id)
    except Exception:
        return {"role": "tool", "tool_call_id": tool_call_id, "content": content}


def _compact_tool_result(result: Any) -> Any:
    if isinstance(result, dict) and isinstance(result.get("data"), list):
        return {**result, "data": result["data"][:10]}
    return result


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


def normalize_analysis_spec(payload: dict[str, Any], question: str, intent: str) -> dict[str, Any]:
    """Normalize request slots before choosing a SQL template.

    A template is eligible only when every parsed filter is explicitly supported.
    This prevents a broad label such as HOT_ARTICLE from silently discarding a
    user's time range or other requested analytical constraint.
    """
    limit = _bounded_limit(payload.get("limit"), extract_requested_limit(question))
    time_range = normalize_time_range(payload.get("timeRange") or extract_time_range(question))
    filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
    normalized_filters = {key: value for key, value in filters.items() if value not in (None, "", [], {})}
    if time_range:
        normalized_filters["timeRange"] = time_range
    unsupported = detect_template_unsupported_requirements(question)
    if unsupported:
        normalized_filters["unsupportedRequirements"] = unsupported
    return {
        "intent": intent,
        "metrics": payload.get("metrics") if isinstance(payload.get("metrics"), list) else [],
        "dimension": str(payload.get("dimension") or "article"),
        "timeRange": time_range,
        "filters": normalized_filters,
        "limit": limit,
    }


def detect_template_unsupported_requirements(question: str) -> list[str]:
    """Conservatively keep complex requests off a simple SQL template."""
    normalized = question.lower()
    markers = {
        "tagFilter": ("标签为", "分类为", "主题为", "tag=", "category="),
        "authorFilter": ("作者", "用户", "user id", "author id"),
        "exclusion": ("排除", "不含", "除外", "except", "exclude"),
        "comparison": ("同比", "环比", "对比", "compare"),
        "advancedMetric": ("平均", "转化", "留存", "复购", "漏斗"),
    }
    return [name for name, values in markers.items() if any(value in normalized or value in question for value in values)]


def template_path_enabled(analysis_spec: dict[str, Any], confidence: float) -> bool:
    if not settings.analytics_low_cost_mode:
        return False
    intent = analysis_spec.get("intent", "CUSTOM_SQL")
    if intent not in TEMPLATE_INTENTS or confidence < TEMPLATE_CONFIDENCE_THRESHOLD:
        return False
    if intent == "OVERVIEW":
        return True
    supported_filters = {"timeRange"}
    filters = analysis_spec.get("filters") or {}
    if set(filters) - supported_filters:
        return False
    # A metric/dimension requested by the user can make a generic template
    # semantically wrong even if keyword routing recognised the broad intent.
    # Field-selection metrics (e.g. "标题, 发布时间" for RECENT_CONTENT) are
    # allowed when the template already returns those columns.
    metrics = analysis_spec.get("metrics") or []
    template_fields = _template_return_fields(intent)
    if metrics and (not template_fields or not set(metrics) <= template_fields):
        return False
    return analysis_spec.get("dimension", "article") in {"article", "unknown", ""}


def _template_return_fields(intent: str) -> set[str]:
    """Columns a template SQL returns, used to allow field-selection metrics."""
    fields: dict[str, set[str]] = {
        "HOT_ARTICLE": {"id", "title", "thumbCount", "tags", "createTime"},
        "LOW_INTERACTION": {"id", "title", "thumbCount", "tags", "createTime"},
        "RECENT_CONTENT": {"id", "title", "thumbCount", "tags", "createTime"},
        "CONTENT_GROWTH": {"day", "date", "articleCount", "count"},
        "TAG_DISTRIBUTION": {"tags", "articleCount"},
        "COMMENT_QUALITY": {"blog_id", "commentCount", "avgSentiment", "flaggedCount"},
        "OVERVIEW": {"blogCount", "commentCount", "thumbCount", "blog_count", "comment_count", "thumb_count"},
    }
    return fields.get(intent, set())


def extract_requested_limit(question: str, default: int = DEFAULT_ANALYTICS_LIMIT) -> int:
    patterns = [
        r"\btop\s*(\d+)\b",
        r"\bfirst\s*(\d+)\b",
        r"(?:前|top)\s*(\d+)\s*(?:篇|条|个)?",
        r"(?:最高|热门|最多|最新|最近).{0,12}?(\d+)\s*(?:篇|条|个)",
        r"(\d+)\s*(?:篇|条|个)(?:文章|内容|博客)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, question, flags=re.IGNORECASE)
        if match:
            return _bounded_limit(match.group(1), default)
    return default


def extract_time_range(question: str) -> dict[str, Any] | None:
    normalized = question.lower()
    match = re.search(r"(?:近|最近|过去|last)\s*(\d+)\s*(?:天|日|days?)", normalized, flags=re.IGNORECASE)
    if match:
        return {"type": "relative_days", "value": min(max(int(match.group(1)), 1), 365)}
    if "本周" in question or "this week" in normalized:
        return {"type": "current_week"}
    if "本月" in question or "this month" in normalized:
        return {"type": "current_month"}
    if "今天" in question or "today" in normalized:
        return {"type": "today"}
    return None


def normalize_time_range(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    kind = str(value.get("type") or "").lower()
    if kind == "relative_days":
        return {"type": kind, "value": _bounded_limit(value.get("value"), 1, maximum=365)}
    if kind in {"current_week", "current_month", "today"}:
        return {"type": kind}
    return None


def _time_range_sql(time_range: dict[str, Any], column: str) -> str:
    if not time_range:
        return ""
    kind = time_range.get("type")
    if kind == "relative_days":
        return f" WHERE {column} >= DATE_SUB(NOW(), INTERVAL {int(time_range['value'])} DAY)"
    if kind == "current_week":
        return f" WHERE {column} >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY)"
    if kind == "current_month":
        return f" WHERE {column} >= DATE_FORMAT(CURDATE(), '%Y-%m-01')"
    if kind == "today":
        return f" WHERE {column} >= CURDATE()"
    return ""


def detect_intent(question: str) -> dict[str, Any]:
    if _is_multi_entity_question(question):
        return {
            "intent": "CUSTOM_SQL",
            "confidence": 0.35,
            "metrics": [],
            "dimension": "unknown",
            "reason": "Multi-entity overview question routed to custom SQL",
            "candidates": [],
            "limit": extract_requested_limit(question),
            "timeRange": extract_time_range(question),
            "filters": {},
            "llmSkipped": True,
        }
    candidates = rule_intent_candidates(question)
    fallback_intent = candidates[0]["intent"] if candidates else "CUSTOM_SQL"
    fallback_confidence = candidates[0]["confidence"] if candidates else 0.35
    fallback = {
        "intent": fallback_intent,
        "confidence": fallback_confidence,
        "metrics": [],
        "dimension": "unknown",
        "reason": "Fallback intent classification",
        "candidates": candidates,
        "limit": extract_requested_limit(question),
        "timeRange": extract_time_range(question),
        "filters": {},
    }
    if (
        settings.analytics_low_cost_mode
        and fallback_intent in TEMPLATE_INTENTS
        and fallback_confidence >= TEMPLATE_CONFIDENCE_THRESHOLD
    ):
        verify = _verify_template_intent(question, fallback_intent, candidates)
        fallback["templateVerify"] = verify
        if verify.get("confirmed"):
            fallback["reason"] = "Rule intent verified by LLM; template path"
            fallback["llmSkipped"] = True
            return fallback
        fallback["reason"] = f"Template candidate rejected by verifier: {verify.get('reason')}"
        fallback["llmSkipped"] = False
        # Fall through to the full LLM classification; a rejected or unavailable
        # verifier must not silently send the user down the wrong template.
    result = llm_client.complete_json(
        render_prompt("intent_clarification") or "Classify the admin analytics question.",
        f"{SCHEMA_CONTEXT}\nRule candidates: {candidates}\nQuestion: {question}",
        fallback,
    )
    result["intent"] = normalize_intent(result.get("intent"))
    result["confidence"] = _bounded_float(result.get("confidence"), fallback_confidence)
    result["candidates"] = candidates
    result["limit"] = _bounded_limit(result.get("limit"), fallback["limit"])
    result["timeRange"] = normalize_time_range(result.get("timeRange") or fallback["timeRange"])
    result["filters"] = result.get("filters") if isinstance(result.get("filters"), dict) else {}
    if fallback.get("templateVerify"):
        result["templateVerify"] = fallback["templateVerify"]
        result["llmSkipped"] = bool(fallback.get("llmSkipped", False))
    return result


def _verify_template_intent(question: str, intent: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """One LLM call to confirm a rule-matched template before the fast path."""
    if not settings.analytics_template_verify:
        return {"confirmed": True, "reason": "verifier-disabled"}
    if intent == "OVERVIEW":
        # The OVERVIEW template is forced by product design; keep it stable.
        return {"confirmed": True, "reason": "overview-forced-template"}
    if any(item.get("reason") == "negated-engagement" for item in candidates):
        # The rule already corrected a negated-engagement question (e.g. "点赞最少"
        # -> LOW_INTERACTION). A verifier viewing it from the original HOT_ARTICLE
        # label would wrongly reject it; trust the corrected rule.
        return {"confirmed": True, "reason": "negated-engagement-rule-trusted"}
    if not llm_client.enabled:
        # No LLM is configured, so rules are the only signal; keep the fast path.
        return {"confirmed": True, "reason": "verifier-unavailable-trust-rules"}
    try:
        model = llm_factory(
            model=settings.llm_model,
            max_tokens=512,
            timeout=settings.analytics_template_verify_timeout,
        )
        if model is None:
            return {"confirmed": True, "reason": "verifier-unavailable-trust-rules"}
        response = model.invoke(
            [
                {"role": "system", "content": render_prompt("template_verifier") or "Verify the candidate intent."},
                {
                    "role": "user",
                    "content": f"{SCHEMA_CONTEXT}\nCandidate intent: {intent}\nRule candidates: {candidates}\nQuestion: {question}",
                },
            ]
        )
        text = str(getattr(response, "content", ""))
        payload = _json_from_text(text, {"confirmed": True, "intent": intent, "reason": "verify-unparseable-trust-rules"})
    except Exception as exc:
        return {"confirmed": True, "reason": f"verifier-error-trust-rules:{type(exc).__name__}"}
    confirmed = bool(payload.get("confirmed"))
    return {
        "confirmed": confirmed,
        "intent": str(payload.get("intent") or intent),
        "reason": str(payload.get("reason") or "")[:200],
    }


def _is_multi_entity_question(question: str) -> bool:
    """Detect overview questions that combine several content entities."""
    entities = ["博客", "文章", "内容", "评论", "点赞", "用户", "作者"]
    present = [item for item in entities if item in question]
    if len(present) < 2:
        return False
    # The OVERVIEW template covers blog/comment/thumb counts together, so a
    # question asking for those entities with an overview marker must stay on
    # the template path instead of being downgraded to custom SQL.
    overview_covered = {"博客", "文章", "内容", "评论", "点赞"}
    if set(present) <= overview_covered and any(marker in question for marker in ("概览", "运营情况", "全站", "整体")):
        return False
    if any(marker in question for marker in ("概览", "几个方面", "整体情况", "全站")):
        return True
    enumerators = ("和", "与", "、", "及", "以及")
    pattern = r"(?:{})".format("|".join(re.escape(item) for item in enumerators))
    for index, first in enumerate(present):
        for second in present[index + 1 :]:
            forward = re.search(
                rf"{re.escape(first)}.{{0,12}}?{pattern}.{{0,12}}?{re.escape(second)}",
                question,
            )
            backward = re.search(
                rf"{re.escape(second)}.{{0,12}}?{pattern}.{{0,12}}?{re.escape(first)}",
                question,
            )
            if forward or backward:
                return True
    return False


def rule_intent_candidates(question: str) -> list[dict[str, Any]]:
    lowered = question.lower()
    rules = [
        ("HOT_ARTICLE", ["hot", "top", "popular", "thumb", "like", "likes", "点赞", "热门", "最高"], 0.82),
        ("LOW_INTERACTION", ["low interaction", "few likes", "点赞少", "低点赞", "点赞低", "互动低", "低互动", "互动较低", "互动不高"], 0.82),
        ("COMMENT_QUALITY", ["comment quality", "sentiment", "flagged", "audit", "评论质量", "评论风险", "风险评论", "情感", "违规", "审核", "被标记"], 0.84),
        ("CONTENT_GROWTH", ["growth", "trend", "publish", "new posts", "新增", "增长", "趋势", "发布"], 0.78),
        ("TAG_DISTRIBUTION", ["tag", "tags", "category", "topic", "标签", "分类", "主题"], 0.78),
        ("RECENT_CONTENT", ["recent", "latest", "newest", "最近", "最新", "近期"], 0.76),
        ("OVERVIEW", ["overview", "概览", "运营情况", "全站情况", "整体情况", "整体数据"], 0.85),
    ]
    candidates = []
    for intent, keywords, confidence in rules:
        if not any(keyword in lowered or keyword in question for keyword in keywords):
            continue
        candidate = {"intent": intent, "confidence": confidence, "matched": True}
        if intent == "HOT_ARTICLE" and _has_negated_engagement(question):
            # "点赞最少 / 没有点赞 / 零赞" is a low-interaction request, not hot content.
            candidate = {"intent": "LOW_INTERACTION", "confidence": 0.84, "matched": True, "reason": "negated-engagement"}
        candidates.append(candidate)
    if any(item["intent"] == "RECENT_CONTENT" for item in candidates) and any(
        item["intent"] == "CONTENT_GROWTH" for item in candidates
    ):
        # "列出最近发布的博客标题" is a detail-list intent (RECENT_CONTENT),
        # not a trend aggregation. Listing verbs outrank the trend label.
        listing_markers = ("列出", "标题", "列表", "明细", "哪些", "什么", "list", "title")
        if any(marker in lowered or marker in question for marker in listing_markers):
            recent = next(item for item in candidates if item["intent"] == "RECENT_CONTENT")
            recent["confidence"] = max(recent.get("confidence", 0), 0.86)
    # Specific intents beat the broad OVERVIEW label when both match.
    specific = [item for item in candidates if item["intent"] != "OVERVIEW"]
    overview = [item for item in candidates if item["intent"] == "OVERVIEW"]
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, float]] = set()
    for item in sorted(specific, key=lambda item: item["confidence"], reverse=True) + overview:
        key = (item["intent"], item["confidence"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _has_negated_engagement(question: str) -> bool:
    lowered = question.lower()
    negations = ("最少", "最低", "低点赞", "点赞低", "没有", "为零", "为 0", "零赞", "很少", "无几", "none", "no likes", "zero")
    engagement = ("点赞", "like", "thumb", "赞")
    return any(marker in lowered or marker in question for marker in negations) and any(
        marker in lowered or marker in question for marker in engagement
    )


def metric_diagnostic_keys(question: str) -> list[str]:
    """Select governed diagnostics only when a question asks for a comparison.

    Ordinary analytics requests keep their existing single-query behaviour so
    the diagnostic layer is explicit about its extra read-only query cost.
    """
    lowered = question.lower()
    comparison_markers = ("anomaly", "decline", "drop", "downturn", "baseline", "异常", "下降", "下滑")
    if not any(marker in lowered or marker in question for marker in comparison_markers):
        return []
    keys: list[str] = []
    if any(marker in lowered or marker in question for marker in ("engagement", "interaction", "like", "点赞", "互动")):
        keys.append("engagement_rate")
    if any(marker in lowered or marker in question for marker in ("supply", "publish", "content volume", "供给", "发布量")):
        keys.append("content_supply")
    if any(marker in lowered or marker in question for marker in ("negative", "sentiment", "comment", "负向", "评论", "情感")):
        keys.append("negative_comment_rate")
    # A generic anomaly request gets the full governed health check, rather
    # than inventing a metric from the LLM's interpretation.
    return keys or ["engagement_rate", "content_supply", "negative_comment_rate"]


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
        "删掉",
        "移除",
        "清除",
        "清空",
        "修改",
          "改成",
          "改为",
          "设为",
          "设置为",
          "更新为",
          "修改为",
          "更新",
        "插入",
        "新增",
        "封禁",
        "下架",
        "隐藏",
    }
    return any(keyword in lowered or keyword in question for keyword in keywords)


def is_sensitive_data_request(question: str) -> bool:
    lowered = question.lower()
    sensitive = ("密码", "口令", "passwd", "password", "密钥", "secret", "jwt", "凭据", "credential", "token")
    return any(marker in lowered or marker in question for marker in sensitive)


def sql_from_template(intent: str, analysis_spec: dict[str, Any]) -> str | None:
    limit = _bounded_limit(analysis_spec.get("limit"), DEFAULT_ANALYTICS_LIMIT)
    time_range = analysis_spec.get("timeRange") or {}
    blog_time_filter = _time_range_sql(time_range, "createTime")
    comment_time_filter = _time_range_sql(time_range, "createdAt")
    if intent == "OVERVIEW":
        return (
            "SELECT (SELECT COUNT(*) FROM blog) AS blogCount, "
            "(SELECT COUNT(*) FROM comments WHERE is_deleted = 0) AS commentCount, "
            "(SELECT COUNT(*) FROM thumb) AS thumbCount LIMIT 1"
        )
    if intent == "HOT_ARTICLE":
        return f"SELECT id, title, thumbCount, tags, createTime FROM blog{blog_time_filter} ORDER BY thumbCount DESC LIMIT {limit}"
    if intent == "LOW_INTERACTION":
        return f"SELECT id, title, thumbCount, tags, createTime FROM blog{blog_time_filter} ORDER BY thumbCount ASC, createTime DESC LIMIT {limit}"
    if intent == "COMMENT_QUALITY":
        return (
            "SELECT blog_id, COUNT(*) AS commentCount, AVG(sentiment_score) AS avgSentiment, SUM(is_flagged) AS flaggedCount "
            f"FROM comments WHERE is_deleted = 0{comment_time_filter.replace(' WHERE ', ' AND ')} GROUP BY blog_id ORDER BY flaggedCount DESC, commentCount DESC "
            f"LIMIT {limit}"
        )
    if intent == "CONTENT_GROWTH":
        return f"SELECT DATE(createTime) AS day, COUNT(*) AS articleCount FROM blog{blog_time_filter} GROUP BY DATE(createTime) ORDER BY day DESC LIMIT {min(max(limit, 7), 30)}"
    if intent == "TAG_DISTRIBUTION":
        predicate = " WHERE tags IS NOT NULL AND tags <> ''"
        if blog_time_filter:
            predicate += blog_time_filter.replace(" WHERE ", " AND ")
        return f"SELECT tags, COUNT(*) AS articleCount FROM blog{predicate} GROUP BY tags ORDER BY articleCount DESC LIMIT {limit}"
    if intent == "RECENT_CONTENT":
        return f"SELECT id, title, thumbCount, tags, createTime FROM blog{blog_time_filter} ORDER BY createTime DESC LIMIT {limit}"
    return None


def sql_from_llm(
    question: str,
    intent_payload: dict[str, Any],
    analysis_plan: dict[str, Any],
    fallback: str,
) -> dict[str, Any]:
    result = llm_client.complete_json(
        (
            render_prompt("data_qa_agent", analytics_max_sql_count=settings.analytics_max_sql_count)
            or 'You are a safe MySQL analyst. Return JSON only: {"sqlList":["SELECT ... LIMIT 10"]}.'
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
        return {"type": "bar", "xField": "blog_id", "yField": "flaggedCount", "data": data}
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
    primary_data = data or next((item.get("data") or [] for item in (query_results or []) if item.get("data")), [])
    fallback = fallback_report(intent, primary_data)
    if not primary_data:
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
        render_prompt("report_generation") or "You are an operations analytics Agent. Return JSON with summary, insights, suggestions.",
        (
            f"Question: {question}\nIntent: {intent}\nPrimary SQL: {sql}\n"
            f"Analysis plan: {analysis_plan or {}}\nQuery results: {result_summary or primary_data[:20]}"
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
    first_row = data[0] if data else {}
    if intent in {"HOT_ARTICLE", "LOW_INTERACTION", "RECENT_CONTENT"} and "title" not in first_row:
        # The query returned article metadata (e.g. tags) without a title row;
        # fall back to a field-aware summary instead of the title-based wording.
        first_fields = "、".join(f"{key}={value}" for key, value in list(first_row.items())[:5]) if first_row else "无匹配行"
        return {
            "summary": f"查询完成：共返回 {len(data)} 行，首行数据为 {first_fields}。",
            "insights": [f"查询返回 {len(data)} 行（intent={intent}）。"],
            "suggestions": [{"action": "review_rows", "reason": "Use returned rows for follow-up analysis.", "priority": "LOW"}],
        }
    if intent == "HOT_ARTICLE":
        top = first_row
        total = sum(int(row.get("thumbCount") or 0) for row in data)
        summary = f"点赞最高的文章是《{top.get('title') or '-'}》（{top.get('thumbCount')} 赞），TOP{len(data)} 合计 {total} 赞。"
    elif intent == "OVERVIEW":
        row = first_row
        summary = (
            f"全站现有博客 {row.get('blogCount') or row.get('blog_count') or row.get('total_blogs') or 0} 篇、"
            f"评论 {row.get('commentCount') or row.get('comment_count') or 0} 条、"
            f"点赞 {row.get('thumbCount') or row.get('thumb_count') or 0} 次。"
        )
    elif intent == "LOW_INTERACTION":
        low = first_row
        summary = f"互动最低的文章是《{low.get('title') or '-'}》（{low.get('thumbCount')} 赞），建议优先关注这 {len(data)} 篇的选题与曝光。"
    elif intent == "COMMENT_QUALITY":
        flagged = sum(int(row.get("flaggedCount") or 0) for row in data)
        summary = f"评论质量分析：{len(data)} 个维度中 flagged 评论合计 {flagged} 条，需关注风险评论集中度。"
    elif intent == "CONTENT_GROWTH":
        days = [str(row.get("day") or row.get("date") or "") for row in data if row.get("day") or row.get("date")]
        total = sum(
            int(row.get("articleCount") or row.get("count") or row.get("commentCount") or 0)
            for row in data
        )
        if days:
            summary = f"最近内容共发布 {total} 篇，覆盖 {min(days)} 至 {max(days)} 的 {len(days)} 个发布日。"
        else:
            first = data[0] if data else {}
            first_fields = "、".join(f"{key}={value}" for key, value in list(first.items())[:4]) if first else "无匹配行"
            summary = f"趋势分析完成：共返回 {len(data)} 行，首行数据为 {first_fields}。"
    elif intent == "TAG_DISTRIBUTION":
        top = first_row
        summary = f"标签分布：最热标签为「{top.get('tags') or '-'}」（{top.get('articleCount')} 篇）。"
    else:
        first = data[0] if data else {}
        first_fields = "、".join(f"{key}={value}" for key, value in list(first.items())[:4]) if first else "无匹配行"
        summary = f"自定义分析完成：共返回 {len(data)} 行，首行数据为 {first_fields}。"
    suggestions_by_intent = {
        "HOT_ARTICLE": [{"action": "write_followup", "reason": "Top articles indicate proven audience interest.", "priority": "HIGH"}],
        "LOW_INTERACTION": [{"action": "improve_cta", "reason": "Low thumb count suggests weak interaction prompts.", "priority": "HIGH"}],
        "COMMENT_QUALITY": [{"action": "manual_review", "reason": "Flagged comments require moderation attention.", "priority": "HIGH"}],
    }
    return {
        "summary": summary,
        "insights": [f"查询返回 {len(data)} 行（intent={intent}），可按需追问具体维度。"],
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
    if "use_template_path" in state:
        return bool(state["use_template_path"])
    intent = state.get("intent", "CUSTOM_SQL")
    confidence = float(state.get("intent_confidence", 0.0) or 0.0)
    return template_path_enabled({"intent": intent, "filters": {}, "metrics": [], "dimension": "article"}, confidence)


def finalize_result(state: AnalyticsState) -> dict[str, Any]:
    data = state.get("data", [])
    sql = state.get("sql")
    intent = state.get("intent", "CUSTOM_SQL")
    confidence = estimate_confidence(sql or "", data, state.get("sql_source") or "unknown", float(state.get("intent_confidence", 0.0) or 0.0))
    report = state.get("report") or fallback_report(intent, data)
    sub_agent = "anomaly_diagnosis" if state.get("diagnostics") else (
        "data_qa_template" if state.get("sql_source") == "template" else "data_qa_agent"
    )
    supervisor = state.get("supervisor") or {}
    declaration = str(supervisor.get("declaration") or build_declaration(intent, state.get("analysis_spec"), data))
    if state.get("diagnostics"):
        keys = [_metric_key(item) for item in state["diagnostics"]]
        declaration = f"我将诊断：{' / '.join(filter(None, keys)) or '运营健康指标'}（当前 vs 基线对比）"
    return {
        "subAgent": sub_agent,
        "supervisor": supervisor or None,
        "memory": {
            "enabled": bool(state.get("memory", {}).get("enabled")),
            "longTermEntries": len(state.get("memory", {}).get("long_term") or []),
            "shortTurns": len(state.get("memory", {}).get("short_turns") or []),
            "sessionMemoryEntries": len(state.get("memory", {}).get("sessionMemory") or []),
        },
        "declaration": declaration,
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


DECLARATION_BUILDERS = {
    "OVERVIEW": lambda spec, data: "我将查询：全站内容概览（博客 / 评论 / 点赞数量）",
    "HOT_ARTICLE": lambda spec, data: f"我将查询：热门内容 TOP {int((spec or {}).get('limit') or 10)}（按点赞数排序）",
    "LOW_INTERACTION": lambda spec, data: f"我将查询：低互动内容 TOP {int((spec or {}).get('limit') or 10)}（按点赞数升序）",
    "COMMENT_QUALITY": lambda spec, data: f"我将查询：评论质量与风险（sentiment / flagged），汇总 {int((spec or {}).get('limit') or 10)} 个维度",
    "CONTENT_GROWTH": lambda spec, data: "我将查询：内容发布趋势（按日期统计发布量）",
    "TAG_DISTRIBUTION": lambda spec, data: f"我将查询：标签分布 TOP {int((spec or {}).get('limit') or 10)}",
    "RECENT_CONTENT": lambda spec, data: f"我将查询：最近发布内容 TOP {int((spec or {}).get('limit') or 10)}",
    "CUSTOM_SQL": lambda spec, data: "我将查询：根据你的问题生成自定义 SQL 分析",
}


def build_declaration(intent: str, analysis_spec: dict[str, Any] | None, data: list[dict[str, Any]]) -> str:
    builder = DECLARATION_BUILDERS.get(intent)
    text = builder(analysis_spec or {}, data or []) if builder else "我将查询：运营数据分析"
    time_range = (analysis_spec or {}).get("timeRange") or {}
    if time_range.get("type") == "relative_days":
        text += f"（最近 {time_range.get('value')} 天）"
    return text


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
    return extract_requested_limit(question, default)


def _bounded_limit(value: Any, default: int, maximum: int = MAX_ANALYTICS_LIMIT) -> int:
    try:
        return min(max(int(value), 1), maximum)
    except (TypeError, ValueError):
        return min(max(default, 1), maximum)


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
    report["summary"] = "无权限执行运营分析（NO_PERMISSION），仅管理员可访问。"
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


def _load_memory_context(user_id: int | None, session_id: str | None, question: str) -> dict[str, Any]:
    """Load L1 (long-term) and L2 (short-term) memory for the current session."""
    if not settings.analytics_memory_enabled:
        return {"enabled": False, "long_term": [], "short_turns": [], "sessionMemory": []}
    long_term = ops_memory.recall_long_term(
        user_id,
        question,
        top_k=settings.analytics_long_memory_top_k,
        min_importance=settings.analytics_long_memory_min_importance,
    )
    short_turns = ops_memory.get_short_turns(user_id, session_id) if session_id else []
    session_memory = ops_memory.list_session_memory(user_id, session_id) if session_id else []
    return {
        "enabled": True,
        "long_term": long_term,
        "short_turns": short_turns,
        "sessionMemory": session_memory,
        "redisAvailable": ops_memory.available,
    }


REFERENTIAL_MARKERS = ("刚才", "上面", "之前", "那篇", "那条", "上一篇", "上一条", "第一条", "最后一条", "它", "这")


def _referential_hint(question: str, short_turns: list[dict[str, Any]]) -> str:
    """Resolve pronouns like '刚才那篇' from the most recent short-term turns."""
    if not short_turns:
        return ""
    if not any(marker in question for marker in REFERENTIAL_MARKERS):
        return ""
    titles: list[str] = []
    lines = []
    for index, turn in enumerate(reversed(short_turns[-4:]), start=1):
        conclusion = str(turn.get("conclusion") or "").strip()
        question_text = str(turn.get("question") or "").strip()
        if not question_text:
            continue
        for match in re.findall(r"《([^》]+)》", conclusion):
            if match.strip() and match.strip() not in titles:
                titles.append(match.strip())
        if conclusion:
            lines.append(f"{index}. Q: {question_text[:80]} | 结论: {conclusion[:160]}")
        else:
            lines.append(f"{index}. Q: {question_text[:80]} | 结论: (无)")
    if not lines and not titles:
        return ""
    target = ""
    if titles:
        target = (
            f"用户指代的对象最可能是文章《{titles[0]}》。"
            "如果问题要求查看该文章的字段（如标签、发布时间），请直接用这个标题作为 WHERE 条件查询，"
            "而不是重新做热门排行等通用分析。\n"
        )
    return (
        "用户问题包含指代词（如「刚才那篇 / 第一条 / 它」），可能引用以下最近的对话轮次。"
        "请优先从这些结论中识别所指对象；如果问题要求查看具体文章的字段，请用结论中的标题去查询，而不是重新做一次通用分析。\n"
        + target
        + "\n".join(lines)
    )


def _referential_title(question: str, short_turns: list[dict[str, Any]]) -> str:
    """Return the concrete article title a pronoun refers to, if resolvable."""
    if not short_turns or not any(marker in question for marker in REFERENTIAL_MARKERS):
        return ""
    for turn in reversed(short_turns[-4:]):
        conclusion = str(turn.get("conclusion") or "")
        match = re.search(r"《([^》]+)》", conclusion)
        if match and match.group(1).strip():
            return match.group(1).strip()
    return ""


def _remember_turn(state: AnalyticsState, result: dict[str, Any]) -> None:
    """Persist the turn to short-term memory and consolidate when due."""
    session_id = state.get("session_id")
    user_id = state.get("user_id")
    if not settings.analytics_memory_enabled or not session_id:
        return
    turn = {
        "question": state.get("question", ""),
        "intent": result.get("intent", ""),
        "declaration": result.get("declaration", ""),
        "sql": result.get("sql") or "",
        "rowCount": len(result.get("data") or []),
        "conclusion": (result.get("report") or {}).get("summary", "") or result.get("insight", ""),
    }
    ops_memory.append_short_turn(user_id, session_id, turn, keep=settings.analytics_short_memory_turns)
    turns = ops_memory.get_short_turns(user_id, session_id)
    if len(turns) >= max(settings.analytics_short_memory_turns, 1):
        # Consolidation runs off the request path; a slow or failing LLM call
        # must never add latency to the analytics answer.
        threading.Thread(
            target=_consolidate_async,
            args=(user_id, session_id, turns),
            name="ops-memory-consolidation",
            daemon=True,
        ).start()


def _consolidate_async(user_id: int | None, session_id: str | None, turns: list[dict[str, Any]]) -> None:
    try:
        consolidate_session_memory(user_id, session_id, turns)
    except Exception:
        return
