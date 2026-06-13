"""A transparent client wrapper that captures token usage for the latency (tokens/s) measurement.

The production :class:`~aivmt.llm.openai_compat.OpenAICompatClient` discards the response's ``usage``
block and is owned by another lane, so the quant lane reads usage non-invasively: :class:`MeteredClient`
delegates every call to the wrapped client and, IFF that client exposes a ``last_usage`` attribute
(a dict or object with ``total_tokens``), accumulates the token count. When no usage is ever exposed
(the default for the stock client), :attr:`total_tokens` stays ``None`` and tokens/s is reported as
unavailable rather than fabricated.

Wall-clock latency is timed per-encounter by the runner (around the whole ``score_overall``), so this
wrapper deliberately does NOT time individual calls — it only meters tokens.
"""

from __future__ import annotations

from ..llm.base import BaseLLMClient


def _extract_total_tokens(usage: object) -> int | None:
    """Pull ``total_tokens`` from a usage dict or object, or ``None`` if unavailable."""
    if usage is None:
        return None
    if isinstance(usage, dict):
        value = usage.get("total_tokens")
    else:
        value = getattr(usage, "total_tokens", None)
    return int(value) if value is not None else None


class MeteredClient(BaseLLMClient):
    """Wrap a client, forwarding every call and accumulating token usage when the client exposes it.

    Parse/refusal/call counters live on the wrapped client; read them via :attr:`inner`.
    """

    def __init__(self, inner: BaseLLMClient) -> None:
        self.inner = inner
        self.model_id = inner.model_id
        self._total_tokens = 0
        self._seen_usage = False

    def _accumulate(self) -> None:
        total = _extract_total_tokens(getattr(self.inner, "last_usage", None))
        if total is not None:
            self._total_tokens += total
            self._seen_usage = True

    def complete_json(self, system: str, user: str, *, task: str) -> dict:
        out = self.inner.complete_json(system, user, task=task)
        self._accumulate()
        return out

    def chat_text(self, system: str, messages: list[dict]) -> str:
        out = self.inner.chat_text(system, messages)
        self._accumulate()
        return out

    @property
    def total_tokens(self) -> int | None:
        """Accumulated token count, or ``None`` if the wrapped client never exposed usage."""
        return self._total_tokens if self._seen_usage else None

    def reset(self) -> None:
        """Zero the token accumulator and the wrapped client's call/parse/refusal counters.

        Used to discard a warm-up encounter (model cold-load) so it pollutes neither the latency
        sample nor the parse/refusal rates of the measured cell.
        """
        self._total_tokens = 0
        self._seen_usage = False
        for counter in ("n_calls", "n_parse_failures", "n_refusals"):
            if hasattr(self.inner, counter):
                setattr(self.inner, counter, 0)


__all__ = ["MeteredClient"]
