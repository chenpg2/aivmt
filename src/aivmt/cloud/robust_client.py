"""Reasoning-tolerant OpenAI-compatible client for cloud comparators.

The stock :class:`~aivmt.llm.openai_compat.OpenAICompatClient` sends
``response_format={"type": "json_object"}`` and parses ``message.content`` directly as JSON. That is
correct for vLLM/Ollama but breaks on the cloud endpoints used for the head-to-head:

- aggregator proxies and several reasoning models reject or ignore ``response_format``;
- reasoning models (DeepSeek-V4, MiniMax, MiMo) put chain-of-thought either in a separate
  ``reasoning_content`` field OR inline as a ``<think>...</think>`` prefix before the JSON.

This client therefore (1) does NOT send ``response_format`` (maximally compatible), (2) strips any
``<think>...</think>`` blocks, and (3) extracts the first balanced ``{...}`` object before parsing.
It still FAILS LOUD (raises :class:`LLMOutputError`, increments counters) on a genuinely unparseable
or empty response — no silent fallback. It is used ONLY for cloud comparators; the local model keeps
using the stock client so the local scoring path is unchanged.
"""

from __future__ import annotations

import json
import logging
import re

from ..llm.base import BaseLLMClient, LLMOutputError

logger = logging.getLogger(__name__)

#: Strip chain-of-thought blocks some reasoning models emit inline before the JSON answer.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _extract_json_object(text: str) -> str:
    """Return the first balanced top-level ``{...}`` substring of ``text``.

    Tolerates reasoning prefixes/suffixes and markdown ``` ```json fences without a regex that could
    mis-balance nested braces. Raises ``ValueError`` if no balanced object is present.
    """
    start = text.find("{")
    if start == -1:
        raise ValueError("no '{' in response")
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("unbalanced '{' — no complete JSON object")


class RobustCloudClient(BaseLLMClient):
    """OpenAI-compatible client that tolerates reasoning-model output, failing loud on real errors."""

    def __init__(
        self,
        model_id: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        timeout: float = 180.0,
        max_retries: int = 3,
    ) -> None:
        self.model_id = model_id
        self._base_url = base_url
        self._api_key = api_key
        self._temperature = temperature
        #: Reasoning models spend tokens on chain-of-thought before the JSON; budget generously so
        #: the answer is never truncated away (an empty-content refusal would otherwise be spurious).
        self._max_tokens = max_tokens
        #: Aggregator proxies are slow/flaky; a generous per-request timeout + SDK-level retries with
        #: backoff keep one slow encounter from crashing a 30-transcript head-to-head batch.
        self._timeout = timeout
        self._max_retries = max_retries
        self.n_calls = 0
        self.n_parse_failures = 0
        self.n_refusals = 0
        self.last_usage: object = None

    def _content(self, system: str, user: str, task: str) -> str:
        try:
            from openai import OpenAI  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover
            raise ImportError("openai required; install with: uv sync --extra serve") from exc

        self.n_calls += 1
        client = OpenAI(
            base_url=self._base_url,
            api_key=self._api_key,
            timeout=self._timeout,
            max_retries=self._max_retries,
        )
        resp = client.chat.completions.create(
            model=self.model_id,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        self.last_usage = getattr(resp, "usage", None)
        message = resp.choices[0].message
        content = message.content or ""
        if not content.strip():
            # Some reasoning models leave content empty and put everything in reasoning_content;
            # the JSON answer is unrecoverable in that case — fail loud, do not fabricate.
            reasoning = getattr(message, "reasoning_content", None)
            logger.error(
                "empty content (task=%s model=%s, reasoning_present=%s)",
                task, self.model_id, bool(reasoning),
            )
            self.n_refusals += 1
            self.n_parse_failures += 1
            raise LLMOutputError(f"empty/refusal response (task={task}, model={self.model_id})")
        return content

    def complete_json(self, system: str, user: str, *, task: str) -> dict:
        content = self._content(system, user, task)
        stripped = _THINK_RE.sub("", content)
        try:
            obj = json.loads(_extract_json_object(stripped))
        except (ValueError, json.JSONDecodeError) as exc:
            self.n_parse_failures += 1
            logger.error("JSON parse failure (task=%s): %s | head=%r", task, exc, content[:200])
            raise LLMOutputError(f"JSON parse failure (task={task}): {exc}") from exc
        if not isinstance(obj, dict):
            self.n_parse_failures += 1
            raise LLMOutputError(f"expected JSON object, got {type(obj).__name__} (task={task})")
        return obj


__all__ = ["RobustCloudClient", "_extract_json_object"]
