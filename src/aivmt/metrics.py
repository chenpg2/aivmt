"""Agreement metrics for the H1 validity analysis.

Primary: two-way random-effects, absolute-agreement ICC (Shrout & Fleiss Case 2),
single (icc2_1) and average (icc2_k) forms — used for system-vs-faculty agreement.
Also: quadratic weighted kappa (ordinal checklist items) and percent agreement.
"""

from __future__ import annotations

from typing import Literal, Sequence

import numpy as np

IccKind = Literal["icc2_1", "icc2_k"]


def icc(data: Sequence[Sequence[float]], kind: IccKind = "icc2_1") -> float:
    """Two-way random-effects, absolute-agreement ICC.

    Args:
        data: matrix of shape (n_targets, k_raters).
        kind: ``"icc2_1"`` single rater, ``"icc2_k"`` average of k raters.

    Returns:
        The ICC, or ``nan`` if the denominator is zero (degenerate variance).
    """
    m = np.asarray(data, dtype=float)
    if m.ndim != 2 or m.shape[0] < 2 or m.shape[1] < 2:
        raise ValueError("data must be (n_targets, k_raters) with n>=2 and k>=2")
    n, k = m.shape
    grand = m.mean()
    ss_total = ((m - grand) ** 2).sum()
    ss_rows = k * ((m.mean(axis=1) - grand) ** 2).sum()      # between targets
    ss_cols = n * ((m.mean(axis=0) - grand) ** 2).sum()      # between raters
    ss_err = ss_total - ss_rows - ss_cols
    ms_rows = ss_rows / (n - 1)
    ms_cols = ss_cols / (k - 1)
    ms_err = ss_err / ((n - 1) * (k - 1))

    if kind == "icc2_1":
        denom = ms_rows + (k - 1) * ms_err + (k / n) * (ms_cols - ms_err)
    elif kind == "icc2_k":
        denom = ms_rows + (ms_cols - ms_err) / n
    else:
        raise ValueError(f"unknown ICC kind: {kind}")
    return float((ms_rows - ms_err) / denom) if denom != 0 else float("nan")


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


def percent_agreement(a: Sequence[float], b: Sequence[float]) -> float:
    """Fraction of exactly-matching paired ratings."""
    ra = np.asarray(a)
    rb = np.asarray(b)
    if ra.shape != rb.shape or ra.size == 0:
        raise ValueError("a and b must be same-length non-empty sequences")
    return float((ra == rb).mean())
