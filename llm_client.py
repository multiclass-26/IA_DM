"""Shim de retrocompatibilidade. Mantém assinatura legada str-returning."""

from __future__ import annotations

from ai_dm.llm.client import DEFAULT_GEMINI_BASE_URL, DEFAULT_OLLAMA_BASE_URL
from ai_dm.llm.client import chat_completion as _chat_completion_v2


def chat_completion(
    provider: str,
    model: str,
    system_prompt: str,
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 1500,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: int = 60,
    retries: int = 2,
) -> str:
    response = _chat_completion_v2(
        provider=provider,
        model=model,
        system_prompt=system_prompt,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
        retries=retries,
    )
    return response.content


__all__ = ["chat_completion", "DEFAULT_OLLAMA_BASE_URL", "DEFAULT_GEMINI_BASE_URL"]
