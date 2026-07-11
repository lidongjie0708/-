from __future__ import annotations

from typing import Any, Literal
import logging
import re
import uuid

from app.agents.analytics_agent import analyze_operation
from app.agents.rag_qa_agent import ask_blog_knowledge
from app.infra.auth import AgentPrincipal
from app.infra.llm import llm_client
from app.rag.memory import build_memory_context, conversation_memory


ChatMode = Literal["chat", "rag", "analytics"]
logger = logging.getLogger(__name__)

ROUTER_VERSION = "hybrid-v2"
HIGH_CONFIDENCE_SCORE = 0.78
HIGH_CONFIDENCE_MARGIN = 0.18
MEDIUM_CONFIDENCE_SCORE = 0.52
MEDIUM_CONFIDENCE_MARGIN = 0.10

RAG_STRONG_PATTERNS = (
    r"根据.{0,8}(博客|文章|知识库|文档)",
    r"(博客|文章|知识库|文档)(中|里|内|提到|介绍|怎么说)",
    r"(这篇|那篇|上述)(博客|文章|内容)",
    r"(检索|搜索|查找).{0,8}(博客|文章|知识库)",
    r"\b(according to|search|retrieve).{0,20}(blog|article|knowledge base|document)",
)
RAG_ENTITY_HINTS = (
    "博客", "文章", "知识库", "文档", "作者", "引用", "出处",
    "blog", "article", "knowledge base", "document", "citation",
)
RAG_ACTION_HINTS = (
    "有哪些", "讲了什么", "提到", "介绍", "总结", "查找", "搜索", "根据",
    "find", "search", "summarize", "according",
)
ANALYTICS_STRONG_PATTERNS = (
    r"(点赞|评论|用户|文章).{0,8}(最多|最少|排行|排名|趋势|增长|下降|统计|数量|占比)",
    r"(最近|本周|本月|今天|昨日).{0,8}(活跃|新增|发布|点赞|评论|趋势)",
    r"(统计|分析|对比).{0,8}(用户|文章|点赞|评论|标签|运营|数据)",
    r"\b(top|rank|ranking|trend|growth|count|active).{0,20}(user|blog|article|thumb|comment)",
)
ANALYTICS_METRIC_HINTS = (
    "最多", "最少", "排行", "排名", "趋势", "增长", "下降", "数量", "多少",
    "占比", "分布", "平均", "总数", "活跃", "新增", "统计", "指标",
    "top", "rank", "trend", "growth", "count", "average", "distribution",
)
ANALYTICS_ENTITY_HINTS = (
    "用户", "文章", "博客", "点赞", "评论", "标签", "发布", "运营",
    "user", "article", "blog", "thumb", "comment", "tag",
)
EXPLANATION_HINTS = (
    "是什么", "什么意思", "原理", "怎么实现", "如何实现", "介绍一下",
    "what is", "how does", "explain",
)


