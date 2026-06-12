"""Intraclass correlation (ICC) for the SQ1 validity analysis.

Two-way random-effects, absolute-agreement ICC (Shrout & Fleiss 1979 Case 2; McGraw & Wong
1996 ICC(A,1)/(A,k)) with F-based 95% confidence intervals, plus a seeded nonparametric
bootstrap CI as an independent cross-check path. The point estimate is validated against the
Shrout & Fleiss (1979) worked example; the CI primitives against published F-table values.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike

from ._special import f_ppf

__all__ = [
    "IccKind",
    "IccEstimate",
    "icc",
    "icc_with_ci",
    "bootstrap_icc_ci",
    "DEFAULT_CI_ALPHA",
    "DEFAULT_BOOTSTRAP_RESAMPLES",
]

IccKind = Literal["icc2_1", "icc2_k"]

#: Two-sided alpha for confidence intervals (95% CI). Config constant, not hardcoded inline.
DEFAULT_CI_ALPHA: float = 0.05
#: Resamples for the bootstrap cross-check path.
DEFAULT_BOOTSTRAP_RESAMPLES: int = 2000


@dataclass(frozen=True)
class _TwoWayAnova:
    """Mean squares of the two-way (targets x raters) ANOVA decomposition."""

    n: int  # number of targets (rows)
    k: int  # number of raters (columns)
    ms_rows: float  # MSR — between targets
    ms_cols: float  # MSC — between raters
    ms_err: float  # MSE — residual


@dataclass(frozen=True)
class IccEstimate:
    """An ICC point estimate with its parametric confidence interval."""

    kind: IccKind
    n: int
    k: int
    point: float
    ci_lower: float
    ci_upper: float
    alpha: float
    method: str

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "n": self.n,
            "k": self.k,
            "point": self.point,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "alpha": self.alpha,
            "method": self.method,
        }


def _as_matrix(data: ArrayLike) -> np.ndarray:
    m = np.asarray(data, dtype=float)
    if m.ndim != 2 or m.shape[0] < 2 or m.shape[1] < 2:
        raise ValueError("data must be (n_targets, k_raters) with n>=2 and k>=2")
    if not np.isfinite(m).all():
        raise ValueError("ICC input contains non-finite values; resolve missing data before ICC")
    return m


def _two_way_anova(m: np.ndarray) -> _TwoWayAnova:
    n, k = m.shape
    grand = m.mean()
    ss_total = ((m - grand) ** 2).sum()
    ss_rows = k * ((m.mean(axis=1) - grand) ** 2).sum()  # between targets
    ss_cols = n * ((m.mean(axis=0) - grand) ** 2).sum()  # between raters
    ss_err = ss_total - ss_rows - ss_cols
    return _TwoWayAnova(
        n=n,
        k=k,
        ms_rows=ss_rows / (n - 1),
        ms_cols=ss_cols / (k - 1),
        ms_err=ss_err / ((n - 1) * (k - 1)),
    )


def _icc_from_anova(a: _TwoWayAnova, kind: IccKind) -> float:
    n, k = a.n, a.k
    if kind == "icc2_1":
        denom = a.ms_rows + (k - 1) * a.ms_err + (k / n) * (a.ms_cols - a.ms_err)
    elif kind == "icc2_k":
        denom = a.ms_rows + (a.ms_cols - a.ms_err) / n
    else:
        raise ValueError(f"unknown ICC kind: {kind}")
    return float((a.ms_rows - a.ms_err) / denom) if denom != 0 else float("nan")


def icc(data: ArrayLike, kind: IccKind = "icc2_1") -> float:
    """Two-way random-effects, absolute-agreement ICC.

    Args:
        data: matrix of shape (n_targets, k_raters).
        kind: ``"icc2_1"`` single rater, ``"icc2_k"`` average of k raters.

    Returns:
        The ICC, or ``nan`` if the denominator is zero (degenerate variance).
    """
    return _icc_from_anova(_two_way_anova(_as_matrix(data)), kind)


def _icc2_single_ci(a: _TwoWayAnova, point: float, alpha: float) -> tuple[float, float]:
    """McGraw & Wong (1996) F-based CI for ICC(A,1) (absolute agreement, single measure)."""
    n, k = a.n, a.k
    msr, msc, mse = a.ms_rows, a.ms_cols, a.ms_err
    if not np.isfinite(point) or msc <= 0 or mse <= 0:
        return float("nan"), float("nan")
    fj = msc / mse
    a_term = n * (1.0 + (k - 1) * point) - k * point
    v_num = (k - 1) * (n - 1) * (k * point * fj + a_term) ** 2
    v_den = (n - 1) * k**2 * point**2 * fj**2 + a_term**2
    if v_den == 0:
        return float("nan"), float("nan")
    v = v_num / v_den
    f_lower = f_ppf(1.0 - alpha / 2.0, n - 1, v)
    f_upper = f_ppf(1.0 - alpha / 2.0, v, n - 1)
    span = k * msc + (k * n - k - n) * mse
    lower = n * (msr - f_lower * mse) / (f_lower * span + n * msr)
    upper = n * (f_upper * msr - mse) / (span + n * f_upper * msr)
    return float(lower), float(upper)


def _spearman_brown(rho: float, k: int) -> float:
    """Step-up a single-measure reliability bound to the k-measure (average) scale."""
    denom = 1.0 + (k - 1) * rho
    return float(k * rho / denom) if denom != 0 else float("nan")


def icc_with_ci(
    data: ArrayLike,
    kind: IccKind = "icc2_1",
    alpha: float = DEFAULT_CI_ALPHA,
) -> IccEstimate:
    """ICC point estimate with the McGraw & Wong (1996) F-based confidence interval.

    The average-measure (``icc2_k``) interval is obtained by the Spearman-Brown step-up of the
    single-measure interval bounds, matching the pingouin / psych reference implementations.
    """
    anova = _two_way_anova(_as_matrix(data))
    point = _icc_from_anova(anova, kind)
    lower, upper = _icc2_single_ci(anova, _icc_from_anova(anova, "icc2_1"), alpha)
    if kind == "icc2_k":
        lower = _spearman_brown(lower, anova.k)
        upper = _spearman_brown(upper, anova.k)
    return IccEstimate(
        kind=kind,
        n=anova.n,
        k=anova.k,
        point=point,
        ci_lower=lower,
        ci_upper=upper,
        alpha=alpha,
        method="mcgraw_wong_1996_f",
    )


def bootstrap_icc_ci(
    data: ArrayLike,
    seed: int,
    kind: IccKind = "icc2_1",
    n_resamples: int = DEFAULT_BOOTSTRAP_RESAMPLES,
    alpha: float = DEFAULT_CI_ALPHA,
) -> IccEstimate:
    """Seeded nonparametric bootstrap CI for the ICC (independent cross-check of the F-based CI).

    Targets (rows / encounters) are the resampling unit. ``seed`` MUST originate from
    ``configs/seed.yaml`` (never hardcoded) so the interval is reproducible.
    """
    m = _as_matrix(data)
    n = m.shape[0]
    rng = np.random.default_rng(seed)
    point = _icc_from_anova(_two_way_anova(m), kind)
    estimates: list[float] = []
    for _ in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        resampled = m[idx]
        # A degenerate resample (all identical rows) has no between-target variance; skip it.
        if np.allclose(resampled.std(axis=0), 0.0):
            continue
        est = _icc_from_anova(_two_way_anova(resampled), kind)
        if np.isfinite(est):
            estimates.append(est)
    if len(estimates) < max(2, n_resamples // 10):
        raise ValueError(
            f"bootstrap produced too few finite ICC estimates ({len(estimates)}); "
            "data may be degenerate"
        )
    arr = np.asarray(estimates)
    lower = float(np.percentile(arr, 100.0 * alpha / 2.0))
    upper = float(np.percentile(arr, 100.0 * (1.0 - alpha / 2.0)))
    return IccEstimate(
        kind=kind,
        n=n,
        k=m.shape[1],
        point=point,
        ci_lower=lower,
        ci_upper=upper,
        alpha=alpha,
        method=f"bootstrap_{n_resamples}_seed{seed}",
    )
