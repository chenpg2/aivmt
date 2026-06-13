"""PhaseQuantFrontier harness wiring: negative controls fire, benchmark populates the evidence table,
and the contract validates a real-shaped artifact + rejects the mock-masquerade signature.

All numbers come from seeded synthetic fixtures / hand-built real-SHAPED cells (the GPU is busy and
the quant ladder is not pulled), so this verifies the LOGIC of the frontier, never a real-model batch.
"""

from __future__ import annotations

import json

import pytest

from aivmt.quant import (
    DiskUsage,
    LatencyStats,
    MemoryUsage,
    QuantCell,
    ValidityCell,
    write_quant_frontier_artifacts,
)
from harness.contracts.quant_frontier import MIN_TRANSCRIPTS, check_quant_frontier_inputs
from harness.registry import PHASE_REGISTRY, PhaseQuantFrontier, load_seed
from harness.sanity.quant_frontier import (
    check_degenerate_cell_is_nan_not_silent,
    check_shuffled_gold_collapses_icc,
    make_validity_fixture,
)

SEED = load_seed()
_GB = 1000**3


# --- registration ---------------------------------------------------------------------------------
def test_phase_registered() -> None:
    assert "phase_quant_frontier" in PHASE_REGISTRY
    assert PHASE_REGISTRY["phase_quant_frontier"] is PhaseQuantFrontier


# --- negative controls ----------------------------------------------------------------------------
def test_shuffled_gold_collapses_icc() -> None:
    m = check_shuffled_gold_collapses_icc(seed=SEED)
    assert m["true_icc"] >= 0.6
    assert m["shuffled_icc"] <= 0.3


def test_degenerate_cell_is_nan_not_silent() -> None:
    out = check_degenerate_cell_is_nan_not_silent(seed=SEED)
    assert out["degenerate_icc_is_nan"] is True


def test_validity_fixture_is_genuinely_valid() -> None:
    from aivmt.quant import validity_icc

    system, gold = make_validity_fixture(seed=SEED)
    icc2_1, _, degenerate = validity_icc(system, gold)
    assert degenerate is False
    assert icc2_1 >= 0.6


# --- real-shaped artifact helper ------------------------------------------------------------------
def _real_shaped_cells() -> list[QuantCell]:
    """A hand-built real-SHAPED frontier (descending validity as quant tightens) for contract paths."""

    def cell(label: str, icc1: float, icc_k: float, mem_gb: float, disk_gb: float) -> QuantCell:
        return QuantCell(
            model_tag=f"qwen2.5:7b-{label}", label=label, seed=SEED, n_transcripts=30,
            variant="zero_shot",
            validity=ValidityCell(icc1, icc_k, 30, 0.99, 0.0, False),
            latency=LatencyStats(30, 1.2, 2.1, 1.35, None),
            memory=MemoryUsage(f"qwen2.5:7b-{label}", int(mem_gb * _GB), f"{mem_gb} GB", "100% GPU", 8192),
            disk=DiskUsage(f"qwen2.5:7b-{label}", int(disk_gb * _GB), f"{disk_gb} GB"),
        )

    return [
        cell("fp16", 0.82, 0.90, 16.0, 15.0),
        cell("q8_0", 0.80, 0.89, 9.0, 8.1),
        cell("q4_K_M", 0.74, 0.85, 6.0, 4.7),
        cell("q3_K_M", 0.61, 0.76, 5.0, 3.8),
    ]


# --- benchmark / evidence-table integration -------------------------------------------------------
def test_benchmark_pending_when_no_artifact(tmp_path, monkeypatch) -> None:
    """Without the batch artifact, benchmark reports the seeded fixture cross-check (reproducible)."""
    phase = PhaseQuantFrontier()
    monkeypatch.setattr(phase, "inputs", [tmp_path / "absent" / "quant_frontier.json"])
    out = phase.benchmark()
    assert out["status"] == "PENDING_REAL_DATA"
    assert out["fixture_true_icc"] >= 0.6
    assert out["fixture_shuffled_icc"] <= 0.3


def test_benchmark_computed_with_artifact(tmp_path, monkeypatch) -> None:
    json_path, _ = write_quant_frontier_artifacts(_real_shaped_cells(), tmp_path / "phase_quant_frontier")
    phase = PhaseQuantFrontier()
    monkeypatch.setattr(phase, "inputs", [json_path])
    monkeypatch.setattr(phase, "outputs", [json_path])
    out = phase.benchmark()
    assert out["status"] == "COMPUTED"
    loaded = phase.run()
    assert loaded["cells"][0]["model_tag"] == "qwen2.5:7b-fp16"


# --- contract -------------------------------------------------------------------------------------
def test_contract_accepts_real_shaped_frontier(tmp_path) -> None:
    json_path, _ = write_quant_frontier_artifacts(_real_shaped_cells(), tmp_path)
    check_quant_frontier_inputs(json_path)  # must not raise


def test_contract_rejects_too_few_transcripts(tmp_path) -> None:
    bad = [{
        "model_tag": "m", "label": "q4", "seed": 42, "n_transcripts": MIN_TRANSCRIPTS - 1,
        "variant": "zero_shot",
        "validity": {"icc2_1": 0.8, "icc2_k": 0.9, "n_scored": 1,
                     "parse_success_rate": 1.0, "refusal_rate": 0.0, "degenerate": False},
        "latency": {"n": 1, "median_s": 1.0, "p90_s": 1.0, "mean_s": 1.0, "tokens_per_s": None},
        "memory": {"model_tag": "m", "size_bytes": _GB, "size_display": "1 GB",
                   "processor": "100% GPU", "context": 8192},
        "disk": {"model_tag": "m", "size_bytes": _GB, "size_display": "1 GB"},
    }]
    p = tmp_path / "quant_frontier.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(AssertionError, match="transcripts"):
        check_quant_frontier_inputs(p)


