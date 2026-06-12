"""Tests for Cohen's kappa, decision consistency at a cut-score, QWK, and Bland-Altman."""

from __future__ import annotations

import math

from aivmt.metrics import (
    DEFAULT_CUT_SCORE,
    bland_altman,
    cohen_kappa,
    decision_consistency,
    quadratic_weighted_kappa,
)


# --- Cohen's kappa ----------------------------------------------------------------------------
def test_cohen_kappa_perfect_and_chance() -> None:
    assert abs(cohen_kappa([0, 1, 0, 1], [0, 1, 0, 1]) - 1.0) < 1e-9
    # Complete disagreement on a balanced binary split -> kappa = -1.
    assert abs(cohen_kappa([0, 0, 1, 1], [1, 1, 0, 0]) + 1.0) < 1e-9


def test_cohen_kappa_undefined_when_single_category() -> None:
    # Both raters place everything in one class: expected agreement 1 -> kappa undefined (nan).
    assert math.isnan(cohen_kappa([1, 1, 1, 1], [1, 1, 1, 1]))


# --- Decision consistency at a configurable cut ------------------------------------------------
def test_decision_consistency_cut_score_is_configurable() -> None:
    sys_scores = [0.9, 0.8, 0.5, 0.4]
    fac_scores = [0.7, 0.65, 0.55, 0.3]
    # Default cut 0.6: system pass/fail = [P, P, F, F], faculty = [P, P, F, F] -> perfect.
    dc = decision_consistency(sys_scores, fac_scores)
    assert dc.cut_score == DEFAULT_CUT_SCORE
    assert dc.raw_agreement == 1.0
    assert dc.n_both_pass == 2 and dc.n_both_fail == 2 and dc.n_disagree == 0

    # Raise the cut to 0.85: system = [P, F, F, F], faculty = [F, F, F, F] -> 1 disagreement.
    dc2 = decision_consistency(sys_scores, fac_scores, cut_score=0.85)
    assert dc2.cut_score == 0.85
    assert dc2.n_disagree == 1
    assert dc2.raw_agreement == 0.75


def test_decision_consistency_dict_round_trip() -> None:
    dc = decision_consistency([0.7, 0.2], [0.8, 0.1])
    d = dc.to_dict()
    assert set(d) == {
        "cut_score", "n", "raw_agreement", "cohen_kappa",
        "n_both_pass", "n_both_fail", "n_disagree",
    }


# --- Quadratic weighted kappa ------------------------------------------------------------------
def test_qwk_ordinal_partial_credit() -> None:
    # Near-misses on an ordinal scale are penalised less than far-misses.
    near = quadratic_weighted_kappa([0, 1, 2, 2], [0, 1, 2, 1], min_rating=0, max_rating=2)
    far = quadratic_weighted_kappa([0, 1, 2, 2], [0, 1, 2, 0], min_rating=0, max_rating=2)
    assert near > far


# --- Bland-Altman -------------------------------------------------------------------------------
def test_bland_altman_constant_bias() -> None:
    b = [0.2, 0.4, 0.6, 0.8]
    a = [x + 0.1 for x in b]
    res = bland_altman(a, b)
    assert abs(res.bias - 0.1) < 1e-9
    assert abs(res.sd_diff - 0.0) < 1e-9
    assert abs(res.loa_lower - 0.1) < 1e-9 and abs(res.loa_upper - 0.1) < 1e-9
    assert abs(res.prop_bias_slope - 0.0) < 1e-9


def test_bland_altman_detects_proportional_bias() -> None:
    # Construct exact proportional bias: a = (11/9) b -> diff/mean = 0.2 for every point.
    b = [0.05, 0.10, 0.20, 0.30, 0.40]
    a = [(11.0 / 9.0) * x for x in b]
    res = bland_altman(a, b)
    assert abs(res.prop_bias_slope - 0.2) < 1e-6
    assert res.prop_bias_p < 1e-6  # slope is highly significant (exact linear relationship)


def test_bland_altman_requires_min_n() -> None:
    try:
        bland_altman([0.1, 0.2], [0.1, 0.2])
    except ValueError as exc:
        assert "n>=3" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for n<3")
