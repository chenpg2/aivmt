"""Tests for ICC confidence intervals, the bootstrap cross-check, and the stats primitives.

Primitives are validated against analytic values and published F-table critical values; the ICC
CI is validated against the Shrout & Fleiss (1979) matrix, whose ICC(2,1) 95% CI is reported by
the `psych` R package as [0.019, 0.761] — reproduced here to 3 decimals.
"""

from __future__ import annotations

import math

import numpy as np

from aivmt.metrics import bootstrap_icc_ci, icc, icc_with_ci
from aivmt.metrics._special import f_cdf, f_ppf, regularized_incomplete_beta, t_two_sided_p

# Shrout & Fleiss (1979), Table 1: 6 targets x 4 judges.
SF = [
    [9, 2, 5, 8],
    [6, 1, 3, 2],
    [8, 4, 6, 8],
    [7, 1, 2, 6],
    [10, 5, 6, 9],
    [6, 2, 4, 7],
]


# --- Special functions -------------------------------------------------------------------------
def test_incomplete_beta_analytic_values() -> None:
    assert abs(regularized_incomplete_beta(2, 3, 0.5) - 0.6875) < 1e-9
    assert abs(regularized_incomplete_beta(1, 1, 0.3) - 0.3) < 1e-9  # uniform CDF
    # symmetry I_x(a,b) = 1 - I_{1-x}(b,a)
    assert abs(
        regularized_incomplete_beta(2.5, 4.0, 0.4)
        - (1.0 - regularized_incomplete_beta(4.0, 2.5, 0.6))
    ) < 1e-12


def test_f_quantiles_match_published_tables() -> None:
    assert abs(f_ppf(0.95, 2, 10) - 4.103) < 1e-2
    assert abs(f_ppf(0.95, 5, 15) - 2.901) < 1e-2
    assert abs(f_ppf(0.95, 1, 10) - 4.965) < 1e-2


def test_f_ppf_round_trips_through_cdf() -> None:
    for p in (0.025, 0.5, 0.975):
        f = f_ppf(p, 3, 12)
        assert abs(f_cdf(f, 3, 12) - p) < 1e-8


def test_t_two_sided_p_matches_table() -> None:
    # t_{0.025, 10} = 2.228 -> two-sided p = 0.05.
    assert abs(t_two_sided_p(2.228, 10) - 0.05) < 1e-3
    assert abs(t_two_sided_p(0.0, 10) - 1.0) < 1e-12


# --- ICC point estimate vs published reference (3 decimals) ------------------------------------
def test_icc_point_estimates_match_shrout_fleiss_to_three_decimals() -> None:
    assert round(icc(SF, "icc2_1"), 3) == 0.290
    assert round(icc(SF, "icc2_k"), 3) == 0.620


# --- ICC parametric CI vs psych reference for the SF matrix ------------------------------------
def test_icc2_1_ci_matches_published_reference() -> None:
    est = icc_with_ci(SF, "icc2_1")
    assert round(est.point, 3) == 0.290
    assert round(est.ci_lower, 3) == 0.019
    assert round(est.ci_upper, 3) == 0.761
    assert est.ci_lower < est.point < est.ci_upper


def test_icc2_k_ci_spearman_brown_step_up() -> None:
    est = icc_with_ci(SF, "icc2_k")
    assert round(est.point, 3) == 0.620
    assert round(est.ci_lower, 3) == 0.071
    assert round(est.ci_upper, 3) == 0.927


def test_icc_ci_brackets_point_on_high_agreement() -> None:
    rng = np.random.default_rng(7)
    truth = rng.uniform(0, 1, 40)
    data = np.column_stack([truth + rng.normal(0, 0.03, 40), truth + rng.normal(0, 0.03, 40)])
    est = icc_with_ci(data, "icc2_1")
    assert est.point > 0.8
    assert est.ci_lower <= est.point <= est.ci_upper


# --- Bootstrap CI (seeded) -----------------------------------------------------------------------
def test_bootstrap_ci_is_seed_reproducible() -> None:
    rng = np.random.default_rng(11)
    truth = rng.uniform(0, 1, 50)
    data = np.column_stack([truth + rng.normal(0, 0.05, 50), truth + rng.normal(0, 0.05, 50)])
    a = bootstrap_icc_ci(data, seed=42, kind="icc2_1", n_resamples=500)
    b = bootstrap_icc_ci(data, seed=42, kind="icc2_1", n_resamples=500)
    assert (a.ci_lower, a.ci_upper) == (b.ci_lower, b.ci_upper)
    assert a.ci_lower < a.point < a.ci_upper


def test_bootstrap_and_parametric_ci_agree_on_clean_fixture() -> None:
    rng = np.random.default_rng(3)
    truth = rng.uniform(0, 1, 60)
    data = np.column_stack([truth + rng.normal(0, 0.04, 60), truth + rng.normal(0, 0.04, 60)])
    par = icc_with_ci(data, "icc2_1")
    boot = bootstrap_icc_ci(data, seed=42, kind="icc2_1", n_resamples=1000)
    # Two independent CI methods should land in the same neighbourhood.
    assert abs(par.point - boot.point) < 1e-9
    assert abs(par.ci_lower - boot.ci_lower) < 0.15
    assert abs(par.ci_upper - boot.ci_upper) < 0.15


def test_ci_values_are_finite() -> None:
    est = icc_with_ci(SF, "icc2_1")
    assert math.isfinite(est.ci_lower) and math.isfinite(est.ci_upper)
