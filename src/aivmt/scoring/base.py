"""Abstract competency scorer + shared helpers.

Each scorer inspects a (Case, Transcript) using an LLM client and returns a partial result
dict that the pipeline merges. Keys: ``history_completion``, ``item_scores``, ``segue``, ``reasoning``.
Scorers VALIDATE model output and fail loud (raise LLMOutputError) — they never default to 0.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, Sequence, Tuple

from ..llm.base import BaseLLMClient, LLMOutputError
from ..schemas import Case, Transcript

#: Scorer prompting variant. ``"zero_shot"`` (default) preserves the original behavior exactly;
#: ``"few_shot"`` prepends SYNTHETIC, explicitly-labeled exemplar pairs to the user prompt.
ScorerVariant = Literal["zero_shot", "few_shot"]

#: A single synthetic exemplar: (short transcript excerpt, expected-rubric-JSON string).
Exemplar = Tuple[str, str]


def render_transcript(transcript: Transcript) -> str:
    """Render a transcript as plain text for prompting."""
    label = {"student": "Student", "patient": "Patient"}
    return "\n".join(f"{label[t.speaker]}: {t.text}" for t in transcript.turns)


def require(condition: bool, message: str) -> None:
    """Fail loud on malformed/invalid model output (no silent zero-fallback)."""
    if not condition:
        raise LLMOutputError(message)


def build_exemplar_block(exemplars: Sequence[Exemplar]) -> str:
    """Render a deterministic few-shot exemplar block for prompt prepending.

    The block is explicitly labeled SYNTHETIC so neither the model nor a human reader mistakes
    these illustrative pairs for real patient data. Rendering is order-preserving and pure, so the
    same exemplars always yield byte-identical text (determinism is required for reproducibility).

    Args:
        exemplars: ordered (transcript-excerpt, expected-rubric-JSON) pairs.

    Returns:
        A formatted, trailing-newline-terminated block, or ``""`` if no exemplars are supplied.
    """
    if not exemplars:
        return ""
    parts = [
        "WORKED EXAMPLES (SYNTHETIC, illustrative only — not real patient data):",
    ]
    for i, (excerpt, expected_json) in enumerate(exemplars, start=1):
        parts.append(f"\nExample {i} transcript excerpt:\n{excerpt}\nExpected JSON:\n{expected_json}")
    parts.append("\nNow score the ACTUAL transcript below using the SAME JSON shape.\n\n")
    return "\n".join(parts)


class BaseScorer(ABC):
    """Base class for all competency scorers.

    Subclasses accept an optional ``variant`` to toggle the few-shot ablation arm. The default
    ``"zero_shot"`` reproduces the original prompts byte-for-byte; ``"few_shot"`` prepends the
    scorer's SYNTHETIC exemplars to the user prompt without altering the rubric or system prompt.
    """

    name: str = "base"

    def __init__(self, variant: ScorerVariant = "zero_shot", **_: object) -> None:
        if variant not in ("zero_shot", "few_shot"):
            raise ValueError(f"unknown scorer variant {variant!r}; use 'zero_shot' or 'few_shot'")
        self.variant = variant

    @abstractmethod
    def score(self, case: Case, transcript: Transcript, llm: BaseLLMClient) -> dict:
        """Return a partial score dict for ``case``/``transcript``."""
        raise NotImplementedError