def test_contract_rejects_nan_in_non_degenerate_cell(tmp_path) -> None:
    """A non-degenerate cell carrying a nan ICC is a silent number -> reject. (A finite sibling cell
    keeps the artifact past the uniform-degenerate guard so the per-cell check is what fires.)"""
    json_path, _ = write_quant_frontier_artifacts(_real_shaped_cells()[:1], tmp_path / "a")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    bad = json.loads(json.dumps(data[0]))  # deep copy of a valid cell
    bad["model_tag"], bad["label"] = "m", "q4"
    bad["validity"]["icc2_1"] = float("nan")  # nan but NOT flagged degenerate -> silent number
    data.append(bad)
    p = tmp_path / "quant_frontier.json"
    p.write_text(json.dumps(data), encoding="utf-8")  # json.dumps emits NaN by default
    with pytest.raises(AssertionError, match="no silent number"):
        check_quant_frontier_inputs(p)


def test_contract_rejects_p90_below_median(tmp_path) -> None:
    bad = [{
        "model_tag": "m", "label": "q4", "seed": 42, "n_transcripts": 30, "variant": "zero_shot",
        "validity": {"icc2_1": 0.8, "icc2_k": 0.9, "n_scored": 30,
                     "parse_success_rate": 1.0, "refusal_rate": 0.0, "degenerate": False},
        "latency": {"n": 30, "median_s": 2.0, "p90_s": 1.0, "mean_s": 1.5, "tokens_per_s": None},
        "memory": {"model_tag": "m", "size_bytes": _GB, "size_display": "1 GB",
                   "processor": "100% GPU", "context": 8192},
        "disk": {"model_tag": "m", "size_bytes": _GB, "size_display": "1 GB"},
    }]
    p = tmp_path / "quant_frontier.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(AssertionError, match="p90"):
        check_quant_frontier_inputs(p)


def test_contract_rejects_missing_memory_footprint(tmp_path) -> None:
    bad = [{
        "model_tag": "m", "label": "q4", "seed": 42, "n_transcripts": 30, "variant": "zero_shot",
        "validity": {"icc2_1": 0.8, "icc2_k": 0.9, "n_scored": 30,
                     "parse_success_rate": 1.0, "refusal_rate": 0.0, "degenerate": False},
        "latency": {"n": 30, "median_s": 1.0, "p90_s": 1.2, "mean_s": 1.1, "tokens_per_s": None},
        "memory": None,
        "disk": {"model_tag": "m", "size_bytes": _GB, "size_display": "1 GB"},
    }]
    p = tmp_path / "quant_frontier.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(AssertionError, match="memory footprint missing"):
        check_quant_frontier_inputs(p)


def test_contract_rejects_uniformly_degenerate_mock_artifact(tmp_path) -> None:
    """Every cell degenerate / ICC ~0 is the constant-mock signature -> reject (no-silent-fallback)."""
    mock = [{
        "model_tag": "mockA", "label": "mock", "seed": 42, "n_transcripts": 30, "variant": "zero_shot",
        "validity": {"icc2_1": float("nan"), "icc2_k": float("nan"), "n_scored": 30,
                     "parse_success_rate": 1.0, "refusal_rate": 0.0, "degenerate": True},
        "latency": {"n": 30, "median_s": 0.5, "p90_s": 0.6, "mean_s": 0.5, "tokens_per_s": None},
        "memory": {"model_tag": "mockA", "size_bytes": _GB, "size_display": "1 GB",
                   "processor": "mock", "context": None},
        "disk": {"model_tag": "mockA", "size_bytes": _GB, "size_display": "1 GB"},
    }]
    p = tmp_path / "quant_frontier.json"
    p.write_text(json.dumps(mock), encoding="utf-8")
    with pytest.raises(AssertionError, match="uniformly degenerate"):
        check_quant_frontier_inputs(p)


def test_contract_accepts_frontier_with_one_degenerate_cell(tmp_path) -> None:
    """A single over-quantized cell collapsing to nan is legitimate; only UNIFORM collapse is rejected."""
    cells = _real_shaped_cells()
    json_path, _ = write_quant_frontier_artifacts(cells, tmp_path / "a")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    # Force the tightest-quant cell degenerate (the believable failure mode at q3).
    data[-1]["validity"]["degenerate"] = True
    data[-1]["validity"]["icc2_1"] = float("nan")
    data[-1]["validity"]["icc2_k"] = float("nan")
    p = tmp_path / "quant_frontier.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    check_quant_frontier_inputs(p)  # must not raise


def test_icc_range_check_tolerates_float_epsilon_above_one() -> None:
    """Regression (mirrors phase_robustness): deterministic rescoring can land the ANOVA ICC an
    epsilon above 1.0; the contract must tolerate it but still reject real out-of-range values."""
    from harness.contracts.quant_frontier import _check_icc_value

    _check_icc_value(1.0000000000000007, "cell", allow_nan=False)  # must not raise
    _check_icc_value(-1.0000000000000007, "cell", allow_nan=False)  # must not raise
    with pytest.raises(AssertionError, match="outside"):
        _check_icc_value(1.0 + 1e-6, "cell", allow_nan=False)
