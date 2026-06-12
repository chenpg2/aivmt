"""PhaseRobustness harness wiring: negative controls fire, benchmark populates the evidence table,
and the contract validates a real artifact produced end-to-end on the mock LLM."""

from __future__ import annotations


import numpy as np
import pytest

from aivmt.robustness import build_golded_dataset, write_robustness_artifacts
from harness.contracts.robustness import MIN_PARAPHRASES, check_robustness_inputs
from harness.registry import PHASE_REGISTRY, PhaseRobustness, load_seed
from harness.sanity.robustness import (
    check_degenerate_input_is_nan_not_silent,
    check_shuffled_repeats_collapse_retest_icc,
    make_repeat_fixture,
)

SEED = load_seed()


# --- registration ----------------------------------------------------------------------------
def test_phase_registered() -> None:
    assert "phase_robustness" in PHASE_REGISTRY
    assert PHASE_REGISTRY["phase_robustness"] is PhaseRobustness


# --- negative controls -----------------------------------------------------------------------
def test_shuffled_repeats_collapse_retest_icc() -> None:
    m = check_shuffled_repeats_collapse_retest_icc(seed=SEED)
    assert m["true_icc"] >= 0.6
    assert m["shuffled_icc"] <= 0.3


def test_degenerate_input_is_nan_not_silent() -> None:
    out = check_degenerate_input_is_nan_not_silent(seed=SEED)
    assert out["degenerate_icc_is_nan"] is True


def test_repeat_fixture_is_reliable() -> None:
    from aivmt.metrics import icc

    repeats = make_repeat_fixture(seed=SEED)
    assert repeats.shape == (30, 3)
    assert float(icc(repeats, "icc2_1")) >= 0.6


def test_shuffle_control_actually_collapses() -> None:
    """Direct check that independent column shuffles destroy the pairing."""
    repeats = make_repeat_fixture(seed=SEED)
    from aivmt.metrics import icc

    rng = np.random.default_rng(SEED + 1)
    shuffled = np.column_stack(
        [repeats[rng.permutation(repeats.shape[0]), j] for j in range(repeats.shape[1])]
    )
    assert float(icc(shuffled, "icc2_1")) <= 0.3


# --- benchmark / evidence-table integration ---------------------------------------------------
def test_benchmark_pending_when_no_artifact(tmp_path, monkeypatch) -> None:
    """Without the batch artifact, benchmark reports the seeded fixture cross-check (reproducible)."""
    phase = PhaseRobustness()
    # Point inputs at a missing path so inputs_exist() is False regardless of CWD.
    monkeypatch.setattr(phase, "inputs", [tmp_path / "absent" / "robustness.json"])
    out = phase.benchmark()
    assert out["status"] == "PENDING_REAL_DATA"
    assert "fixture_true_retest_icc" in out
    assert "fixture_shuffled_retest_icc" in out
    assert out["fixture_true_retest_icc"] >= 0.6
    assert out["fixture_shuffled_retest_icc"] <= 0.3


def test_benchmark_computed_with_artifact(tmp_path, monkeypatch) -> None:
    """With a valid artifact present, benchmark reports COMPUTED and the contract passes."""
    from aivmt.robustness import (
        RobustnessReport,
        paraphrase_sensitivity,
        retest_reliability,
        transcripts_only,
    )
    from tests.test_robustness import QualityMock, _CASE  # reuse the controllable mock

    ds = build_golded_dataset(_CASE, 8)
    para = paraphrase_sensitivity(_CASE, ds, QualityMock())
    retest = retest_reliability(
        _CASE, transcripts_only(ds), lambda s, t: QualityMock(seed=s, jitter=0.0),
        temperature=0.0, seeds=[1, 2],
    )
    report = RobustnessReport("quality-mock", "zero_shot", SEED, para, (retest,))
    out_dir = tmp_path / "phase_robustness"
    json_path, _ = write_robustness_artifacts([report], out_dir)

    phase = PhaseRobustness()
    monkeypatch.setattr(phase, "inputs", [json_path])
    monkeypatch.setattr(phase, "outputs", [json_path])
    out = phase.benchmark()
    assert out["status"] == "COMPUTED"
    # run() validates + reloads the artifact.
    loaded = phase.run()
    assert loaded["reports"][0]["model_id"] == "quality-mock"


