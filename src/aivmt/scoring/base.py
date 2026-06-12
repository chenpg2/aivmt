"""Abstract competency scorer + shared helpers.

Each scorer inspects a (Case, Transcript) using an LLM client and returns a partial result
dict that the pipeline merges. Keys: ``history_completion``, ``item_scores``, ``segue``, ``reasoning``.
Scorers VALIDATE model output and fail loud (raise LLMOutputError) — they never default to 0.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..llm.base import BaseLLMClient, LLMOutputError
from ..schemas import Case, Transcript


def render_transcript(transcript: Transcript) -> str:
    """Render a transcript as plain text for prompting."""
    label = {"student": "Student", "patient": "Patient"}
    return "\n".join(f"{label[t.speaker]}: {t.text}" for t in transcript.turns)


def require(condition: bool, message: str) -> None:
    """Fail loud on malformed/invalid model output (no silent zero-fallback)."""
    if not condition:
        raise LLMOutputError(message)


class BaseScorer(ABC):
    """Base class for all competency scorers."""

    name: str = "base"

    @abstractmethod
    def score(self, case: Case, transcript: Transcript, llm: BaseLLMClient) -> dict:
        """Return a partial score dict for ``case``/``transcript``."""
        raise NotImplementedError
