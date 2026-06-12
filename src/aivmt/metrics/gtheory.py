"""Generalizability theory for the persons x raters (p x r) crossed random design.

ANOVA variance-component estimators for the faculty rating matrix (persons = encounters,
raters = faculty), the relative G-coefficient and absolute dependability (Phi), and a D-study
table projecting reliability for varying numbers of raters. For a single rating per cell the
p x r interaction is confounded with residual error, so ``var_residual`` denotes that combined
term. With ``n_raters = k`` the relative coefficient equals ICC(C,k) (consistency) and Phi
equals ICC(A,k) (absolute agreement) on the same matrix — used as a cross-check in tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

logger = logging.getLogger(__name__)

__all__ = [
    "VarianceComponents",
    "DStudyPoint",
    "GTheoryResult",
    "g_theory",
    "DEFAULT_DSTUDY_MAX_RATERS",
]

#: Number of raters to project in the D-study table (k = 1..MAX). Config constant.
DEFAULT_DSTUDY_MAX_RATERS: int = 5


@dataclass(frozen=True)
class VarianceComponents:
    """Estimated variance components for the p x r crossed design (clamped at 0)."""

    var_person: float
    var_rater: float
    var_residual: float
    var_person_raw: float  # pre-clamp estimate (may be negative)
    var_rater_raw: float

    def to_dict(self) -> dict:
        return {
            "var_person": self.var_person,
            "var_rater": self.var_rater,
            "var_residual": self.var_residual,
            "var_person_raw": self.var_person_raw,
            "var_rater_raw": self.var_rater_raw,
        }


@dataclass(frozen=True)
class DStudyPoint:
    """Projected reliability for a given number of raters."""

    n_raters: int
    g_coefficient: float
    phi: float

    def to_dict(self) -> dict:
        return {"n_raters": self.n_raters, "g_coefficient": self.g_coefficient, "phi": self.phi}


@dataclass(frozen=True)
class GTheoryResult:
    """Variance components, observed-design coefficients, and the D-study projection."""

    n_persons: int
    n_raters: int
    components: VarianceComponents
    g_coefficient: float
    phi: float
    d_study: tuple[DStudyPoint, ...]

    def to_dict(self) -> dict:
        return {
            "n_persons": self.n_persons,
            "n_raters": self.n_raters,
            "components": self.components.to_dict(),
            "g_coefficient": self.g_coefficient,
            "phi": self.phi,
            "d_study": [p.to_dict() for p in self.d_study],
        }


def _coefficients(comp: VarianceComponents, n_raters: int) -> tuple[float, float]:
    """Relative G-coefficient and absolute Phi for a design averaging over ``n_raters`` raters."""
    vp = comp.var_person
    rel_error = comp.var_residual / n_raters
    abs_error = (comp.var_rater + comp.var_residual) / n_raters
    g = vp / (vp + rel_error) if (vp + rel_error) > 0 else float("nan")
    phi = vp / (vp + abs_error) if (vp + abs_error) > 0 else float("nan")
    return float(g), float(phi)


def g_theory(
    matrix: ArrayLike,
    max_raters: int = DEFAULT_DSTUDY_MAX_RATERS,
) -> GTheoryResult:
    """Estimate variance components, G / Phi, and the D-study for a p x r matrix.

    Args:
        matrix: shape (n_persons, n_raters); cell = one rater's score for one person.
        max_raters: largest rater count to project in the D-study (k = 1..max_raters).

    Returns:
        Variance components, observed-design G and Phi, and the D-study projection.
    """
    m = np.asarray(matrix, dtype=float)
    if m.ndim != 2 or m.shape[0] < 2 or m.shape[1] < 2:
        raise ValueError("g_theory needs a (n_persons, n_raters) matrix with n>=2 and k>=2")
    if not np.isfinite(m).all():
        raise ValueError("g_theory input contains non-finite values; resolve missing data first")
    n, k = m.shape
    grand = m.mean()
    ss_person = k * ((m.mean(axis=1) - grand) ** 2).sum()
    ss_rater = n * ((m.mean(axis=0) - grand) ** 2).sum()
    ss_total = ((m - grand) ** 2).sum()
    ss_resid = ss_total - ss_person - ss_rater
    ms_person = ss_person / (n - 1)
    ms_rater = ss_rater / (k - 1)
    ms_resid = ss_resid / ((n - 1) * (k - 1))

    var_person_raw = (ms_person - ms_resid) / k
    var_rater_raw = (ms_rater - ms_resid) / n
    var_residual = max(ms_resid, 0.0)
    if var_person_raw < 0:
        logger.warning("g_theory: negative person variance estimate %.4g clamped to 0", var_person_raw)
    if var_rater_raw < 0:
        logger.warning("g_theory: negative rater variance estimate %.4g clamped to 0", var_rater_raw)
    components = VarianceComponents(
        var_person=max(var_person_raw, 0.0),
        var_rater=max(var_rater_raw, 0.0),
        var_residual=var_residual,
        var_person_raw=float(var_person_raw),
        var_rater_raw=float(var_rater_raw),
    )
    g_obs, phi_obs = _coefficients(components, k)
    d_study = tuple(
        DStudyPoint(n_raters=r, g_coefficient=_coefficients(components, r)[0],
                    phi=_coefficients(components, r)[1])
        for r in range(1, max_raters + 1)
    )
    return GTheoryResult(
        n_persons=int(n),
        n_raters=int(k),
        components=components,
        g_coefficient=g_obs,
        phi=phi_obs,
        d_study=d_study,
    )
