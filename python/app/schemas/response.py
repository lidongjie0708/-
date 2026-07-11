from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    success: bool
    action: str
    result: dict[str, Any] = Field(default_factory=dict)
    errorMessage: str | None = None


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    taskId: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    logs: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
