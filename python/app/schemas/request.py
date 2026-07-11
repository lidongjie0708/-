from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    action: str
    content: str | None = None
    title: str | None = None
    contentId: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class RagAskRequest(BaseModel):
    question: str
    sessionId: str | None = None
    userId: int | None = None
    role: str = "USER"
    visibleScopes: list[str] = Field(default_factory=lambda: ["PUBLIC"])


class RagEvalCase(BaseModel):
    question: str
    groundTruth: str | None = None
    reference: str | None = None
    contexts: list[str] = Field(default_factory=list)
    expectedKeywords: list[str] = Field(default_factory=list)


class RagEvalRequest(BaseModel):
    cases: list[RagEvalCase]
    userId: int | None = None
    role: str = "ADMIN"
    visibleScopes: list[str] = Field(default_factory=lambda: ["PUBLIC", "PRIVATE"])
    framework: Literal["ragas", "lite"] = "ragas"


class WritingRequest(BaseModel):
    topic: str
    keywords: list[str] = Field(default_factory=list)
    style: str = "technical_blog"
    userRequirement: str | None = None


class SeoRequest(BaseModel):
    articleTitle: str
    articleContent: str
    tags: list[str] = Field(default_factory=list)


class AuditRequest(BaseModel):
    contentType: Literal["article", "comment"] = "article"
    content: str
    userId: int | None = None


class AnalyticsRequest(BaseModel):
    question: str
    userId: int | None = None
    role: str = "ADMIN"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    mode: Literal["auto", "chat", "rag", "analytics"] = "auto"
    sessionId: str | None = Field(default=None, max_length=120)


class ArticleWorkflowRequest(BaseModel):
    userId: int
    role: str = "USER"
    topic: str
    keywords: list[str] = Field(default_factory=list)
    style: str = "technical_blog"
    autoPublish: bool = False
