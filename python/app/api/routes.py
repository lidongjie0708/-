from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.agents.analytics_agent import analyze_operation
from app.agents.chat_orchestrator import route_chat, run_unified_chat
from app.agents.audit_agent import audit_comment, audit_content
from app.agents.rag_qa_agent import ask_blog_knowledge, stream_blog_knowledge
from app.agents.seo_agent import optimize_seo
from app.agents.writing_agent import generate_article, recommend_tags, summarize
from app.config import settings
from app.infra.task_store import task_store
from app.infra.llm import llm_client
from app.rag.memory import build_memory_context, conversation_memory
from app.infra.auth import AgentPrincipal, verify_agent_token
from app.rag.document_sync import sync_blog_incremental
from app.rag.evaluation_runner import run_rag_evaluation
from app.schemas.request import (
    AgentRequest,
    AnalyticsRequest,
    ChatRequest,
    ArticleWorkflowRequest,
    AuditRequest,
    RagEvalRequest,
    RagAskRequest,
    SeoRequest,
    WritingRequest,
)
from app.schemas.response import AgentResponse, ApiResponse
from app.workflows.article_publish_graph import run_article_workflow


router = APIRouter(prefix="/api/agent", tags=["agent"])


def _rag_visible_scopes(principal: AgentPrincipal, requested: list[str] | None) -> list[str]:
    if principal.role.upper() == "ADMIN":
        allowed = {"PUBLIC", "PRIVATE"}
        scopes = [scope.upper() for scope in (requested or ["PUBLIC", "PRIVATE"]) if scope.upper() in allowed]
        return scopes or ["PUBLIC", "PRIVATE"]
    return ["PUBLIC"]


def _verify_internal_embed_request(request: AgentRequest, internal_token: str | None) -> None:
    if request.action not in {"embed", "blog-process"}:
        return
    if not settings.internal_agent_token_required:
        return
    if not settings.internal_agent_token:
        raise HTTPException(status_code=500, detail="INTERNAL_AGENT_TOKEN is not configured")
    if internal_token != settings.internal_agent_token:
        raise HTTPException(status_code=403, detail="Invalid internal Agent token")


@router.post("/execute", response_model=AgentResponse)
def execute_agent(
    request: AgentRequest,
    x_internal_agent_token: str | None = Header(default=None, alias="X-Internal-Agent-Token"),
) -> AgentResponse:
    _verify_internal_embed_request(request, x_internal_agent_token)
    try:
        action = request.action
        if action == "summary":
            result = summarize(request.title, request.content)
        elif action == "tags":
            result = recommend_tags(request.title, request.content)
        elif action == "blog-process":
            summary_result = summarize(request.title, request.content)
            tags_result = recommend_tags(request.title, request.content)
            summary = str(summary_result.get("summary", ""))
            tags = tags_result.get("tags", [])
            embed_result = sync_blog_incremental(
                {
                    "id": request.contentId or "unknown",
                    "title": request.title or "",
                    "content": request.content or "",
                    "summary": summary,
                    "tags": tags,
                },
                metadata={
                    "authorId": request.extra.get("userId"),
                    "visibility": request.extra.get("visibility", "PUBLIC"),
                    "status": request.extra.get("status", "PUBLISHED"),
                },
            )
            result = {
                "summary": summary,
                "tags": tags,
                "embed_success": bool(embed_result.get("success", True)),
                "embed": embed_result,
            }
        elif action == "embed":
            result = sync_blog_incremental(
                {
                    "id": request.contentId or "unknown",
                    "title": request.title or "",
                    "content": request.content or "",
                    "summary": str(request.extra.get("summary", "")),
                    "tags": request.extra.get("tags", ""),
                },
                metadata={
                    "authorId": request.extra.get("userId"),
                    "visibility": request.extra.get("visibility", "PUBLIC"),
                    "status": request.extra.get("status", "PUBLISHED"),
                },
            )
        elif action == "audit-comment":
            result = audit_comment(request.content or "", request.extra.get("userId"))
        elif action == "audit-article":
            result = audit_content("article", request.content or "", request.extra.get("userId"))
        else:
            return AgentResponse(success=False, action=action, errorMessage=f"Unsupported action: {action}")
        return AgentResponse(success=True, action=action, result=result)
    except Exception as exc:
        return AgentResponse(success=False, action=request.action, errorMessage=str(exc))


