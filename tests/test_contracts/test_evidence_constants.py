"""Drift guards (test_contracts).

Locks the metric machinery NOW (ICC correctness + the negative control). The REAL SQ1
evidence constant (local-model ICC vs faculty) is locked here after the first real-data run
of phase_scoring_validity — see the commented template at the bottom.
"""

from __future__ import annotations

from aivmt.metrics import icc
from harness.sanity.scoring_validity import check_shuffled_pairing_collapses_icc

# Shrout & Fleiss (1979) reference matrix — pins the ICC implementation.
SF = [
    [9, 2, 5, 8],
    [6, 1, 3, 2],
    [8, 4, 6, 8],
    [7, 1, 2, 6],
    [10, 5, 6, 9],
    [6, 2, 4, 7],
]


def test_icc_machinery_locked() -> None:
    assert abs(icc(SF, "icc2_1") - 0.290) < 0.01, "ICC(2,1) drifted"
    assert abs(icc(SF, "icc2_k") - 0.620) < 0.01, "ICC(2,k) drifted"


def test_negative_control_collapses() -> None:
    m = check_shuffled_pairing_collapses_icc(seed=42)
    assert m["true_icc"] >= 0.6, "fixture true agreement too low"
    assert m["shuffled_icc"] <= 0.3, "shuffled pairing failed to collapse — artifact risk"


# After the first real-data run, lock the actual SQ1 number, e.g.:
# def test_sq1_local_model_icc():
#     result = json.loads((PROJECT_ROOT / "results/phase_scoring_validity/icc.json").read_text())
#     assert 0.70 <= result["icc2_1"] <= 0.95, "SQ1 local-model ICC drifted"
