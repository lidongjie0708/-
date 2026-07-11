from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from fastapi import Header, HTTPException

from app.config import settings


@dataclass(frozen=True)
class AgentPrincipal:
    username: str
    user_id: int | None
    role: str
    scope: str


def verify_agent_token(authorization: str | None = Header(default=None)) -> AgentPrincipal:
    if not settings.ai_token_required:
        return AgentPrincipal(username="anonymous", user_id=None, role="USER", scope="agent:stream")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing AI agent token")
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_ai_token(token)
    return AgentPrincipal(
        username=str(payload.get("sub") or ""),
        user_id=_to_int(payload.get("userId")),
        role=str(payload.get("role") or "USER"),
        scope=str(payload.get("scope") or ""),
    )


def decode_ai_token(token: str) -> dict[str, Any]:
    if not settings.jwt_secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET is not configured for Python Agent")
    try:
        import jwt

        secret = base64.b64decode(settings.jwt_secret)
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid AI agent token: {exc}") from exc
    if payload.get("typ") != "AI_AGENT":
        raise HTTPException(status_code=403, detail="Token type is not AI_AGENT")
    if payload.get("scope") != "agent:stream":
        raise HTTPException(status_code=403, detail="Token scope is not agent:stream")
    return payload


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
