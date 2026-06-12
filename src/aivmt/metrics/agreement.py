"""Categorical / ordinal agreement metrics and pass-fail decision consistency.

- ``quadratic_weighted_kappa``: ordinal agreement (e.g. anchored SEGUE domains, checklist items).
- ``cohen_kappa``: unweighted chance-corrected agreement for nominal categories.
- ``percent_agreement``: raw exact-match fraction.
- ``decision_consistency``: pass/fail agreement at a configurable cut-score (raw % + kappa).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike

__all__ = [
    "quadratic_weighted_kappa",
    "cohen_kappa",
    "percent_agreement",
    "decision_consistency",
    "DecisionConsistency",
    "DEFAULT_CUT_SCORE",
]

#: Default pass/fail cut on the [0, 1] overall competency scale. Config constant — callers may
#: override; it is never hardcoded at the call sites.
DEFAULT_CUT_SCORE: float = 0.6


def quadratic_weighted_kappa(
    a: Sequence[int],
    b: Sequence[int],
    min_rating: int | None = None,
    max_rating: int | None = None,
) -> float:
    """Quadratic weighted kappa for two ordinal raters."""
    ra = np.asarray(a, dtype=int)
    rb = np.asarray(b, dtype=int)
    if ra.shape != rb.shape or ra.size == 0:
        raise ValueError("a and b must be same-length non-empty sequences")
    lo = min_rating if min_rating is not None else int(min(ra.min(), rb.min()))
    hi = max_rating if max_rating is not None else int(max(ra.max(), rb.max()))
    cats = list(range(lo, hi + 1))
    size = len(cats)
    if size == 1:
        return 1.0  # only one possible rating -> perfect by convention
    index = {r: i for i, r in enumerate(cats)}

    observed = np.zeros((size, size), dtype=float)
    for x, y in zip(ra, rb):
        observed[index[int(x)], index[int(y)]] += 1
    weights = np.fromfunction(
        lambda i, j: ((i - j) ** 2) / ((size - 1) ** 2), (size, size), dtype=float
    )
    hist_a = observed.sum(axis=1)
    hist_b = observed.sum(axis=0)
    total = observed.sum()
    expected = np.outer(hist_a, hist_b) / total
    num = (weights * observed).sum()
    den = (weights * expected).sum()
    return float(1.0 - num / den) if den != 0 else float("nan")


def cohen_kappa(a: ArrayLike, b: ArrayLike) -> float:
    """Unweighted Cohen's kappa for two raters over shared nominal categories.

    Returns ``nan`` when expected agreement is 1 (all ratings in a single category), where kappa
    is mathematically undefined — surfaced rather than silently coerced to 0 or 1.
    """
    ra = np.asarray(a, dtype=int)
    rb = np.asarray(b, dtype=int)
    if ra.shape != rb.shape or ra.size == 0:
        raise ValueError("a and b must be same-length non-empty sequences")
    cats = sorted(set(ra.tolist()) | set(rb.tolist()))
    index = {c: i for i, c in enumerate(cats)}
    size = len(cats)
    observed = np.zeros((size, size), dtype=float)
    for x, y in zip(ra, rb):
        observed[index[int(x)], index[int(y)]] += 1
    total = observed.sum()
    po = np.trace(observed) / total
    pe = (observed.sum(axis=1) * observed.sum(axis=0)).sum() / (total**2)
    if pe == 1.0:
        return float("nan")
    return float((po - pe) / (1.0 - pe))


def percent_agreement(a: ArrayLike, b: ArrayLike) -> float:
    """Fraction of exactly-matching paired ratings."""
    ra = np.asarray(a)
    rb = np.asarray(b)
    if ra.shape != rb.shape or ra.size == 0:
        raise ValueError("a and b must be same-length non-empty sequences")
    return float((ra == rb).mean())


@dataclass(frozen=True)
class DecisionConsistency:
    """Pass/fail decision agreement between two scorers at a cut-score."""

    cut_score: float
    n: int
    raw_agreement: float
    cohen_kappa: float
    n_both_pass: int
    n_both_fail: int
    n_disagree: int

    def to_dict(self) -> dict:
        return {
            "cut_score": self.cut_score,
            "n": self.n,
            "raw_agreement": self.raw_agreement,
            "cohen_kappa": self.cohen_kappa,
            "n_both_pass": self.n_both_pass,
            "n_both_fail": self.n_both_fail,
            "n_disagree": self.n_disagree,
        }


def decision_consistency(
    a: ArrayLike,
    b: ArrayLike,
    cut_score: float = DEFAULT_CUT_SCORE,
) -> DecisionConsistency:
    """Raw agreement % and Cohen's kappa for the pass/fail decision at ``cut_score``.

    A score >= ``cut_score`` is a pass. Both scorers are dichotomized at the same cut.
    """
    ra = np.asarray(a, dtype=float)
    rb = np.asarray(b, dtype=float)
    if ra.shape != rb.shape or ra.ndim != 1 or ra.size == 0:
        raise ValueError("a and b must be equal-length 1-D non-empty sequences")
    a_pass = ra >= cut_score
    b_pass = rb >= cut_score
    raw = float((a_pass == b_pass).mean())
    kappa = cohen_kappa(a_pass.astype(int), b_pass.astype(int))
    both_pass = int(np.sum(a_pass & b_pass))
    both_fail = int(np.sum(~a_pass & ~b_pass))
    disagree = int(np.sum(a_pass != b_pass))
    return DecisionConsistency(
        cut_score=float(cut_score),
        n=int(ra.size),
        raw_agreement=raw,
        cohen_kappa=kappa,
        n_both_pass=both_pass,
        n_both_fail=both_fail,
        n_disagree=disagree,
    )
