"""Negative control for SQ1: destroying the system<->faculty pairing must collapse ICC.

If shuffled-pairing ICC stays high, our agreement is an artifact, not real agreement.
Operates on a seeded synthetic fixture so the control is runnable before real data exists;
the identical check applies to real (system, faculty) arrays later.
"""

from __future__ import annotations

import numpy as np

from aivmt.metrics import icc


def make_correlated_fixture(n: int = 40, noise_sd: float = 0.1, seed: int = 42):
    """Synthetic (system, faculty) pair with genuine agreement (system = faculty + noise)."""
    rng = np.random.default_rng(seed)
    faculty = rng.uniform(0.0, 1.0, n)
    system = np.clip(faculty + rng.normal(0.0, noise_sd, n), 0.0, 1.0)
    return system, faculty


def check_shuffled_pairing_collapses_icc(
    seed: int = 42, true_min: float = 0.6, shuffled_max: float = 0.3
) -> dict:
    """Assert true pairing agrees (ICC>=true_min) but shuffled pairing collapses (ICC<=shuffled_max)."""
    system, faculty = make_correlated_fixture(seed=seed)
    true_icc = icc(np.column_stack([system, faculty]), "icc2_1")

    shuffled = faculty.copy()
    np.random.default_rng(seed + 1).shuffle(shuffled)
    shuffled_icc = icc(np.column_stack([system, shuffled]), "icc2_1")

    assert true_icc >= true_min, f"fixture true ICC too low ({true_icc:.3f}) — fixture broken"
    assert shuffled_icc <= shuffled_max, (
        f"NEGATIVE CONTROL FAILED: shuffled ICC {shuffled_icc:.3f} did not collapse "
        f"(<= {shuffled_max}); agreement may be an artifact"
    )
    return {"true_icc": float(true_icc), "shuffled_icc": float(shuffled_icc)}
