"""Self-contained statistical special functions (no SciPy dependency).

scipy is intentionally NOT a project dependency (keeps the edge/LMIC footprint minimal),
so the F- and t-distribution quantiles needed for parametric ICC / Bland-Altman CIs are
implemented here on top of the regularized incomplete beta function. Algorithms follow the
continued-fraction expansion of Numerical Recipes (Lentz's method); validated in tests against
analytic values and published F-table critical values.
"""

from __future__ import annotations

import math

__all__ = [
    "regularized_incomplete_beta",
    "f_cdf",
    "f_ppf",
    "t_two_sided_p",
]

# Numerical constants for the continued-fraction evaluation.
_MAX_ITER: int = 300
_EPS: float = 3.0e-16
_FP_MIN: float = 1.0e-300


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """Lentz's continued fraction for the incomplete beta integral.

    Raises:
        RuntimeError: if the continued fraction fails to converge.
    """
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < _FP_MIN:
        d = _FP_MIN
    d = 1.0 / d
    h = d
    for m in range(1, _MAX_ITER + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < _FP_MIN:
            d = _FP_MIN
        c = 1.0 + aa / c
        if abs(c) < _FP_MIN:
            c = _FP_MIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < _FP_MIN:
            d = _FP_MIN
        c = 1.0 + aa / c
        if abs(c) < _FP_MIN:
            c = _FP_MIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _EPS:
            return h
    raise RuntimeError(f"incomplete beta continued fraction did not converge (a={a}, b={b}, x={x})")


def regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b) on x in [0, 1].

    Args:
        a: first shape parameter (> 0).
        b: second shape parameter (> 0).
        x: upper integration limit in [0, 1].

    Returns:
        I_x(a, b) in [0, 1].
    """
    if a <= 0.0 or b <= 0.0:
        raise ValueError(f"beta shape parameters must be positive (a={a}, b={b})")
    if not 0.0 <= x <= 1.0:
        raise ValueError(f"x must lie in [0, 1] (got {x})")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0
    log_beta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(log_beta + a * math.log(x) + b * math.log(1.0 - x))
    # Use the symmetry I_x(a,b) = 1 - I_{1-x}(b,a) for fast convergence.
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_continued_fraction(a, b, x) / a
    return 1.0 - front * _beta_continued_fraction(b, a, 1.0 - x) / b


def f_cdf(f: float, df1: float, df2: float) -> float:
    """Cumulative distribution function of the F(df1, df2) distribution."""
    if df1 <= 0.0 or df2 <= 0.0:
        raise ValueError(f"degrees of freedom must be positive (df1={df1}, df2={df2})")
    if f <= 0.0:
        return 0.0
    x = df1 * f / (df1 * f + df2)
    return regularized_incomplete_beta(df1 / 2.0, df2 / 2.0, x)


def f_ppf(p: float, df1: float, df2: float) -> float:
    """Quantile (inverse CDF) of the F(df1, df2) distribution via bracketed bisection.

    Args:
        p: probability in the open interval (0, 1).
        df1: numerator degrees of freedom (> 0).
        df2: denominator degrees of freedom (> 0).

    Returns:
        f such that f_cdf(f, df1, df2) == p (to ~1e-10 in probability).
    """
    if not 0.0 < p < 1.0:
        raise ValueError(f"p must lie in (0, 1) (got {p})")
    if df1 <= 0.0 or df2 <= 0.0:
        raise ValueError(f"degrees of freedom must be positive (df1={df1}, df2={df2})")
    lo, hi = 0.0, 1.0
    # Expand the upper bracket until it exceeds the target quantile.
    for _ in range(200):
        if f_cdf(hi, df1, df2) >= p:
            break
        hi *= 2.0
    else:  # pragma: no cover - guards a pathological non-convergence
        raise RuntimeError(f"could not bracket F quantile (p={p}, df1={df1}, df2={df2})")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        cdf_mid = f_cdf(mid, df1, df2)
        if abs(cdf_mid - p) < 1.0e-12 or (hi - lo) < 1.0e-12:
            return mid
        if cdf_mid < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def t_two_sided_p(t: float, df: float) -> float:
    """Two-sided p-value P(|T| >= |t|) for a Student-t statistic with df dof."""
    if df <= 0.0:
        raise ValueError(f"degrees of freedom must be positive (got {df})")
    x = df / (df + t * t)
    return regularized_incomplete_beta(df / 2.0, 0.5, x)