# --- contract --------------------------------------------------------------------------------
def test_contract_rejects_too_few_paraphrases(tmp_path) -> None:
    import json

    bad = [
        {
            "model_id": "m", "variant": "zero_shot", "seed": 42,
            "paraphrase": {
                "n_paraphrases": MIN_PARAPHRASES - 1,
                "per_paraphrase_icc": {"p0_identity": 0.9},
            },
            "test_retest": [],
        }
    ]
    p = tmp_path / "robustness.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(AssertionError, match="paraphrases"):
        check_robustness_inputs(p)


def test_contract_rejects_uniformly_degenerate_mock_artifact(tmp_path) -> None:
    """A fully synthetic mock/offline artifact (every paraphrase ICC ~0 AND every test-retest cell
    degenerate) must be refused, not read as COMPUTED — the no-silent-fallback masquerade guard."""
    import json

    from aivmt.robustness import PARAPHRASE_TEMPLATES

    mock = [
        {
            "model_id": "mockA", "variant": "zero_shot", "seed": 42,
            "paraphrase": {
                "n_paraphrases": len(PARAPHRASE_TEMPLATES),
                # constant mock score -> every ICC collapses to numeric zero (~1e-16)
                "per_paraphrase_icc": {t.name: -1.3e-16 for t in PARAPHRASE_TEMPLATES},
            },
            "test_retest": [
                {"temperature": 0.0, "n_repeats": 2, "retest_icc": float("nan"),
                 "mean_cv": 0.0, "degenerate": True}
            ],
        }
    ]
    p = tmp_path / "robustness.json"
    p.write_text(json.dumps(mock), encoding="utf-8")
    with pytest.raises(AssertionError, match="uniformly degenerate"):
        check_robustness_inputs(p)


def test_contract_accepts_real_shaped_artifact_with_one_degenerate_cell(tmp_path) -> None:
    """A degenerate cell is legitimate in isolation: an artifact with real paraphrase spread and a
    mix of degenerate + non-degenerate cells must still pass (guard only rejects UNIFORM collapse)."""
    import json

    from aivmt.robustness import PARAPHRASE_TEMPLATES

    ok = [
        {
            "model_id": "real", "variant": "zero_shot", "seed": 42,
            "paraphrase": {
                "n_paraphrases": len(PARAPHRASE_TEMPLATES),
                "per_paraphrase_icc": {t.name: 0.8 for t in PARAPHRASE_TEMPLATES},
            },
            "test_retest": [
                {"temperature": 0.0, "n_repeats": 2, "retest_icc": float("nan"),
                 "mean_cv": 0.0, "degenerate": True},
                {"temperature": 0.3, "n_repeats": 3, "retest_icc": 0.88,
                 "mean_cv": 0.05, "degenerate": False},
            ],
        }
    ]
    p = tmp_path / "robustness.json"
    p.write_text(json.dumps(ok), encoding="utf-8")
    check_robustness_inputs(p)  # must not raise


def test_contract_rejects_nan_in_non_degenerate_cell(tmp_path) -> None:
    import json

    from aivmt.robustness import PARAPHRASE_TEMPLATES

    bad = [
        {
            "model_id": "m", "variant": "zero_shot", "seed": 42,
            "paraphrase": {
                "n_paraphrases": len(PARAPHRASE_TEMPLATES),
                "per_paraphrase_icc": {t.name: 0.9 for t in PARAPHRASE_TEMPLATES},
            },
            "test_retest": [
                {"temperature": 0.3, "n_repeats": 3, "retest_icc": float("nan"),
                 "mean_cv": 0.1, "degenerate": False}
            ],
        }
    ]
    p = tmp_path / "robustness.json"
    # json.dumps emits NaN by default (allow_nan=True); the contract must still reject it.
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(AssertionError, match="no silent number"):
        check_robustness_inputs(p)
