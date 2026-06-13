"""Negative controls for the local-vs-cloud phase.

Three controls, all LLM-free and seeded, exercising the exact machinery the real comparison uses:

  - ``check_shuffled_gold_collapses_icc``: a genuinely valid scorer tracks the gold (high ICC);
    permuting which gold each encounter pairs with destroys the alignment and the overall ICC must
    collapse toward 0. Reuses the quant lane's validity fixture so the two lanes share one notion of
    "a valid scorer" (the local-vs-cloud overall ICC is the same estimator).
  - ``check_degenerate_cell_is_nan_not_silent``: a constant system-score column (a model that can no
    longer discriminate — exactly the cloud-collapse failure mode on a communication subdomain) must
    yield an EXPLICIT nan flagged degenerate, never a silent fake number.
  - ``check_phi_guard_blocks_real_data_path``: the STRUCTURAL PHI guard must REFUSE (raise) a path
    resolving inside ``data/transcripts`` / ``data/encounters``, and must ACCEPT a synthetic-fixture
    path. This is the control that proves real PHI can never reach a cloud endpoint.

The first two delegate to the quant lane's fixtures (identical ICC logic), so they stay fast,
deterministic, and free of any LLM/network dependency.
"""

from __future__ import annotations

import math
from pathlib import Path

from aivmt.cloud import (
    PhiLeakError,
    assert_path_is_offdevice_safe,
)
from aivmt.cloud.provenance import REAL_DATA_DIRS
from aivmt.quant import validity_icc
from harness.sanity.quant_frontier import make_validity_fixture

#: Validity floor a true scorer must clear; a shuffled-gold pairing must collapse below the ceiling.
_TRUE_MIN = 0.6
_SHUFFLED_MAX = 0.3


def check_shuffled_gold_collapses_icc(
    seed: int = 42, true_min: float = _TRUE_MIN, shuffled_max: float = _SHUFFLED_MAX
) -> dict:
    """True scorer agrees with gold (ICC>=true_min); shuffling the gold pairing collapses it."""
    import numpy as np

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
    """A constant system-score column (collapsed scorer) must yield an EXPLICIT nan, not a fake number."""
    import numpy as np

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


def check_phi_guard_blocks_real_data_path(seed: int = 42) -> dict:
    """The PHI guard MUST refuse real-data paths and MUST accept synthetic-fixture paths.

    This is the structural guarantee that a future real-data run cannot leak PHI to a cloud endpoint:
    if the guard ever stops raising on a ``data/transcripts`` / ``data/encounters`` path, this control
    fails and sinks ``run_all``.
    """
    _ = seed  # control is deterministic; seed accepted for a uniform phase.sanity() signature
    blocked = 0
    for real_dir in REAL_DATA_DIRS:
        real_path = Path("/Users/x/AIVMT") / real_dir / "patient_001.json"
        try:
            assert_path_is_offdevice_safe(real_path)
        except PhiLeakError:
            blocked += 1
        else:  # pragma: no cover - reaching here is the control FAILING
            raise AssertionError(
                f"PHI GUARD FAILED: real-data path {real_path} was NOT refused — PHI could leak to "
                "a cloud endpoint"
            )
    assert blocked == len(REAL_DATA_DIRS), "PHI guard did not block every real-data directory"

    # A synthetic-fixture path (outside the real-data dirs) must pass through unharmed.
    safe = assert_path_is_offdevice_safe(Path("/tmp/synthetic_fixtures/case_demo.json"))
    assert safe is not None, "PHI guard wrongly rejected a synthetic-fixture path"
    return {"real_data_dirs_blocked": blocked, "synthetic_path_allowed": True}


__all__ = [
    "check_shuffled_gold_collapses_icc",
    "check_degenerate_cell_is_nan_not_silent",
    "check_phi_guard_blocks_real_data_path",
]
