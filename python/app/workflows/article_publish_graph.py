from __future__ import annotations

import time
import uuid
from typing import Any

from app.agents.audit_agent import audit_content
from app.agents.seo_agent import optimize_seo
from app.agents.writing_agent import generate_article
from app.rag.retriever import retrieve_blog_context
from app.schemas.state import ArticleWorkflowState
from app.tools.article_tool import build_publish_result


def _log(state: ArticleWorkflowState, node: str, status: str, message: str) -> None:
    state.setdefault("logs", []).append(
        {
            "node": node,
            "status": status,
            "message": message,
            "createdAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    state["current_node"] = node


def planner_node(state: ArticleWorkflowState) -> ArticleWorkflowState:
    _log(state, "Planner", "RUNNING", "开始规划文章生产任务")
    state["plan"] = {
        "goal": f"围绕 {state['topic']} 生成一篇{state.get('style', '技术博客')}",
        "steps": ["检索历史文章", "生成正文", "SEO 优化", "内容审核", "发布决策"],
    }
    _log(state, "Planner", "SUCCESS", "文章规划完成")
    return state


def retriever_node(state: ArticleWorkflowState) -> ArticleWorkflowState:
    _log(state, "Retriever", "RUNNING", "检索历史相关文章")
    docs = retrieve_blog_context(
        f"{state['topic']} {' '.join(state.get('keywords', []))}",
        user_id=state.get("user_id"),
        role=state.get("role", "USER"),
        visible_scopes=["PUBLIC"],
    )
    state["retrieved_docs"] = docs
    _log(state, "Retriever", "SUCCESS", f"检索到 {len(docs)} 条上下文")
    return state


def writer_node(state: ArticleWorkflowState) -> ArticleWorkflowState:
    _log(state, "Writer", "RUNNING", "生成文章大纲和正文")
    result = generate_article(state["topic"], state.get("keywords", []), state.get("style", "技术博客"))
    state["outline"] = result.get("outline", [])
    state["content"] = result.get("content", "")
    _log(state, "Writer", "SUCCESS", "正文生成完成")
    return state


def seo_node(state: ArticleWorkflowState) -> ArticleWorkflowState:
    _log(state, "SEO", "RUNNING", "生成 SEO 元数据和内部链接")
    title = state.get("topic", "未命名文章")
    state["seo"] = optimize_seo(title, state.get("content", ""), state.get("keywords", []))
    _log(state, "SEO", "SUCCESS", "SEO 优化完成")
    return state


def audit_node(state: ArticleWorkflowState) -> ArticleWorkflowState:
    _log(state, "Audit", "RUNNING", "执行内容审核")
    state["audit"] = audit_content("article", state.get("content", ""), state.get("user_id"))
    _log(state, "Audit", "SUCCESS", f"审核完成：{state['audit'].get('riskLevel')}")
    return state


def publish_node(state: ArticleWorkflowState) -> ArticleWorkflowState:
    _log(state, "Publish", "RUNNING", "执行发布决策")
    state["publish_result"] = build_publish_result(state.get("audit", {}), state.get("auto_publish", False))
    state["status"] = "COMPLETED"
    _log(state, "Publish", "SUCCESS", state["publish_result"]["message"])
    return state


def human_review_node(state: ArticleWorkflowState) -> ArticleWorkflowState:
    _log(state, "HumanReview", "SUCCESS", "已进入人工审核队列")
    state["publish_result"] = {"decision": "HUMAN_REVIEW", "message": "内容需要人工审核。"}
    state["status"] = "WAITING_HUMAN_REVIEW"
    return state


def reject_node(state: ArticleWorkflowState) -> ArticleWorkflowState:
    _log(state, "Reject", "SUCCESS", "内容被审核拦截")
    state["publish_result"] = {"decision": "REJECT", "message": state.get("audit", {}).get("reason", "内容风险较高。")}
    state["status"] = "REJECTED"
    return state


def route_after_audit(state: ArticleWorkflowState) -> str:
    risk = state.get("audit", {}).get("riskLevel", "MEDIUM")
    if risk == "LOW":
        return "publish"
    if risk == "MEDIUM":
        return "human_review"
    return "reject"


def build_graph():
    try:
        from langgraph.graph import END, START, StateGraph

        graph = StateGraph(ArticleWorkflowState)
        graph.add_node("planner", planner_node)
        graph.add_node("retriever", retriever_node)
        graph.add_node("writer", writer_node)
        graph.add_node("seo", seo_node)
        graph.add_node("audit", audit_node)
        graph.add_node("publish", publish_node)
        graph.add_node("human_review", human_review_node)
        graph.add_node("reject", reject_node)
        graph.add_edge(START, "planner")
        graph.add_edge("planner", "retriever")
        graph.add_edge("retriever", "writer")
        graph.add_edge("writer", "seo")
        graph.add_edge("seo", "audit")
        graph.add_conditional_edges(
            "audit",
            route_after_audit,
            {"publish": "publish", "human_review": "human_review", "reject": "reject"},
        )
        graph.add_edge("publish", END)
        graph.add_edge("human_review", END)
        graph.add_edge("reject", END)
        return graph.compile()
    except Exception:
        return None


compiled_graph = build_graph()


def run_article_workflow(payload: dict[str, Any]) -> ArticleWorkflowState:
    state: ArticleWorkflowState = {
        "task_id": payload.get("task_id") or f"article-{uuid.uuid4().hex[:12]}",
        "user_id": payload["user_id"],
        "role": payload.get("role", "USER"),
        "topic": payload["topic"],
        "keywords": payload.get("keywords", []),
        "style": payload.get("style", "技术博客"),
        "auto_publish": payload.get("auto_publish", False),
        "status": "RUNNING",
        "current_node": "START",
        "error": None,
        "logs": [],
        "retry_count": 0,
    }
    try:
        if compiled_graph:
            return compiled_graph.invoke(state)
        for node in [planner_node, retriever_node, writer_node, seo_node, audit_node]:
            state = node(state)
        route = route_after_audit(state)
        return {"publish": publish_node, "human_review": human_review_node, "reject": reject_node}[route](state)
    except Exception as exc:
        state["status"] = "FAILED"
        state["error"] = str(exc)
        _log(state, state.get("current_node", "UNKNOWN"), "FAILED", str(exc))
        return state
