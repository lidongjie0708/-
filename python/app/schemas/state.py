from __future__ import annotations

from typing import Any, TypedDict


class ArticleWorkflowState(TypedDict, total=False):
    task_id: str
    user_id: int
    role: str
    topic: str
    keywords: list[str]
    style: str
    auto_publish: bool

    plan: dict[str, Any]
    retrieved_docs: list[dict[str, Any]]
    outline: list[str]
    content: str
    seo: dict[str, Any]
    audit: dict[str, Any]
    publish_result: dict[str, Any]

    status: str
    current_node: str
    error: str | None
    logs: list[dict[str, Any]]
    retry_count: int