def route_chat(message: str, requested_mode: str, principal: AgentPrincipal) -> dict[str, Any]:
    if requested_mode in {"chat", "rag", "analytics"}:
        mode = requested_mode
        if mode == "analytics" and principal.role.upper() != "ADMIN":
            return _decision(
                "analytics", 1.0, "explicit:analytics-denied", {"analytics": 1.0},
                policy="explicit", denied=True,
            )
        return _decision(mode, 1.0, f"explicit:{mode}", {mode: 1.0}, policy="explicit")

    normalized = " ".join(message.lower().split())
    scores = {
        "chat": 0.20,
        "rag": _intent_score(normalized, RAG_STRONG_PATTERNS, RAG_ENTITY_HINTS, RAG_ACTION_HINTS),
        "analytics": _intent_score(
            normalized,
            ANALYTICS_STRONG_PATTERNS,
            ANALYTICS_ENTITY_HINTS,
            ANALYTICS_METRIC_HINTS,
        ),
    }

    # Questions explaining a concept are ordinary chat unless they explicitly
    # ask for information from blog content or for a measurable system metric.
    if any(hint in normalized for hint in EXPLANATION_HINTS):
        scores["chat"] += 0.35
        scores["rag"] = max(0.0, scores["rag"] - 0.18)
        scores["analytics"] = max(0.0, scores["analytics"] - 0.18)
    if "sql" in normalized or "数据库" in normalized:
        scores["analytics"] += 0.20

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_mode, top_score = ranked[0]
    margin = top_score - ranked[1][1]
    if top_score >= HIGH_CONFIDENCE_SCORE and margin >= HIGH_CONFIDENCE_MARGIN:
        return _authorized_decision(
            top_mode, min(top_score, 0.99), "rules:high-confidence", scores, principal,
            policy="rules",
        )

    llm_evidence = _llm_route(normalized, scores, principal)
    if llm_evidence:
        llm_mode = llm_evidence["mode"]
        llm_confidence = llm_evidence["confidence"]
        if llm_mode == top_mode:
            fused_confidence = min(0.99, 0.55 * llm_confidence + 0.45 * top_score)
            if fused_confidence >= 0.60:
                return _authorized_decision(
                    llm_mode,
                    fused_confidence,
                    f"fusion:agreement:{llm_evidence['reason']}",
                    scores,
                    principal,
                    policy="fusion",
                    classifier=llm_evidence,
                )
        elif top_score >= MEDIUM_CONFIDENCE_SCORE and llm_confidence >= 0.72:
            return _clarification_decision(scores, top_mode, llm_mode, "fusion:conflict")
        elif top_score < MEDIUM_CONFIDENCE_SCORE and llm_confidence >= 0.80:
            return _authorized_decision(
                llm_mode,
                llm_confidence * 0.85,
                f"llm:strong:{llm_evidence['reason']}",
                scores,
                principal,
                policy="llm",
                classifier=llm_evidence,
            )

    if top_score >= MEDIUM_CONFIDENCE_SCORE and margin >= MEDIUM_CONFIDENCE_MARGIN:
        return _authorized_decision(
            top_mode, min(top_score, 0.85), "rules:medium-confidence", scores, principal,
            policy="rules",
        )
    if scores["rag"] >= 0.34 and scores["analytics"] >= 0.34:
        return _clarification_decision(scores, "rag", "analytics", "rules:multi-intent")
    return _decision("chat", 0.45, "fallback:ambiguous", scores, policy="fallback")


