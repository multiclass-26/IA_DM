"""Cliente LLM compatível com OpenAI SDK.

Suporta Ollama e Gemini (via endpoint OpenAI-compatible).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

log = logging.getLogger(__name__)

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


@dataclass(frozen=True)
class LLMResponse:
    content: str
    elapsed_s: float
    prompt_chars: int
    response_chars: int
    provider: str
    model: str
    attempts: int


def _provider_config(provider: str, base_url: str | None, api_key: str | None) -> tuple[str, str]:
    provider_norm = (provider or "ollama").strip().lower()
    if provider_norm == "gemini":
        url = (base_url or DEFAULT_GEMINI_BASE_URL).strip()
        key = (api_key or "").strip()
        if not key:
            raise ValueError("API key do Gemini nao configurada.")
        return url, key
    if provider_norm == "ollama":
        return (base_url or DEFAULT_OLLAMA_BASE_URL).strip(), "ollama"
    raise ValueError(f"Provedor de IA nao suportado: {provider}")


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
    response_format: dict[str, Any] | None = None,
) -> LLMResponse:
    """Chama a LLM e retorna texto + métricas. Lança RuntimeError em falha."""
    url, key = _provider_config(provider, base_url, api_key)

    full_messages = [{"role": "system", "content": system_prompt}, *messages]
    prompt_chars = sum(len(m.get("content", "")) for m in full_messages)

    last_exc: Exception | None = None
    started = time.monotonic()
    for attempt in range(retries + 1):
        try:
            client = OpenAI(base_url=url, api_key=key, timeout=timeout)
            kwargs: dict[str, Any] = dict(
                model=model,
                messages=full_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if response_format:
                kwargs["response_format"] = response_format

            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("Resposta vazia da IA.")
            elapsed = time.monotonic() - started
            log.info(
                "LLM ok provider=%s model=%s attempts=%d elapsed=%.2fs chars=%d",
                provider, model, attempt + 1, elapsed, len(content),
            )
            return LLMResponse(
                content=content,
                elapsed_s=elapsed,
                prompt_chars=prompt_chars,
                response_chars=len(content),
                provider=provider,
                model=model,
                attempts=attempt + 1,
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            log.warning("LLM tentativa %d falhou: %s", attempt + 1, exc)
            if attempt < retries:
                time.sleep(0.7 * (attempt + 1))

    elapsed = time.monotonic() - started
    raise RuntimeError(f"Falha ao chamar o provedor de IA apos {retries+1} tentativas em {elapsed:.1f}s: {last_exc}")
