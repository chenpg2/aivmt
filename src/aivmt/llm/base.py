"""Abstract LLM client interface (OpenAI-compatible, JSON-returning)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMOutputError(RuntimeError):
    """Model output could not be parsed/validated. Fail-loud — never silently default to zeros."""


class BaseLLMClient(ABC):
    """A client that returns a parsed JSON object for a scoring sub-task."""

    model_id: str
    #: Observability counters (fail-loud). Implementations update these per call.
    n_calls: int = 0
    n_parse_failures: int = 0
    n_refusals: int = 0

    @abstractmethod
    def complete_json(self, system: str, user: str, *, task: str) -> dict:
        """Return a JSON object for ``task`` given ``system``/``user`` prompts.

        Args:
            system: System prompt establishing the rater role.
            user: User prompt containing the case + transcript + instructions.
            task: Sub-task hint (e.g. ``"checklist"``, ``"segue"``, ``"reasoning"``,
                ``"feedback"``) used by mock/routing logic.

        Returns:
            Parsed JSON object.
        """
        raise NotImplementedError

    def chat_text(self, system: str, messages: list[dict]) -> str:
        """Multi-turn chat returning plain text (used by the standardized-patient agent).

        Override in clients that support it. ``messages`` is a list of
        ``{"role": "user"|"assistant", "content": str}`` in chronological order.
        """
        raise NotImplementedError("this client does not support chat_text")
