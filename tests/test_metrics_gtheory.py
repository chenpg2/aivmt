"""G-theory tests: hand-computed variance components, D-study, and the ICC cross-check.

Hand matrix (4 persons x 2 raters), rater 2 = rater 1 + 2 (a pure rater main effect, no
interaction):
    P1: 1, 3 | P2: 3, 5 | P3: 5, 7 | P4: 7, 9
Grand mean 5; SS_person 40, SS_rater 8, SS_residual 0; MS_person 40/3, MS_rater 8, MS_resid 0.
=> var_person = (40/3)/2 = 6.6667, var_rater = 8/4 = 2.0, var_residual = 0.
=> G(k=2) = 1.0, Phi(k=2) = 6.6667/(6.6667+1.0) = 0.8696.
"""

from __future__ import annotations

from aivmt.metrics import g_theory, icc

HAND = [[1, 3], [3, 5], [5, 7], [7, 9]]


def test_variance_components_match_hand_computation() -> None:
    res = g_theory(HAND)
    comp = res.components
    assert abs(comp.var_person - 6.66667) < 1e-4
    assert abs(comp.var_rater - 2.0) < 1e-9
    assert abs(comp.var_residual - 0.0) < 1e-9


def test_observed_design_coefficients() -> None:
    res = g_theory(HAND)
    assert abs(res.g_coefficient - 1.0) < 1e-9
    assert abs(res.phi - 0.869565) < 1e-5


def test_g_equals_consistency_phi_equals_absolute_icc() -> None:
    """At n_raters = k, Phi == ICC(2,k) (absolute agreement) on the same matrix."""
    res = g_theory(HAND)
    assert abs(res.phi - icc(HAND, "icc2_k")) < 1e-9


def test_d_study_projects_increasing_reliability() -> None:
    res = g_theory(HAND, max_raters=5)
    assert [p.n_raters for p in res.d_study] == [1, 2, 3, 4, 5]
    phis = [p.phi for p in res.d_study]
    # More raters -> higher absolute dependability (monotone non-decreasing).
    assert all(b >= a - 1e-12 for a, b in zip(phis, phis[1:]))
    # Single-rater Phi is the absolute ICC(2,1).
    assert abs(res.d_study[0].phi - icc(HAND, "icc2_1")) < 1e-9


def test_negative_person_variance_is_clamped_and_raw_preserved() -> None:
    # No real between-person variance (all persons equal); rater effect only.
    noisy = [[1, 2], [1, 2], [1, 2], [1, 2]]
    res = g_theory(noisy)
    assert res.components.var_person == 0.0
    assert res.components.var_person_raw <= 0.0
