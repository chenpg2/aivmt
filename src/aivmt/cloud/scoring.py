"""Per-encounter scoring that returns the overall score AND every SEGUE domain in one pass.

The robustness/quant lanes only need ``score_overall`` (a single float). The local-vs-cloud lane must
additionally report DOMAIN-LEVEL agreement, because the scoop literature shows the communication
subdomains are where cloud models collapse (ECOSBot: GPT-4o SEGUE-style ICC 0.31-0.44). So this
module runs the identical three production scorers ONCE per transcript and exposes both the weighted
overall (byte-identical to ``aivmt.robustness.score_overall``) and the five raw SEGUE domain scores.

Reuses the scoring/ package read-only (ScorerFactory) and ``DEFAULT_WEIGHTS`` / ``SEGUE_DOMAINS`` so
the quantity scored is the same one the validity phase reports — the cloud comparison is apples-to-apples.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..llm.base import BaseLLMClient
from ..pipeline import DEFAULT_WEIGHTS
from ..schemas import Case, Transcript
from ..scoring import ScorerFactory, ScorerVariant
from ..scoring.segue import SEGUE_DOMAINS

#: Scorers composing the overall competency score (production pipeline order — must match core.py).
_SCORER_NAMES: tuple[str, ...] = ("checklist", "segue", "reasoning")


@dataclass(frozen=True)
class DomainScores:
    """One encounter's overall score plus its five SEGUE domain scores (all in [0, 1])."""

    overall: float
    segue: dict[str, float]


def score_with_domains(
    case: Case,
    transcript: Transcript,
    llm: BaseLLMClient,
    variant: ScorerVariant = "zero_shot",
) -> DomainScores:
    """Score one encounter and return overall + per-SEGUE-domain.

    The overall computation mirrors ``aivmt.robustness.score_overall`` exactly (same weights, same
    segue-mean collapse), so the overall axis of the cloud comparison is directly comparable to the
    other lanes. The ``segue`` dict carries every domain so domain-level ICC deltas can be computed.

    Raises:
        KeyError: if the SEGUE scorer did not return all five domains (it validates upstream and
            fails loud, so this is a defensive guard, not a silent fallback).
    """
    scorers = [ScorerFactory(n, variant=variant) for n in _SCORER_NAMES]
    acc: dict = {}
    for s in scorers:
        acc.update(s.score(case, transcript, llm))

    history = float(acc.get("history_completion", 0.0))
    reasoning = float(acc.get("reasoning", 0.0))
    segue_raw: dict[str, float] = acc.get("segue", {})
    segue = {d: float(segue_raw[d]) for d in SEGUE_DOMAINS}  # KeyError if a domain is missing
    segue_mean = sum(segue.values()) / len(segue)

    overall = (
        DEFAULT_WEIGHTS["history"] * history
        + DEFAULT_WEIGHTS["segue"] * segue_mean
        + DEFAULT_WEIGHTS["reasoning"] * reasoning
    )
    return DomainScores(overall=overall, segue=segue)


__all__ = ["DomainScores", "score_with_domains", "SEGUE_DOMAINS"]