@router.post("/rag/ask", response_model=ApiResponse)
def rag_ask(request: RagAskRequest, principal: AgentPrincipal = Depends(verify_agent_token)) -> ApiResponse:
    user_id = request.userId if principal.role.upper() == "ADMIN" and request.userId is not None else principal.user_id
    role = principal.role or request.role
    data = ask_blog_knowledge(request.question, user_id, role, _rag_visible_scopes(principal, request.visibleScopes), request.sessionId)
    return ApiResponse(data=data)


@router.post("/chat", response_model=ApiResponse)
def unified_chat(request: ChatRequest, principal: AgentPrincipal = Depends(verify_agent_token)) -> ApiResponse:
    data = run_unified_chat(request.message, request.mode, request.sessionId, principal)
    code = 403 if data.get("error") == "NO_PERMISSION" else 0
    message = "forbidden" if code == 403 else "success"
    return ApiResponse(code=code, message=message, data=data, error=data.get("error"))


@router.post("/chat/stream")
def unified_chat_stream(
    request: ChatRequest,
    principal: AgentPrincipal = Depends(verify_agent_token),
) -> StreamingResponse:
    def events():
        yield _chat_sse("tool.status", {"stage": "routing", "message": "正在选择合适的 Agent"})
        decision = route_chat(request.message, request.mode, principal)
        mode = decision["mode"]
        yield _chat_sse("tool.status", {
            "stage": "routed",
            "mode": mode,
            "streamingMode": "native",
            "routeDecision": decision,
        })

        if decision.get("needsClarification"):
            answer = decision["clarificationQuestion"]
            yield _chat_sse("message.delta", {"content": answer})
            yield _chat_sse("message.completed", {
                "mode": "chat",
                "answer": answer,
                "citations": [],
                "chart": None,
                "routeReason": decision["reason"],
                "routeConfidence": decision["confidence"],
                "routeCandidates": decision["candidates"],
                "routerVersion": decision["routerVersion"],
                "needsClarification": True,
                "suggestedModes": decision["suggestedModes"],
                "streamingMode": "none",
            })
            return

        if mode == "chat":
            memory = build_memory_context(request.sessionId, principal.user_id)
            parts: list[str] = []
            for token in llm_client.stream_complete(
                "你是 BlogsLike 的通用聊天助手。自然、准确地回答用户问题。",
                f"最近对话：\n{memory.get('summary', '')}\n\n用户：{request.message}",
            ):
                parts.append(token)
                yield _chat_sse("message.delta", {"content": token})
            answer = "".join(parts)
            saved = conversation_memory.append(request.sessionId, request.message, answer, [], principal.user_id)
            if request.sessionId and not saved:
                yield _chat_sse("warning", {"message": "会话暂未持久化"})
            yield _chat_sse("message.completed", {
                "mode": "chat", "answer": answer, "citations": [], "chart": None,
                "routeReason": decision["reason"], "routeConfidence": decision["confidence"],
                "routeCandidates": decision["candidates"],
                "routerVersion": decision["routerVersion"],
                "routePolicy": decision.get("policy"),
                "streamingMode": "fallback" if llm_client.degraded or not llm_client.enabled else "native",
                "degraded": llm_client.degraded,
                "responseMode": "degraded" if llm_client.degraded else "normal",
                "warning": (
                    f"LLM 暂不可用，已使用本地 fallback 响应：{llm_client.degraded_reason}"
                    if llm_client.degraded
                    else None
                ),
            })
            return

        if mode == "rag":
            scopes = ["PUBLIC", "PRIVATE"] if principal.role.upper() == "ADMIN" else ["PUBLIC"]
            for block in stream_blog_knowledge(
                request.message, principal.user_id, principal.role, scopes, request.sessionId
            ):
                event, payload = _parse_sse_block(block)
                if event == "token":
                    yield _chat_sse("message.delta", payload)
                elif event == "citations":
                    yield _chat_sse("citation", payload)
                elif event == "status":
                    yield _chat_sse("tool.status", payload)
                elif event == "done":
                    payload["mode"] = "rag"
                    payload["routeReason"] = decision["reason"]
                    payload["routeConfidence"] = decision["confidence"]
                    payload["routeCandidates"] = decision["candidates"]
                    payload["routerVersion"] = decision["routerVersion"]
                    payload["routePolicy"] = decision.get("policy")
                    payload["streamingMode"] = "fallback" if llm_client.degraded or not llm_client.enabled else "native"
                    payload["degraded"] = llm_client.degraded
                    payload["responseMode"] = "degraded" if llm_client.degraded else "normal"
                    if llm_client.degraded:
                        payload["warning"] = (
                            f"LLM 暂不可用，已使用本地 fallback 响应：{llm_client.degraded_reason}"
                        )
                    yield _chat_sse("message.completed", payload)
            return

        # Analytics is a structured SQL/tool workflow, not a token-generating answer.
        # Report it honestly as buffered instead of simulating token chunks.
        data = run_unified_chat(request.message, "analytics", request.sessionId, principal)
        if data.get("chart"):
            yield _chat_sse("chart", {"chart": data["chart"]})
        answer = str(data.get("answer") or "")
        yield _chat_sse("tool.status", {"stage": "completed", "streamingMode": "buffered"})
        yield _chat_sse("message.delta", {"content": answer})
        data["streamingMode"] = "buffered"
        yield _chat_sse("message.completed", data)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _chat_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _parse_sse_block(block: str) -> tuple[str, dict]:
    event = "message"
    data: dict = {}
    for line in block.splitlines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data = json.loads(line[5:].strip())
    return event, data


