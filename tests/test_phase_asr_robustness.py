"""PhaseAsrRobustness harness wiring: the curve degrades, negative controls fire, benchmark
populates the evidence table, and the contract validates a real-shaped artifact + rejects mocks.

All numbers come from the mock LLM / seeded synthetic zh fixture (the GPU is busy), so this verifies
the LOGIC of the ICC-degradation curve, never a real-model batch."""

from __future__ import annotations

import json

import pytest

from aivmt.asr import (
    AsrDegradationCurve,
    CurvePoint,
    build_zh_golded_dataset,
    compute_curve,
    write_curve_artifacts,
)
from harness.contracts.asr_robustness import check_asr_robustness_inputs
from harness.registry import PHASE_REGISTRY, PhaseAsrRobustness, load_seed
from harness.sanity.asr_robustness import (
    KeywordCountMock,
    _CASE,
    check_clean_level_reproduces_anchor,
    check_degenerate_curve_point_is_nan_not_silent,
    check_degradation_is_monotone_ish,
    check_scramble_collapses_icc,
)

SEED = load_seed()


# --- registration ---------------------------------------------------------------------------------
def test_phase_registered() -> None:
    assert "phase_asr_robustness" in PHASE_REGISTRY
    assert PHASE_REGISTRY["phase_asr_robustness"] is PhaseAsrRobustness


# --- negative controls ----------------------------------------------------------------------------
def test_clean_level_reproduces_anchor() -> None:
    out = check_clean_level_reproduces_anchor(seed=SEED)
    assert out["clean_icc"] >= 0.5


def test_degradation_is_monotone_ish() -> None:
    out = check_degradation_is_monotone_ish(seed=SEED)
    assert out["drop"] >= 0.1
    assert out["clean_icc"] > out["high_cer_icc"]


def test_scramble_collapses_icc() -> None:
    out = check_scramble_collapses_icc(seed=SEED)
    icc = out["scrambled_icc"]
    assert (icc != icc) or icc <= 0.3  # nan (collapse) or <= ceiling
    assert out["achieved_cer"] >= 0.5


def test_degenerate_curve_point_is_nan_not_silent() -> None:
    out = check_degenerate_curve_point_is_nan_not_silent(seed=SEED)
    assert out["degenerate_icc_is_nan"] is True


# --- curve direct ---------------------------------------------------------------------------------
def test_curve_clean_anchor_is_identity_path() -> None:
    """The WER=0 point must be the identity-scored ICC (corruption machinery does not perturb it)."""
    ds = build_zh_golded_dataset(_CASE, 8)
    full = compute_curve(_CASE, ds, KeywordCountMock(), seed=SEED, wer_levels=(0.0, 0.30))
    anchor_only = compute_curve(_CASE, ds, KeywordCountMock(), seed=SEED, wer_levels=(0.0,))
    assert full.clean_icc() == anchor_only.points[0].icc_vs_gold


def test_curve_requires_two_transcripts() -> None:
    ds = build_zh_golded_dataset(_CASE, 8)[:1]
    with pytest.raises(ValueError, match=">=2 transcripts"):
        compute_curve(_CASE, ds, KeywordCountMock(), seed=SEED)


def test_curve_rejects_out_of_range_level() -> None:
    ds = build_zh_golded_dataset(_CASE, 4)
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        compute_curve(_CASE, ds, KeywordCountMock(), seed=SEED, wer_levels=(0.0, 1.5))


def test_curve_metric_is_cer() -> None:
    ds = build_zh_golded_dataset(_CASE, 4)
    curve = compute_curve(_CASE, ds, KeywordCountMock(), seed=SEED, wer_levels=(0.0, 0.15))
    assert curve.metric == "cer"


# --- benchmark / evidence-table integration -------------------------------------------------------
def test_benchmark_pending_when_no_artifact(tmp_path, monkeypatch) -> None:
    phase = PhaseAsrRobustness()
    monkeypatch.setattr(phase, "inputs", [tmp_path / "absent" / "asr_robustness.json"])
    out = phase.benchmark()
    assert out["status"] == "PENDING_REAL_DATA"
    assert out["fixture_clean_icc"] > out["fixture_high_cer_icc"]
    assert out["fixture_icc_drop"] >= 0.1


def _real_shaped_curve() -> AsrDegradationCurve:
    """A hand-built real-SHAPED curve (degrading, non-degenerate) for the contract/benchmark path."""
    return AsrDegradationCurve(
        model_id="real-model", variant="zero_shot", seed=SEED, metric="cer",
        points=(
            CurvePoint(0.0, 0.0, 0.85, 8, False),
            CurvePoint(0.05, 0.05, 0.78, 8, False),
            CurvePoint(0.15, 0.16, 0.60, 8, False),
            CurvePoint(0.30, 0.31, 0.41, 8, False),
        ),
    )


