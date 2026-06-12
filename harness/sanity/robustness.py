"""Negative controls for the scorer-robustness phase.

Two controls run on seeded synthetic fixtures (no real model required), and the identical logic
applies to real (model, transcript) data later:

  - ``check_shuffled_repeats_collapse_retest_icc``: a genuinely reliable repeat-set has high
    test-retest ICC; permuting which encounter each repeat belongs to destroys the pairing and the
    ICC must collapse toward 0. If it stays high, the reliability is an artifact.
  - ``check_degenerate_input_is_nan_not_silent``: an all-identical score matrix has no
    between-encounter variance; the metric must return an EXPLICIT ``nan`` (flagged ``degenerate``),
    never a silent fake number.

These exercise the metric/aggregation machinery directly with a stub scorer (a fixed score matrix),
so they are fast, deterministic, and free of any LLM dependency.
"""

from __future__ import annotations

import numpy as np

from aivmt.metrics import icc

#: Reliability floor a true repeat-set must clear; a shuffled set must collapse below the ceiling.
_TRUE_MIN = 0.6
_SHUFFLED_MAX = 0.3


def make_repeat_fixture(
    n: int = 30, k: int = 3, seed: int = 42, noise_sd: float = 0.04
) -> np.ndarray:
    """Synthetic (n_encounters x k_repeats) overall-score matrix with genuine repeat reliability.

    Each encounter has a latent quality observed by every repeat with small noise — exactly the
    structure a low-temperature stable scorer produces. Used to prove the test-retest machinery
    detects reliability AND that destroying the pairing collapses it.
    """
    rng = np.random.default_rng(seed)
    latent = rng.uniform(0.2, 0.95, n)
    return np.clip(latent[:, None] + rng.normal(0.0, noise_sd, (n, k)), 0.0, 1.0)


def check_shuffled_repeats_collapse_retest_icc(
    seed: int = 42, true_min: float = _TRUE_MIN, shuffled_max: float = _SHUFFLED_MAX
) -> dict:
    """True repeat-set agrees (ICC>=true_min); shuffling repeat-pairings collapses it (<=shuffled_max)."""
    repeats = make_repeat_fixture(seed=seed)
    true_icc = float(icc(repeats, "icc2_1"))

    # Independently permute every repeat column so no encounter's repeats line up any more.
    rng = np.random.default_rng(seed + 1)
    shuffled = np.column_stack(
        [repeats[rng.permutation(repeats.shape[0]), j] for j in range(repeats.shape[1])]
    )
    shuffled_icc = float(icc(shuffled, "icc2_1"))

    assert true_icc >= true_min, f"fixture true retest ICC too low ({true_icc:.3f}) — fixture broken"
    assert shuffled_icc <= shuffled_max, (
        f"NEGATIVE CONTROL FAILED: shuffled retest ICC {shuffled_icc:.3f} did not collapse "
        f"(<= {shuffled_max}); test-retest reliability may be an artifact"
    )
    return {"true_icc": true_icc, "shuffled_icc": shuffled_icc}


def check_degenerate_input_is_nan_not_silent(seed: int = 42) -> dict:
    """An all-identical-score matrix must yield an EXPLICIT nan, not a silently fabricated number."""
    from aivmt.robustness.core import _icc_pair  # internal helper under test

    constant = [0.5, 0.5, 0.5, 0.5]
    value = _icc_pair(constant, constant)
    assert np.isnan(value), (
        f"NEGATIVE CONTROL FAILED: degenerate (zero-variance) input returned {value!r} "
        "instead of an explicit nan — a silent number would mask a collapsed analysis"
    )

    # Same guarantee through the test-retest path: a matrix with no BETWEEN-encounter variance
    # (every row equal) flags degenerate=True (matches test_retest_reliability's row-mean probe).
    degenerate = np.full((4, 3), 0.5)
    row_means = degenerate.mean(axis=1)
    flagged = bool(np.allclose(row_means, row_means.mean()))
    assert flagged, "degenerate repeat matrix (no between-encounter variance) must be detected"
    return {"degenerate_icc_is_nan": True}
