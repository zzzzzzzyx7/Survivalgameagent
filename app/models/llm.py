"""Unified LLM factory."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from app.config import settings


@dataclass(frozen=True)
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model_name: str
    usage: LLMUsage = LLMUsage()
    latency_ms: float = 0.0


class ChatModel(Protocol):
    model_name: str

    def complete(self, prompt: str) -> str:
        """Return a text completion for a prompt."""

    def complete_with_metrics(self, prompt: str) -> LLMResponse:
        """Return a text completion with token and latency metadata."""


@dataclass
class OpenAIChatModel:
    model_name: str
    base_url: str = settings.llm_base_url
    api_key_env: str = settings.llm_api_key_env
    timeout_seconds: float = settings.llm_timeout_seconds
    max_retries: int = settings.llm_max_retries
    retry_backoff_seconds: float = settings.llm_retry_backoff_seconds

    def complete(self, prompt: str) -> str:
        return self.complete_with_metrics(prompt).text

    def complete_with_metrics(self, prompt: str) -> LLMResponse:
        import time

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the openai package to use OpenAIChatModel.") from exc

        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise RuntimeError(f"Set {self.api_key_env} to use {self.model_name}.")

        client = OpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            max_retries=0,
        )
        start = time.perf_counter()
        response = None
        attempts = max(1, int(self.max_retries) + 1)
        for attempt in range(1, attempts + 1):
            try:
                response = client.responses.create(model=self.model_name, input=prompt)
                break
            except Exception as exc:
                if attempt >= attempts or not _is_retryable_llm_error(exc):
                    elapsed = time.perf_counter() - start
                    raise RuntimeError(
                        _format_llm_error_message(
                            exc,
                            attempts=attempt,
                            elapsed_seconds=elapsed,
                            timeout_seconds=self.timeout_seconds,
                        )
                    ) from exc
                time.sleep(float(self.retry_backoff_seconds) * attempt)
        latency_ms = (time.perf_counter() - start) * 1000
        usage = _parse_usage(getattr(response, "usage", None))
        return LLMResponse(
            text=str(response.output_text),
            model_name=self.model_name,
            usage=usage,
            latency_ms=latency_ms,
        )


def get_llm(model_name: str | None = None) -> ChatModel:
    return OpenAIChatModel(model_name=model_name or settings.model_name)


def _parse_usage(raw_usage: object) -> LLMUsage:
    if raw_usage is None:
        return LLMUsage()
    return LLMUsage(
        input_tokens=int(getattr(raw_usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(raw_usage, "output_tokens", 0) or 0),
        total_tokens=int(getattr(raw_usage, "total_tokens", 0) or 0),
    )


def _is_retryable_llm_error(exc: Exception) -> bool:
    return type(exc).__name__ in {
        "APITimeoutError",
        "APIConnectionError",
        "RateLimitError",
        "InternalServerError",
    }


def _format_llm_error_message(
    exc: Exception,
    *,
    attempts: int,
    elapsed_seconds: float,
    timeout_seconds: float,
) -> str:
    if type(exc).__name__ == "APITimeoutError":
        return (
            "LLM request timed out. "
            f"Tried {attempts} request(s), timeout={timeout_seconds:g}s, "
            f"elapsed={elapsed_seconds:.1f}s. "
            "Increase SURVIVAL_AGENT_LLM_TIMEOUT_SECONDS, use a faster model, "
            "or retry when the API is less busy."
        )
    return (
        f"LLM request failed after {attempts} request(s): "
        f"{type(exc).__name__}: {exc}"
    )