def test_benchmark_computed_with_artifact(tmp_path, monkeypatch) -> None:
    json_path, _ = write_curve_artifacts([_real_shaped_curve()], tmp_path / "phase_asr_robustness")
    phase = PhaseAsrRobustness()
    monkeypatch.setattr(phase, "inputs", [json_path])
    monkeypatch.setattr(phase, "outputs", [json_path])
    out = phase.benchmark()
    assert out["status"] == "COMPUTED"
    loaded = phase.run()
    assert loaded["curves"][0]["model_id"] == "real-model"


# --- contract -------------------------------------------------------------------------------------
def test_contract_accepts_real_shaped_curve(tmp_path) -> None:
    json_path, _ = write_curve_artifacts([_real_shaped_curve()], tmp_path)
    check_asr_robustness_inputs(json_path)  # must not raise


def test_contract_rejects_too_few_levels(tmp_path) -> None:
    bad = [{
        "model_id": "m", "variant": "zero_shot", "seed": 42, "metric": "cer",
        "points": [{"target_wer": 0.0, "achieved_cer": 0.0, "icc_vs_gold": 0.8,
                    "n_transcripts": 8, "degenerate": False}],
    }]
    p = tmp_path / "asr_robustness.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(AssertionError, match="curve points"):
        check_asr_robustness_inputs(p)


def test_contract_rejects_missing_clean_anchor(tmp_path) -> None:
    bad = [{
        "model_id": "m", "variant": "zero_shot", "seed": 42, "metric": "cer",
        "points": [
            {"target_wer": 0.15, "achieved_cer": 0.15, "icc_vs_gold": 0.6,
             "n_transcripts": 8, "degenerate": False},
            {"target_wer": 0.30, "achieved_cer": 0.30, "icc_vs_gold": 0.4,
             "n_transcripts": 8, "degenerate": False},
        ],
    }]
    p = tmp_path / "asr_robustness.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(AssertionError, match="WER=0 anchor"):
        check_asr_robustness_inputs(p)


def test_contract_rejects_nan_in_non_degenerate_point(tmp_path) -> None:
    bad = [{
        "model_id": "m", "variant": "zero_shot", "seed": 42, "metric": "cer",
        "points": [
            {"target_wer": 0.0, "achieved_cer": 0.0, "icc_vs_gold": 0.8,
             "n_transcripts": 8, "degenerate": False},
            {"target_wer": 0.30, "achieved_cer": 0.30, "icc_vs_gold": float("nan"),
             "n_transcripts": 8, "degenerate": False},
        ],
    }]
    p = tmp_path / "asr_robustness.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(AssertionError, match="no silent number"):
        check_asr_robustness_inputs(p)


def test_contract_rejects_uniformly_degenerate_mock_artifact(tmp_path) -> None:
    """A constant-mock artifact (every point degenerate / ICC ~0) is the offline signature -> reject."""
    mock = [{
        "model_id": "mockA", "variant": "zero_shot", "seed": 42, "metric": "cer",
        "points": [
            {"target_wer": 0.0, "achieved_cer": 0.0, "icc_vs_gold": float("nan"),
             "n_transcripts": 8, "degenerate": True},
            {"target_wer": 0.30, "achieved_cer": 0.30, "icc_vs_gold": float("nan"),
             "n_transcripts": 8, "degenerate": True},
        ],
    }]
    p = tmp_path / "asr_robustness.json"
    p.write_text(json.dumps(mock), encoding="utf-8")
    with pytest.raises(AssertionError, match="uniformly degenerate"):
        check_asr_robustness_inputs(p)


def test_contract_accepts_curve_with_one_degenerate_point(tmp_path) -> None:
    """A degenerate point is legitimate in isolation (e.g. the catastrophic level collapsing); only
    UNIFORM collapse is rejected."""
    ok = [{
        "model_id": "real", "variant": "zero_shot", "seed": 42, "metric": "cer",
        "points": [
            {"target_wer": 0.0, "achieved_cer": 0.0, "icc_vs_gold": 0.85,
             "n_transcripts": 8, "degenerate": False},
            {"target_wer": 0.30, "achieved_cer": 0.30, "icc_vs_gold": 0.45,
             "n_transcripts": 8, "degenerate": False},
            {"target_wer": 0.9, "achieved_cer": 0.88, "icc_vs_gold": float("nan"),
             "n_transcripts": 8, "degenerate": True},
        ],
    }]
    p = tmp_path / "asr_robustness.json"
    p.write_text(json.dumps(ok), encoding="utf-8")
    check_asr_robustness_inputs(p)  # must not raise


def test_icc_range_check_tolerates_float_epsilon_above_one() -> None:
    """Regression (mirrors phase_robustness): deterministic rescoring can land the ANOVA ICC an
    epsilon above 1.0; the contract must tolerate it but still reject real out-of-range values."""
    import pytest as _pytest

    from harness.contracts.asr_robustness import _check_icc_value

    _check_icc_value(1.0000000000000007, "curve", allow_nan=False)  # must not raise
    with _pytest.raises(AssertionError, match="outside"):
        _check_icc_value(1.0 + 1e-6, "curve", allow_nan=False)
