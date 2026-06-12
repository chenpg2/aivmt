"""Tests for agreement metrics, validated against the Shrout & Fleiss (1979) example."""

from __future__ import annotations

import math

from aivmt.metrics import icc, percent_agreement, quadratic_weighted_kappa

# Shrout & Fleiss (1979), Table 1: 6 targets x 4 judges.
SF = [
    [9, 2, 5, 8],
    [6, 1, 3, 2],
    [8, 4, 6, 8],
    [7, 1, 2, 6],
    [10, 5, 6, 9],
    [6, 2, 4, 7],
]


def test_icc2_1_matches_known_value() -> None:
    # Known ICC(2,1) ~= 0.290 for the Shrout & Fleiss example.
    assert abs(icc(SF, "icc2_1") - 0.290) < 0.01


def test_icc2_k_matches_known_value() -> None:
    # Known ICC(2,k=4) ~= 0.620 for the Shrout & Fleiss example.
    assert abs(icc(SF, "icc2_k") - 0.620) < 0.01


def test_icc_perfect_agreement_is_one() -> None:
    perfect = [[1, 1], [2, 2], [3, 3], [4, 4]]
    assert abs(icc(perfect, "icc2_1") - 1.0) < 1e-9


def test_quadratic_weighted_kappa_perfect_and_range() -> None:
    assert abs(quadratic_weighted_kappa([0, 1, 2, 3], [0, 1, 2, 3]) - 1.0) < 1e-9
    qwk = quadratic_weighted_kappa([0, 1, 2, 3], [0, 1, 3, 2])
    assert -1.0 <= qwk <= 1.0


def test_percent_agreement() -> None:
    assert percent_agreement([1, 2, 3, 4], [1, 2, 9, 4]) == 0.75


def test_icc_finite() -> None:
    assert math.isfinite(icc(SF, "icc2_1"))
    assert math.isfinite(icc(SF, "icc2_k"))
