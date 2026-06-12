"""ASR-robustness ICC-degradation curve: how scorer validity falls as CER rises.

Given a synthetic golded transcript set (designed-quality "gold"), this corrupts every transcript at
each target CER level, rescores the corrupted transcripts with the local model, and computes
ICC(system_overall, gold) at each level. The result is an ICC-degradation curve anchored at the
clean (WER=0) operating point — the quantitative form of the no-AEC robustness story.

Reuses (read-only) ``aivmt.robustness.score_overall`` so the scored quantity is IDENTICAL to the
validity/robustness phases, and ``aivmt.metrics.icc`` for the agreement number. Degenerate variance
(every corrupted encounter scored the same) yields an explicit ``nan`` + ``degenerate=True`` flag,
never a silent number (AI4S no-silent-fallback).

WER vs CER: the metric is Character Error Rate (CER), the standard zh severity metric; the public
field is named ``target_wer`` to match the device-deployment vocabulary, and the per-level
``achieved_cer`` records what was actually reached (targets may be unreachable on short clean text).
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Sequence

import numpy as np

from ..llm.base import BaseLLMClient
from ..metrics import icc
from ..robustness import GoldedTranscript, score_overall
from ..scoring import ScorerVariant
from ..schemas import Case
from .confusion import ConfusionTable, load_confusion_table
from .noise import AsrNoiseConfig, corrupt, transcript_cer

logger = logging.getLogger(__name__)

#: Default WER/CER ladder for the degradation curve (clean -> high degradation).
DEFAULT_WER_LEVELS: tuple[float, ...] = (0.0, 0.05, 0.15, 0.30)


@dataclass(frozen=True)
class CurvePoint:
    """ICC-vs-gold at one corruption level, with the achieved CER and degeneracy flag."""

    target_wer: float
    achieved_cer: float
    icc_vs_gold: float
    n_transcripts: int
    degenerate: bool


@dataclass(frozen=True)
class AsrDegradationCurve:
    """The full ICC-degradation curve for one (model x scorer-variant)."""

    model_id: str
    variant: str
    seed: int
    metric: str  # "cer" — stated explicitly so the manuscript can't conflate WER/CER
    points: tuple[CurvePoint, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return asdict(self)

    def clean_icc(self) -> float:
        """ICC at WER==0 (the un-degraded anchor); ``nan`` if absent."""
        for p in self.points:
            if p.target_wer == 0.0:
                return p.icc_vs_gold
        return float("nan")


def _icc_vs_gold(sys_scores: Sequence[float], golds: Sequence[float]) -> tuple[float, bool]:
    """ICC(2,1) between system scores and gold; (nan, True) if EITHER column has no variance.

    A zero-variance system column means the scorer cannot discriminate the corrupted encounters at
    all (catastrophic corruption, or a constant scorer) — ICC has no signal to attribute, so we flag
    it degenerate and return an explicit nan rather than a silently fabricated number.
    """
    arr = np.column_stack([np.asarray(sys_scores, float), np.asarray(golds, float)])
    stds = arr.std(axis=0)
    if np.any(np.isclose(stds, 0.0)):
        return float("nan"), True
    return float(icc(arr, "icc2_1")), False


def compute_curve(
    case: Case,
    dataset: Sequence[GoldedTranscript],
    llm: BaseLLMClient,
    *,
    seed: int,
    wer_levels: Sequence[float] = DEFAULT_WER_LEVELS,
    variant: ScorerVariant = "zero_shot",
    table: ConfusionTable | None = None,
    scramble: bool = False,
) -> AsrDegradationCurve:
    """Score ``dataset`` corrupted at each level in ``wer_levels`` and report ICC-vs-gold per level.

    Each transcript is corrupted deterministically (the per-transcript seed mixes the run ``seed``
    with the transcript index so different transcripts get different noise, reproducibly). At each
    level all corrupted transcripts are rescored and ICC(system_overall, gold) is computed.

    Args:
        case: the standardized-patient case the transcripts belong to.
        dataset: (transcript, gold) pairs — the designed-quality synthetic ladder.
        llm: the scoring client (mock for tests, local Ollama for the real curve).
        seed: run seed (from ``configs/seed.yaml`` in callers).
        wer_levels: CER targets; must include 0.0 to anchor the clean ICC.
        variant: scorer prompting arm (zero/few-shot).
        table: optional pre-loaded confusion table (defaults to the synthetic repo table).
        scramble: negative-control switch — corrupts every char so ICC must collapse.

    Raises:
        ValueError: if fewer than two transcripts are supplied (ICC needs >=2 targets), or a level
            is outside [0, 1].
    """
    if len(dataset) < 2:
        raise ValueError("compute_curve needs >=2 transcripts (ICC requires n>=2 targets)")
    for w in wer_levels:
        if not 0.0 <= w <= 1.0:
            raise ValueError(f"wer level {w} outside [0, 1]")

    tbl = table if table is not None else load_confusion_table()
    golds = [g for _, g in dataset]

    points: list[CurvePoint] = []
    for level in wer_levels:
        achieved_total = 0.0
        sys_scores: list[float] = []
        for idx, (transcript, _gold) in enumerate(dataset):
            tx_seed = seed + idx  # distinct, reproducible noise per transcript
            cfg = AsrNoiseConfig(target_wer=level, seed=tx_seed, scramble=scramble)
            noisy = corrupt(transcript, level, tx_seed, table=tbl, config=cfg)
            achieved_total += 0.0 if (level == 0.0 and not scramble) else transcript_cer(transcript, noisy)
            sys_scores.append(score_overall(case, noisy, llm, variant))
        achieved = achieved_total / len(dataset)
        icc_val, degenerate = _icc_vs_gold(sys_scores, golds)
        logger.debug(
            "level=%.3f achieved_cer=%.3f icc=%.4f degenerate=%s",
            level, achieved, icc_val, degenerate,
        )
        points.append(
            CurvePoint(
                target_wer=float(level),
                achieved_cer=float(achieved),
                icc_vs_gold=icc_val,
                n_transcripts=len(dataset),
                degenerate=degenerate,
            )
        )

    return AsrDegradationCurve(
        model_id=getattr(llm, "model_id", "unknown"),
        variant=variant,
        seed=seed,
        metric="cer",
        points=tuple(points),
    )


__all__ = [
    "DEFAULT_WER_LEVELS",
    "CurvePoint",
    "AsrDegradationCurve",
    "compute_curve",
]
