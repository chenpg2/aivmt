"""OpenAI-compatible client for self-hosted local models (Ollama / vLLM / llama.cpp).

Fail-loud: a parse failure or empty/refusal response RAISES LLMOutputError (and is counted)
instead of silently degrading to ``{}`` -> all-zero scores. The ``openai`` package is imported
lazily (install the ``serve`` extra to use this client).
"""

from __future__ import annotations

import json

from . import register_llm
from .base import BaseLLMClient, LLMOutputError
from ..utils import get_logger

logger = get_logger(__name__)


@register_llm("openai_compat")
class OpenAICompatClient(BaseLLMClient):
    """Calls a chat-completions endpoint and parses a JSON object response."""

    def __init__(
        self,
        model_id: str,
        base_url: str = "http://localhost:8000/v1",
        api_key: str = "EMPTY",
        temperature: float = 0.0,
        **_: object,
    ) -> None:
        self.model_id = model_id
        self._base_url = base_url
        self._api_key = api_key
        self._temperature = temperature
        self.n_calls = 0
        self.n_parse_failures = 0
        self.n_refusals = 0

    def complete_json(self, system: str, user: str, *, task: str) -> dict:
        try:
            from openai import OpenAI  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover
            raise ImportError("openai required; install with: uv sync --extra serve") from exc

        self.n_calls += 1
        client = OpenAI(base_url=self._base_url, api_key=self._api_key)
        resp = client.chat.completions.create(
            model=self.model_id,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=self._temperature,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        if not content or not content.strip():
            self.n_refusals += 1
            self.n_parse_failures += 1
            logger.error("empty/refusal response (task=%s model=%s)", task, self.model_id)
            raise LLMOutputError(f"empty/refusal response (task={task})")
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            self.n_parse_failures += 1
            logger.error("JSON parse failure (task=%s): %s | head=%r", task, exc, content[:200])
            raise LLMOutputError(f"JSON parse failure (task={task}): {exc}") from exc

    def chat_text(self, system: str, messages: list[dict]) -> str:
        try:
            from openai import OpenAI  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover
            raise ImportError("openai required; install with: uv sync --extra serve") from exc

        self.n_calls += 1
        client = OpenAI(base_url=self._base_url, api_key=self._api_key)
        resp = client.chat.completions.create(
            model=self.model_id,
            messages=[{"role": "system", "content": system}, *messages],  # type: ignore[arg-type]
            temperature=self._temperature,
        )
        content = resp.choices[0].message.content
        if not content or not content.strip():
            self.n_refusals += 1
            raise LLMOutputError("empty patient reply")
        return content.strip()
