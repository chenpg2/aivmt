"""Negative controls for the quantization-frontier phase.

Both controls run on a seeded synthetic ``(system_score, gold)`` fixture (no real model required),
and the identical ICC logic applies to real ``(model, transcript)`` cells later:

  - ``check_shuffled_gold_collapses_icc``: a genuinely valid scorer tracks the gold (high ICC);
    permuting which gold each encounter is paired with destroys the alignment and the ICC must
    collapse toward 0. If it stays high, the validity is an artifact of the aggregation.
  - ``check_degenerate_cell_is_nan_not_silent``: a constant system-score column (an over-quantized
    model that can no longer discriminate) has no between-encounter variance; the metric must return
    an EXPLICIT ``nan`` flagged degenerate, never a silent fake number.

These exercise the metric machinery directly with a fixed score vector, so they are fast,
deterministic, and free of any LLM or ``ollama`` dependency.
"""

from __future__ import annotations

import math

import numpy as np

from aivmt.quant import validity_icc

#: Validity floor a true scorer must clear; a shuffled-gold pairing must collapse below the ceiling.
_TRUE_MIN = 0.6
_SHUFFLED_MAX = 0.3


def make_validity_fixture(
    n: int = 30, seed: int = 42, noise_sd: float = 0.05
) -> tuple[list[float], list[float]]:
    """Synthetic ``(system_scores, golds)`` with genuine validity.

    Each encounter has a latent quality that IS the gold and that the scorer observes with small
    noise — exactly the structure a valid local-model scorer produces. Used to prove the ICC
    machinery detects validity AND that destroying the pairing collapses it.
    """
    rng = np.random.default_rng(seed)
    latent = rng.uniform(0.15, 0.95, n)
    system = np.clip(latent + rng.normal(0.0, noise_sd, n), 0.0, 1.0)
    return system.tolist(), latent.tolist()


def check_shuffled_gold_collapses_icc(
    seed: int = 42, true_min: float = _TRUE_MIN, shuffled_max: float = _SHUFFLED_MAX
) -> dict:
    """True scorer agrees with gold (ICC>=true_min); shuffling the gold pairing collapses it."""
    system, gold = make_validity_fixture(seed=seed)
    true_icc, _, true_degenerate = validity_icc(system, gold)

    rng = np.random.default_rng(seed + 1)
    shuffled = [gold[i] for i in rng.permutation(len(gold))]
    shuffled_icc, _, _ = validity_icc(system, shuffled)

    assert not true_degenerate, "fixture system column is degenerate — fixture broken"
    assert true_icc >= true_min, f"fixture true ICC too low ({true_icc:.3f}) — fixture broken"
    assert shuffled_icc <= shuffled_max, (
        f"NEGATIVE CONTROL FAILED: shuffled-gold ICC {shuffled_icc:.3f} did not collapse "
        f"(<= {shuffled_max}); the validity may be an artifact"
    )
    return {"true_icc": true_icc, "shuffled_icc": shuffled_icc}


def check_degenerate_cell_is_nan_not_silent(seed: int = 42) -> dict:
    """A constant system-score column must yield an EXPLICIT nan, not a silently fabricated number."""
    rng = np.random.default_rng(seed)
    gold = rng.uniform(0.1, 0.9, 6).tolist()
    constant_system = [0.5] * len(gold)  # scorer can no longer discriminate -> zero variance

    icc2_1, icc2_k, degenerate = validity_icc(constant_system, gold)
    assert degenerate is True, "constant system column must flag degenerate=True"
    assert math.isnan(icc2_1) and math.isnan(icc2_k), (
        f"NEGATIVE CONTROL FAILED: degenerate cell returned ({icc2_1!r}, {icc2_k!r}) instead of nan "
        "— a silent number would mask a collapsed scorer"
    )
    return {"degenerate_icc_is_nan": True}


__all__ = [
    "make_validity_fixture",
    "check_shuffled_gold_collapses_icc",
    "check_degenerate_cell_is_nan_not_silent",
]
