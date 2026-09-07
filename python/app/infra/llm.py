from __future__ import annotations

import json
from typing import Any

from app.config import settings


class LlmClient:
    """Small adapter around the configured DeepSeek-compatible chat model."""

    def __init__(self) -> None:
        self._model = None
        self._last_degraded_reason: str | None = None
        if settings.llm_api_key:
            try:
                from langchain_openai import ChatOpenAI

                self._model = ChatOpenAI(
                    model=settings.llm_model,
                    api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url or None,
                    temperature=settings.temperature,
                    request_timeout=settings.llm_timeout,
                )
            except Exception:
                self._model = None

    @property
    def enabled(self) -> bool:
        return self._model is not None

    @property
    def degraded(self) -> bool:
        return self._last_degraded_reason is not None

    @property
    def degraded_reason(self) -> str | None:
        return self._last_degraded_reason

    def complete(self, system: str, user: str) -> str:
        if not self._model:
            self._last_degraded_reason = "model-not-configured"
            return self._fallback_text(user)
        self._last_degraded_reason = None
        try:
            response = self._model.invoke(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ]
            )
            return getattr(response, "content", str(response))
        except Exception as exc:
            self._last_degraded_reason = f"{type(exc).__name__}: {exc}"
            return self._fallback_text()

    def stream_complete(self, system: str, user: str):
        if not self._model:
            text = self._fallback_text()
            for index in range(0, len(text), 24):
                yield text[index : index + 24]
            return
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            for chunk in self._model.stream(messages):
                content = getattr(chunk, "content", "")
                if content:
                    yield str(content)
        except Exception:
            yield self.complete(system, user)

    def complete_json(self, system: str, user: str, fallback: dict[str, Any]) -> dict[str, Any]:
        if not self._model:
            self._last_degraded_reason = "model-not-configured"
            return fallback
        text = self.complete(system, user)
        if self.degraded:
            return fallback
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end >= start:
                return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
        return fallback

    def _fallback_text(self) -> str:
        reason = self._last_degraded_reason or "unknown"
        return (
            "（系统降级）LLM 服务暂不可用，无法生成回答。"
            f"错误原因：{reason}。请稍后重试。"
        )


llm_client = LlmClient()


def llm_factory(
    model: str | None = None,
    client: Any | None = None,
    max_tokens: int | None = None,
    timeout: int | None = None,
) -> Any:
    """Create a LangChain chat model for evaluator/tool-calling paths.

    Uses the configured generation provider (settings.llm_*) so the tool-calling
    agent loop and evaluators follow the same provider as chat/RAG responses.
    """
    try:
        from langchain_openai import ChatOpenAI
    except Exception:
        return None

    if not settings.llm_api_key:
        return None
    max_tokens = max_tokens or settings.evaluator_max_tokens
    return ChatOpenAI(
        model=model or settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url or None,
        temperature=settings.temperature,
        max_tokens=min(int(max_tokens), 32768),
        request_timeout=timeout if timeout else settings.llm_timeout,
    )


def embedding_factory(model: str | None = None, client: Any | None = None) -> Any:
    """Create a LangChain embeddings object backed by OpenAI-compatible DashScope."""
    try:
        from langchain_openai import OpenAIEmbeddings
    except Exception:
        return None

    if not settings.dashscope_api_key:
        return None
    return OpenAIEmbeddings(
        model=model or settings.evaluator_embedding_model,
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )


def build_openai_compatible_clients() -> dict[str, Any]:
    """Return OpenAI-compatible SDK clients pointed at configured provider endpoints."""
    try:
        from openai import AsyncOpenAI
    except Exception:
        return {"llm_client": None, "embedding_client": None}
    return {
        "llm_client": AsyncOpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url or None)
        if settings.deepseek_api_key
        else None,
        "embedding_client": AsyncOpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url or None,
        )
        if settings.dashscope_api_key
        else None,
    }