def run_unified_chat(
    message: str,
    requested_mode: str,
    session_id: str | None,
    principal: AgentPrincipal,
) -> dict[str, Any]:
    trace_id = str(uuid.uuid4())
    decision = route_chat(message, requested_mode, principal)
    mode = decision["mode"]
    route_reason = decision["reason"]
    if decision.get("needsClarification"):
        return _result(
            mode="chat",
            answer=decision["clarificationQuestion"],
            trace_id=trace_id,
            route_reason=route_reason,
            route_confidence=decision["confidence"],
            route_candidates=decision["candidates"],
            details={"routeDecision": decision},
        )
    if mode == "analytics" and principal.role.upper() != "ADMIN":
        return _result(
            mode=mode,
            answer="运营分析仅对管理员开放。",
            trace_id=trace_id,
            route_reason=route_reason,
            route_confidence=decision["confidence"],
            route_candidates=decision["candidates"],
            error="NO_PERMISSION",
        )
    if mode == "rag":
        try:
            rag = ask_blog_knowledge(
                message,
                principal.user_id,
                principal.role,
                ["PUBLIC", "PRIVATE"] if principal.role.upper() == "ADMIN" else ["PUBLIC"],
                session_id,
            )
            return _result(
                mode=mode,
                answer=str(rag.get("answer") or ""),
                trace_id=trace_id,
                route_reason=route_reason,
                route_confidence=decision["confidence"],
                route_candidates=decision["candidates"],
                citations=rag.get("citations") or [],
                confidence=rag.get("confidence"),
                details=rag,
                warning=(
                    "Redis 会话存储暂时不可用，本次 RAG 回答未写入会话历史。"
                    if session_id and not rag.get("memoryPersistence", {}).get("saved")
                    else None
                ),
            )
        except Exception as exc:
            # The chat surface remains useful when vector infrastructure is
            # temporarily unavailable, while making the degradation explicit.
            fallback, memory_warning = _ordinary_chat(message, session_id, principal)
            return _result(
                mode="chat",
                answer=fallback,
                trace_id=trace_id,
                route_reason=f"{route_reason}:rag-degraded",
                route_confidence=decision["confidence"],
                route_candidates=decision["candidates"],
                warning=_merge_warnings(
                    f"知识库暂时不可用，本次已降级为普通聊天：{exc}",
                    memory_warning,
                ),
                degraded_from="rag",
            )
    if mode == "analytics":
        analytics = analyze_operation(message, principal.role, principal.user_id)
        answer = (
            analytics.get("report", {}).get("insight")
            or analytics.get("insight")
            or analytics.get("error")
            or "运营分析已完成。"
        )
        return _result(
            mode=mode,
            answer=str(answer),
            trace_id=trace_id,
            route_reason=route_reason,
            route_confidence=decision["confidence"],
            route_candidates=decision["candidates"],
            chart=analytics.get("chart"),
            details=analytics,
            error=analytics.get("error"),
        )
    answer, memory_warning = _ordinary_chat(message, session_id, principal)
    return _result(
        mode="chat",
        answer=answer,
        trace_id=trace_id,
        route_reason=route_reason,
        route_confidence=decision["confidence"],
        route_candidates=decision["candidates"],
        warning=memory_warning,
    )


def _ordinary_chat(message: str, session_id: str | None, principal: AgentPrincipal) -> tuple[str, str | None]:
    memory = build_memory_context(session_id, principal.user_id)
    answer = llm_client.complete(
        (
            "你是 BlogsLike 的通用聊天助手。自然、准确地回答用户问题。"
            "不要声称查询了知识库或数据库；需要这些能力时建议用户切换相应模式。"
        ),
        f"最近对话：\n{memory.get('summary', '')}\n\n用户：{message}",
    )
    saved = conversation_memory.append(session_id, message, answer, [], principal.user_id)
    warning = None
    if session_id and (not memory.get("storageAvailable") or not saved):
        warning = "Redis 会话存储暂时不可用，本次以无上下文模式回答，消息未持久化。"
    if llm_client.degraded:
        warning = _merge_warnings(
            warning,
            f"LLM 暂不可用，已使用本地 fallback 响应：{llm_client.degraded_reason}",
        )
    return answer, warning


def _merge_warnings(*warnings: str | None) -> str | None:
    values = [item for item in warnings if item]
    return "；".join(values) if values else None


def _intent_score(
    message: str,
    strong_patterns: tuple[str, ...],
    entity_hints: tuple[str, ...],
    action_hints: tuple[str, ...],
) -> float:
    score = 0.0
    if any(re.search(pattern, message, flags=re.IGNORECASE) for pattern in strong_patterns):
        score += 0.62
    entity_hits = sum(1 for hint in entity_hints if hint in message)
    action_hits = sum(1 for hint in action_hints if hint in message)
    score += min(entity_hits, 2) * 0.14
    score += min(action_hits, 2) * 0.14
    if entity_hits and action_hits:
        score += 0.12
    return min(score, 1.0)


