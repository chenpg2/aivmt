"""Core robustness computations: paraphrase sensitivity and test-retest reliability.

All functions are pure given their inputs (the only nondeterminism is the LLM client itself, which
is why ``seed`` is threaded through and originates from ``configs/seed.yaml``). They call the
metrics package read-only for ICC and never fabricate a number when variance is degenerate — a
collapsed test-retest matrix yields an explicit ``nan`` + ``degenerate=True`` flag.
"""

from __future__ import annotations

import logging
from typing import Sequence

import numpy as np

from ..llm.base import BaseLLMClient
from ..metrics import icc
from ..pipeline import DEFAULT_WEIGHTS
from ..schemas import Case, Transcript
from ..scoring import ScorerFactory, ScorerVariant
from .paraphrase import PARAPHRASE_TEMPLATES, ParaphrasingClient
from .types import ParaphraseSensitivity, TestRetest

logger = logging.getLogger(__name__)

#: Scorers composing the overall competency score (must match the production pipeline order).
_SCORER_NAMES: tuple[str, ...] = ("checklist", "segue", "reasoning")

#: A transcript paired with its designed-quality "gold" used to anchor the paraphrase ICC.
GoldedTranscript = tuple[Transcript, float]


def score_overall(
    case: Case,
    transcript: Transcript,
    llm: BaseLLMClient,
    variant: ScorerVariant = "zero_shot",
) -> float:
    """Run all scorers for one encounter and collapse to the weighted overall score in [0, 1].

    Mirrors ``ScoringPipeline``'s overall weighting so robustness measures the SAME quantity the
    validity phase reports. ``variant`` selects the zero-/few-shot ablation arm.
    """
    scorers = [ScorerFactory(n, variant=variant) for n in _SCORER_NAMES]
    acc: dict = {}
    for s in scorers:
        acc.update(s.score(case, transcript, llm))
    history = float(acc.get("history_completion", 0.0))
    segue: dict[str, float] = acc.get("segue", {})
    reasoning = float(acc.get("reasoning", 0.0))
    segue_mean = sum(segue.values()) / len(segue) if segue else 0.0
    return (
        DEFAULT_WEIGHTS["history"] * history
        + DEFAULT_WEIGHTS["segue"] * segue_mean
        + DEFAULT_WEIGHTS["reasoning"] * reasoning
    )


def _icc_pair(a: Sequence[float], b: Sequence[float]) -> float:
    """ICC(2,1) between two equal-length score vectors; ``nan`` if either has no variance."""
    arr = np.column_stack([np.asarray(a, dtype=float), np.asarray(b, dtype=float)])
    if np.allclose(arr.std(axis=0), 0.0):
        return float("nan")
    return float(icc(arr, "icc2_1"))


def paraphrase_sensitivity(
    case: Case,
    dataset: Sequence[GoldedTranscript],
    llm: BaseLLMClient,
    variant: ScorerVariant = "zero_shot",
) -> ParaphraseSensitivity:
    """Score ``dataset`` under each system-prompt paraphrase and report the ICC-vs-gold spread.

    For every paraphrase template the scorer's system prompt is rewrapped (semantics preserved),
    all transcripts are rescored, and ICC(system_overall, gold) is computed. The spread (SD/range)
    across paraphrases quantifies how much harmless rewording perturbs the validity signal.

    Raises:
        ValueError: if fewer than two transcripts are supplied (ICC needs >=2 targets).
    """
    if len(dataset) < 2:
        raise ValueError("paraphrase_sensitivity needs >=2 transcripts (ICC requires n>=2 targets)")
    golds = [g for _, g in dataset]

    per_paraphrase: dict[str, float] = {}
    for template in PARAPHRASE_TEMPLATES:
        client = ParaphrasingClient(llm, template.transform)
        sys_scores = [score_overall(case, tr, client, variant) for tr, _ in dataset]
        per_paraphrase[template.name] = _icc_pair(sys_scores, golds)
        logger.debug("paraphrase %s -> icc=%.4f", template.name, per_paraphrase[template.name])

    values = np.asarray([v for v in per_paraphrase.values() if np.isfinite(v)], dtype=float)
    if values.size == 0:
        mean = sd = vmin = vmax = vrange = float("nan")
    else:
        mean = float(values.mean())
        sd = float(values.std(ddof=1)) if values.size >= 2 else 0.0
        vmin, vmax = float(values.min()), float(values.max())
        vrange = vmax - vmin
    return ParaphraseSensitivity(
        variant=variant,
        n_paraphrases=len(PARAPHRASE_TEMPLATES),
        n_transcripts=len(dataset),
        per_paraphrase_icc=per_paraphrase,
        icc_mean=mean,
        icc_sd=sd,
        icc_min=vmin,
        icc_max=vmax,
        icc_range=vrange,
    )


def _coefficient_of_variation(repeats: np.ndarray) -> float:
    """Mean per-encounter CV (sd/mean) across repeats; rows whose mean is ~0 are skipped."""
    means = repeats.mean(axis=1)
    sds = repeats.std(axis=1, ddof=1) if repeats.shape[1] >= 2 else np.zeros(repeats.shape[0])
    mask = np.abs(means) > 1e-9
    if not mask.any():
        return float("nan")
    return float(np.mean(sds[mask] / means[mask]))


def retest_reliability(
    case: Case,
    transcripts: Sequence[Transcript],
    client_factory,
    *,
    temperature: float,
    seeds: Sequence[int],
    variant: ScorerVariant = "zero_shot",
) -> TestRetest:
    """Measure stochasticity by re-scoring the same transcripts K=len(seeds) times.

    ``client_factory(seed, temperature)`` returns a fresh LLM client for one repeat (the seed lets
    a stochastic backend differ run-to-run). A perfectly deterministic backend (e.g. temp 0) yields
    identical repeat columns but still varying encounters, so the test-retest ICC is a legitimate
    ~1.0 (the scorer IS perfectly reliable) — that is reported, not faked away.

    The genuinely undefined case is the absence of BETWEEN-ENCOUNTER variance (every encounter
    scored identically): ICC has no signal to attribute, so we flag ``degenerate=True`` and return
    an explicit ``nan`` instead of a silent number.

    Returns a :class:`TestRetest` with the across-repeat ICC and mean per-encounter CV.

    Raises:
        ValueError: if fewer than two transcripts or fewer than two seeds are supplied.
    """
    if len(transcripts) < 2:
        raise ValueError("test_retest needs >=2 transcripts (ICC requires n>=2 targets)")
    if len(seeds) < 2:
        raise ValueError("test_retest needs >=2 seeds/repeats (K>=2)")

    columns: list[list[float]] = []
    for seed in seeds:
        client = client_factory(seed, temperature)
        columns.append([score_overall(case, tr, client, variant) for tr in transcripts])
    repeats = np.column_stack(columns)  # (n_transcripts, n_repeats)

    # Degenerate <=> no between-encounter variance (every row equal). The grand-mean spread across
    # rows is the right probe; identical repeat COLUMNS are fine (that is perfect reliability).
    row_means = repeats.mean(axis=1)
    degenerate = bool(np.allclose(row_means, row_means.mean()))
    retest = float("nan") if degenerate else float(icc(repeats, "icc2_1"))
    return TestRetest(
        variant=variant,
        temperature=temperature,
        n_repeats=len(seeds),
        n_seeds=len(seeds),
        n_transcripts=len(transcripts),
        retest_icc=retest,
        mean_cv=_coefficient_of_variation(repeats),
        degenerate=degenerate,
    )
