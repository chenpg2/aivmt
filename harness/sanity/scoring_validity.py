"""Negative controls for SQ1: destroying the system<->faculty pairing must collapse ICC.

If shuffled-pairing ICC stays high, our agreement is an artifact, not real agreement. Two
controls operate on seeded synthetic fixtures so they run before real data exists; the identical
checks apply to real (system, faculty) data later:
  - ``check_shuffled_pairing_collapses_icc``: the minimal 2-column ICC control (machinery lock).
  - ``check_validity_suite_negative_control``: exercises the FULL encounters x raters suite and
    shows the headline overall ICC collapses when system scores are permuted across encounters.
"""

from __future__ import annotations

import numpy as np

from aivmt.metrics import icc, run_validity_suite
from aivmt.metrics.validity import ALL_DIMENSIONS, ORDINAL_ANCHORS, ORDINAL_DIMENSIONS


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


def make_validity_fixture(
    n: int = 30, k: int = 3, seed: int = 42, noise_sd: float = 0.06
) -> tuple[dict[str, dict[str, float]], list[dict[str, object]]]:
    """Seeded synthetic encounters x raters fixture exercising the FULL validity suite.

    Each encounter has a latent per-dimension quality; system and every faculty rater observe it
    with small noise (faculty also carries a tiny systematic rater bias). Ordinal-anchored
    dimensions (SEGUE domains + reasoning) are drawn on the {0, 0.5, 1.0} anchor grid so quadratic
    weighted kappa is meaningful. Returns (system_by_id, faculty_rows-in-long-format).
    """
    rng = np.random.default_rng(seed)
    raters = [f"R{j + 1}" for j in range(k)]
    rater_bias = rng.normal(0.0, 0.03, k)
    ordinal = set(ORDINAL_DIMENSIONS)
    continuous = [d for d in ALL_DIMENSIONS if d not in ordinal]

    system_by_id: dict[str, dict[str, float]] = {}
    faculty_rows: list[dict[str, object]] = []
    for i in range(n):
        eid = f"syn_enc_{i:03d}"
        latent: dict[str, float] = {}
        for d in continuous:
            latent[d] = float(rng.uniform(0.2, 0.95))
        for d in ordinal:
            latent[d] = float(ORDINAL_ANCHORS[int(rng.integers(0, len(ORDINAL_ANCHORS)))])

        system_by_id[eid] = {
            d: float(np.clip(latent[d] + rng.normal(0.0, noise_sd), 0.0, 1.0)) for d in ALL_DIMENSIONS
        }
        for j, rid in enumerate(raters):
            row: dict[str, object] = {"encounter_id": eid, "rater_id": rid, "notes": ""}
            for d in ALL_DIMENSIONS:
                row[d] = float(np.clip(latent[d] + rater_bias[j] + rng.normal(0.0, noise_sd), 0.0, 1.0))
            faculty_rows.append(row)
    return system_by_id, faculty_rows


def check_validity_suite_negative_control(
    seed: int = 42, true_min: float = 0.6, shuffled_max: float = 0.3
) -> dict:
    """Run the full suite on the fixture; the overall system-vs-consensus ICC must collapse when
    system scores are permuted across encounters."""
    system_by_id, faculty_rows = make_validity_fixture(seed=seed)
    res_true = run_validity_suite(system_by_id, faculty_rows, seed=seed)
    true_icc = res_true["system_vs_consensus_icc"]["overall"]["icc2_1"]["point"]

    eids = sorted(system_by_id)
    perm = np.random.default_rng(seed + 1).permutation(len(eids))
    if np.all(perm == np.arange(len(eids))):  # guard against the identity permutation
        perm = np.roll(perm, 1)
    shuffled_system = {eids[i]: system_by_id[eids[perm[i]]] for i in range(len(eids))}
    res_shuf = run_validity_suite(shuffled_system, faculty_rows, seed=seed)
    shuffled_icc = res_shuf["system_vs_consensus_icc"]["overall"]["icc2_1"]["point"]

    assert true_icc >= true_min, f"fixture true overall ICC too low ({true_icc:.3f}) — fixture broken"
    assert shuffled_icc <= shuffled_max, (
        f"NEGATIVE CONTROL FAILED: shuffled overall ICC {shuffled_icc:.3f} did not collapse "
        f"(<= {shuffled_max}); agreement may be an artifact"
    )
    return {"true_icc": float(true_icc), "shuffled_icc": float(shuffled_icc)}