@router.post("/rag/ask/stream")
def rag_ask_stream(request: RagAskRequest, principal: AgentPrincipal = Depends(verify_agent_token)) -> StreamingResponse:
    user_id = request.userId if principal.role.upper() == "ADMIN" and request.userId is not None else principal.user_id
    role = principal.role or request.role
    visible_scopes = _rag_visible_scopes(principal, request.visibleScopes)
    return StreamingResponse(
        stream_blog_knowledge(request.question, user_id, role, visible_scopes, request.sessionId),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/rag/evaluate", response_model=ApiResponse)
def rag_evaluate(request: RagEvalRequest, principal: AgentPrincipal = Depends(verify_agent_token)) -> ApiResponse:
    if principal.role.upper() != "ADMIN":
        return ApiResponse(code=403, message="Only admin can run RAG evaluation", error="NO_PERMISSION")
    data = run_rag_evaluation(
        [case.model_dump() for case in request.cases],
        request.userId,
        principal.role,
        request.visibleScopes,
        request.framework,
    )
    return ApiResponse(data=data)


@router.post("/write", response_model=ApiResponse)
def write_article(request: WritingRequest) -> ApiResponse:
    data = generate_article(request.topic, request.keywords, request.style, request.userRequirement)
    return ApiResponse(data=data)


@router.post("/seo/optimize", response_model=ApiResponse)
def seo_optimize(request: SeoRequest) -> ApiResponse:
    data = optimize_seo(request.articleTitle, request.articleContent, request.tags)
    return ApiResponse(data=data)


@router.post("/audit", response_model=ApiResponse)
def audit(request: AuditRequest) -> ApiResponse:
    data = audit_content(request.contentType, request.content, request.userId)
    return ApiResponse(data=data)


@router.post("/analytics/query", response_model=ApiResponse)
def analytics_query(request: AnalyticsRequest, principal: AgentPrincipal = Depends(verify_agent_token)) -> ApiResponse:
    user_id = request.userId if principal.role.upper() == "ADMIN" and request.userId is not None else principal.user_id
    data = analyze_operation(request.question, principal.role, user_id)
    return ApiResponse(data=data)


@router.post("/workflows/article", response_model=ApiResponse)
def article_workflow(request: ArticleWorkflowRequest) -> ApiResponse:
    state = run_article_workflow(
        {
            "user_id": request.userId,
            "role": request.role,
            "topic": request.topic,
            "keywords": request.keywords,
            "style": request.style,
            "auto_publish": request.autoPublish,
        }
    )
    task_store.save(state["task_id"], dict(state))
    return ApiResponse(taskId=state["task_id"], data=dict(state), logs=state.get("logs", []), error=state.get("error"))


@router.get("/tasks/{task_id}", response_model=ApiResponse)
def get_task(task_id: str) -> ApiResponse:
    task = task_store.get(task_id)
    if not task:
        return ApiResponse(code=404, message="not found", taskId=task_id, error="Task not found")
    return ApiResponse(taskId=task_id, data=task, logs=task.get("logs", []), error=task.get("error"))
