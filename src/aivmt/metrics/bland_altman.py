"""Bland-Altman agreement analysis (bias, limits of agreement, proportional-bias test).

Compares two scorers of the same construct (here: system vs faculty-consensus overall score).
Reports the mean bias, the 95% limits of agreement, and a regression of the paired difference on
the paired mean to test for proportional bias (slope != 0).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from ._special import t_two_sided_p

__all__ = ["BlandAltman", "bland_altman", "LOA_Z"]

#: Normal multiplier for the 95% limits of agreement (config constant).
LOA_Z: float = 1.96


@dataclass(frozen=True)
class BlandAltman:
    """Result of a Bland-Altman analysis of two paired measurement methods."""

    n: int
    bias: float
    sd_diff: float
    loa_lower: float
    loa_upper: float
    prop_bias_slope: float
    prop_bias_intercept: float
    prop_bias_p: float

    def to_dict(self) -> dict:
        return {
            "n": self.n,
            "bias": self.bias,
            "sd_diff": self.sd_diff,
            "loa_lower": self.loa_lower,
            "loa_upper": self.loa_upper,
            "prop_bias_slope": self.prop_bias_slope,
            "prop_bias_intercept": self.prop_bias_intercept,
            "prop_bias_p": self.prop_bias_p,
        }


def bland_altman(a: ArrayLike, b: ArrayLike) -> BlandAltman:
    """Bland-Altman analysis of paired measurements ``a`` (system) vs ``b`` (reference).

    Args:
        a: first method's scores (e.g. system overall).
        b: second method's scores (e.g. faculty-consensus overall).

    Returns:
        Bias, SD of differences, 95% limits of agreement, and proportional-bias regression.

    Raises:
        ValueError: if inputs are not equal-length 1-D sequences with n >= 3 (needed for the
            proportional-bias t-test, which has n - 2 residual degrees of freedom).
    """
    ra = np.asarray(a, dtype=float)
    rb = np.asarray(b, dtype=float)
    if ra.shape != rb.shape or ra.ndim != 1:
        raise ValueError("a and b must be equal-length 1-D sequences")
    n = ra.size
    if n < 3:
        raise ValueError(f"Bland-Altman needs n>=3 for the proportional-bias test (got n={n})")
    diff = ra - rb
    mean = (ra + rb) / 2.0
    bias = float(diff.mean())
    sd_diff = float(diff.std(ddof=1))
    loa_lower = bias - LOA_Z * sd_diff
    loa_upper = bias + LOA_Z * sd_diff

    # Proportional bias: regress difference on mean; test slope != 0.
    slope, intercept = np.polyfit(mean, diff, 1)
    predicted = slope * mean + intercept
    residuals = diff - predicted
    dof = n - 2
    ss_x = float(((mean - mean.mean()) ** 2).sum())
    if ss_x == 0.0 or dof <= 0:
        p_value = float("nan")
    else:
        residual_var = float((residuals**2).sum()) / dof
        se_slope = float(np.sqrt(residual_var / ss_x))
        if se_slope == 0.0:
            p_value = 0.0 if slope != 0.0 else 1.0
        else:
            t_stat = float(slope) / se_slope
            p_value = t_two_sided_p(t_stat, dof)
    return BlandAltman(
        n=int(n),
        bias=bias,
        sd_diff=sd_diff,
        loa_lower=float(loa_lower),
        loa_upper=float(loa_upper),
        prop_bias_slope=float(slope),
        prop_bias_intercept=float(intercept),
        prop_bias_p=float(p_value),
    )