def _llm_route(
    message: str,
    rule_scores: dict[str, float],
    principal: AgentPrincipal,
) -> dict[str, Any] | None:
    if not llm_client.enabled:
        return None
    fallback = {"mode": "chat", "confidence": 0.4, "reason": "llm-invalid"}
    payload = llm_client.complete_json(
        (
            "Classify a BlogsLike assistant request. Return JSON only with mode, confidence, reason. "
            "mode must be chat, rag, or analytics. Use rag only when the user asks to retrieve or summarize "
            "blog knowledge. Use analytics only for measurable platform data, rankings, trends, counts, or "
            "operational metrics. Explanations and casual questions are chat."
        ),
        f"User role: {principal.role}\nRule scores: {rule_scores}\nMessage: {message}",
        fallback,
    )
    mode = str(payload.get("mode") or "chat").lower()
    if mode not in {"chat", "rag", "analytics"}:
        mode = "chat"
    try:
        confidence = max(0.0, min(float(payload.get("confidence", 0.4)), 1.0))
    except (TypeError, ValueError):
        confidence = 0.4
    if confidence < 0.55:
        return None
    if mode == "analytics" and principal.role.upper() != "ADMIN":
        mode = "chat"
    return {
        "mode": mode,
        "confidence": confidence,
        "reason": str(payload.get("reason") or "classified")[:160],
    }


def _authorized_decision(
    mode: str,
    confidence: float,
    reason: str,
    candidates: dict[str, float],
    principal: AgentPrincipal,
    **metadata: Any,
) -> dict[str, Any]:
    if mode == "analytics" and principal.role.upper() != "ADMIN":
        return _decision(
            "chat", confidence, f"{reason}:analytics-denied-fallback", candidates,
            policy="authorization",
        )
    return _decision(mode, confidence, reason, candidates, **metadata)


def _decision(
    mode: str,
    confidence: float,
    reason: str,
    candidates: dict[str, float],
    **metadata: Any,
) -> dict[str, Any]:
    decision = {
        "mode": mode,
        "confidence": round(confidence, 4),
        "reason": reason,
        "candidates": {key: round(value, 4) for key, value in candidates.items()},
        "routerVersion": ROUTER_VERSION,
        "needsClarification": False,
        **metadata,
    }
    logger.info(
        "agent_route version=%s mode=%s confidence=%.4f reason=%s policy=%s",
        ROUTER_VERSION,
        mode,
        confidence,
        reason,
        decision.get("policy", "unknown"),
    )
    return decision


def _clarification_decision(
    candidates: dict[str, float],
    first_mode: str,
    second_mode: str,
    reason: str,
) -> dict[str, Any]:
    labels = {"rag": "从博客知识库查资料", "analytics": "统计平台运营数据", "chat": "普通解释"}
    decision = _decision(
        "chat",
        0.0,
        reason,
        candidates,
        policy="abstain",
        needsClarification=True,
        suggestedModes=[first_mode, second_mode],
    )
    decision["clarificationQuestion"] = (
        f"这个问题可能有两种理解：你想{labels[first_mode]}，"
        f"还是想{labels[second_mode]}？"
    )
    return decision


def _result(
    *,
    mode: str,
    answer: str,
    trace_id: str,
    route_reason: str,
    route_confidence: float = 1.0,
    route_candidates: dict[str, float] | None = None,
    citations: list[dict[str, Any]] | None = None,
    chart: dict[str, Any] | None = None,
    confidence: Any = None,
    details: dict[str, Any] | None = None,
    warning: str | None = None,
    error: str | None = None,
    degraded_from: str | None = None,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "answer": answer,
        "citations": citations or [],
        "chart": chart,
        "confidence": confidence,
        "traceId": trace_id,
        "routeReason": route_reason,
        "routeConfidence": route_confidence,
        "routeCandidates": route_candidates or {},
        "warning": warning,
        "error": error,
        "degradedFrom": degraded_from,
        "degraded": degraded_from is not None or warning is not None,
        "responseMode": "degraded" if degraded_from is not None or warning is not None else "normal",
        "details": details or {},
        "suggestions": _suggestions(mode),
    }


def _suggestions(mode: str) -> list[str]:
    if mode == "rag":
        return ["继续追问相关博客", "查看引用文章", "切换普通聊天"]
    if mode == "analytics":
        return ["查看趋势", "按时间范围分析", "查看执行明细"]
    return ["使用知识库回答", "换一种方式解释", "继续追问"]
