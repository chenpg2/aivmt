"""Local-vs-cloud lane: PHI guard, provider registry, per-domain scoring, compare logic, contract,
and phase wiring — ALL verified on the MOCK / seeded fixtures. No real network call is ever made
(the providers' real base_urls never appear; see test_cloud_no_network.py for the guard test).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from aivmt.cases import load_case
from aivmt.cloud import (
    CLOUD_PROVIDERS,
    CloudSafeDataset,
    MissingApiKeyError,
    PhiLeakError,
    assert_dataset_cloud_safe,
    assert_path_is_offdevice_safe,
    build_cloud_client,
    compare_local_vs_cloud,
    deidentified_cloud_dataset,
    resolve_provider,
    score_provider_cell,
    score_with_domains,
    synthetic_cloud_dataset,
    write_local_vs_cloud_artifacts,
)
from aivmt.cloud.provenance import REAL_DATA_DIRS
from aivmt.cloud.scoring import SEGUE_DOMAINS
from aivmt.llm.base import BaseLLMClient
from aivmt.llm.mock import MockLLMClient
from harness.contracts.local_vs_cloud import check_local_vs_cloud_inputs
from harness.registry import PHASE_REGISTRY, PhaseLocalVsCloud, load_seed

SEED = load_seed()
ROOT = Path(__file__).resolve().parents[1]
CASE = load_case(ROOT / "conf" / "case" / "example_chestpain_en.yaml")


# --- a fixture client that produces gold-tracking, VARYING scores (so ICC is non-degenerate) -------
class _GoldTrackingClient(BaseLLMClient):
    """Mock client whose SEGUE/checklist/reasoning outputs scale with a per-transcript signal.

    The signal is derived from the transcript's encounter_id index so each encounter scores
    differently and tracks the designed gold — exercising the real scoring + ICC path end-to-end
    WITHOUT any network. Parse-failure counters mirror the production client interface.
    """

    def __init__(self, *, noise: float = 0.0, model_id: str = "fixture") -> None:
        self.model_id = model_id
        self.n_calls = 0
        self.n_parse_failures = 0
        self.n_refusals = 0
        self._noise = noise

    def _signal(self, user: str) -> float:
        # The synthetic transcripts embed "(case i)"; map i -> a monotone quality in (0,1).
        idx = 0
        marker = "(case "
        if marker in user:
            try:
                idx = int(user.split(marker, 1)[1].split(")", 1)[0])
            except ValueError:
                idx = 0
        base = ((idx % 4) + 1) / 5.0  # 0.2, 0.4, 0.6, 0.8 cycling — tracks the graded tiers
        return max(0.0, min(1.0, base + self._noise * ((idx % 3) - 1) * 0.05))

    def complete_json(self, system: str, user: str, *, task: str) -> dict:
        self.n_calls += 1
        v = self._signal(user)
        if task == "checklist":
            n = max(1, round(v * 4))
            return {"covered": [f"q_{i}" for i in range(n)], "evidence": {}}
        if task == "segue":
            return {"domains": {d: v for d in SEGUE_DOMAINS}}
        if task == "reasoning":
            return {"score": v, "rationale": "fixture"}
        return {}

    def chat_text(self, system: str, messages: list[dict]) -> str:
        self.n_calls += 1
        return "fixture"


def _safe_dataset(n: int = 8) -> CloudSafeDataset:
    return synthetic_cloud_dataset(CASE, n)


# === PHI GUARD ====================================================================================
def test_phi_guard_blocks_real_transcript_dir() -> None:
    for real_dir in REAL_DATA_DIRS:
        p = ROOT / real_dir / "patient_001.json"
        with pytest.raises(PhiLeakError, match="real-data"):
            assert_path_is_offdevice_safe(p)


def test_phi_guard_blocks_actual_existing_real_transcript() -> None:
    """The repo's real-data dir literally contains SMOKE01.json — the guard must refuse its path."""
    real = ROOT / "data" / "transcripts" / "SMOKE01.json"
    with pytest.raises(PhiLeakError):
        assert_path_is_offdevice_safe(real)


def test_phi_guard_allows_synthetic_fixture_path(tmp_path) -> None:
    p = tmp_path / "synthetic_fixtures" / "case.json"
    assert assert_path_is_offdevice_safe(p) == p  # must not raise


def test_phi_guard_blocks_nested_real_data_path() -> None:
    p = ROOT / "data" / "encounters" / "site_a" / "enc_42.json"
    with pytest.raises(PhiLeakError):
        assert_path_is_offdevice_safe(p)


@pytest.mark.parametrize(
    "mixed",
    [
        Path("/Users/x/AIVMT/Data/Transcripts/p.json"),
        Path("/Users/x/AIVMT/DATA/ENCOUNTERS/site_a/enc.json"),
        Path("/Users/x/AIVMT/data/Transcripts/p.json"),
    ],
)
def test_phi_guard_blocks_mixed_case_real_data_path(mixed: Path) -> None:
    """Regression: on a case-INSENSITIVE filesystem (macOS default) a mixed-case real-data path
    resolves to the SAME real dir as its lowercase form, so the guard must refuse it too — a
    case-sensitive substring match would let `Data/Transcripts` slip past and leak PHI."""
    with pytest.raises(PhiLeakError, match="real-data"):
        assert_path_is_offdevice_safe(mixed)


def test_compare_refuses_raw_transcript_list() -> None:
    """A bare list (which could originate from real data) must be refused by the cloud path."""
    raw = list(synthetic_cloud_dataset(CASE, 4).transcripts)  # a plain list, NOT CloudSafeDataset
    with pytest.raises(PhiLeakError, match="CloudSafeDataset"):
        assert_dataset_cloud_safe(raw)


def test_cloudsafe_dataset_rejects_non_safe_provenance() -> None:
    with pytest.raises(PhiLeakError, match="not cloud-safe"):
        CloudSafeDataset(provenance="real_phi", transcripts=tuple(_safe_dataset(2).transcripts))


def test_deidentified_constructor_is_cloud_safe() -> None:
    ds = deidentified_cloud_dataset(_safe_dataset(4).transcripts, source="deid-upstream")
    assert assert_dataset_cloud_safe(ds).provenance == "deidentified"


# === PROVIDER REGISTRY ============================================================================
def test_default_providers_present() -> None:
    assert set(CLOUD_PROVIDERS) == {"deepseek", "qwen-max", "gpt-4o"}
    assert CLOUD_PROVIDERS["deepseek"].env_key_name == "DEEPSEEK_API_KEY"
    assert CLOUD_PROVIDERS["qwen-max"].base_url.startswith("https://dashscope")
    assert CLOUD_PROVIDERS["gpt-4o"].model_id == "gpt-4o"


def test_build_cloud_client_fails_loud_without_key(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(MissingApiKeyError, match="DEEPSEEK_API_KEY"):
        build_cloud_client(resolve_provider("deepseek"))


def test_unknown_provider_raises() -> None:
    with pytest.raises(KeyError, match="claude"):
        resolve_provider("claude")


def test_has_key_reflects_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert CLOUD_PROVIDERS["gpt-4o"].has_key()
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    assert not CLOUD_PROVIDERS["gpt-4o"].has_key()


# === PER-DOMAIN SCORING (on the mock) =============================================================
def test_score_with_domains_returns_all_segue_domains() -> None:
    ds = synthetic_cloud_dataset(CASE, 2)
    transcript, _ = ds.transcripts[0]
    out = score_with_domains(CASE, transcript, MockLLMClient())
    assert set(out.segue) == set(SEGUE_DOMAINS)
    assert 0.0 <= out.overall <= 1.0


# === COMPARE LOGIC (fixture client, non-degenerate) ===============================================
def test_compare_produces_overall_and_domain_deltas() -> None:
    ds = _safe_dataset(8)
    local = _GoldTrackingClient(model_id="llama3.1:8b")
    cloud = [
        ("deepseek", "deepseek-chat", _GoldTrackingClient(model_id="deepseek-chat")),
        ("gpt-4o", "gpt-4o", _GoldTrackingClient(noise=1.0, model_id="gpt-4o")),
    ]
    comp = compare_local_vs_cloud(CASE, ds, "llama3.1:8b", local, cloud, seed=SEED)

    assert comp.provenance == "synthetic"
    assert comp.non_inferiority_margin == 0.10
    assert not comp.local.overall_degenerate
    assert comp.local.overall_icc2_1 > 0.0  # tracks gold (positive agreement, non-degenerate)
    # The SEGUE domains carry the clean gold signal -> high domain-level ICC (the load-bearing claim).
    assert comp.local.domain_icc("elicit_information") >= 0.6
    assert len(comp.cloud) == 2
    assert {d.cloud_provider for d in comp.deltas} == {"deepseek", "gpt-4o"}
    for d in comp.deltas:
        assert set(d.delta_by_domain) == set(SEGUE_DOMAINS)
        assert math.isfinite(d.delta_overall)
    # local and the noiseless deepseek score identically -> overall delta ~0 (non-inferior).
    deepseek_delta = next(d for d in comp.deltas if d.cloud_provider == "deepseek")
    assert abs(deepseek_delta.delta_overall) < 1e-9


def test_compare_with_zero_cloud_providers_writes_local_only() -> None:
    ds = _safe_dataset(6)
    comp = compare_local_vs_cloud(
        CASE, ds, "llama3.1:8b", _GoldTrackingClient(), [], seed=SEED
    )
    assert comp.cloud == ()
    assert comp.deltas == ()
    assert comp.local.role == "local"


def test_compare_records_requested_and_skipped_providers() -> None:
    """A partial head-to-head (2 of 3 keys missing) must be auditable in the artifact, not log-only.

    The runner would request all 3 providers but only resolve a client for deepseek; the other two
    are recorded in ``skipped_providers`` so a JSON reader can tell this apart from a 1-provider
    request."""
    ds = _safe_dataset(8)
    local = _GoldTrackingClient(model_id="llama3.1:8b")
    cloud = [("deepseek", "deepseek-chat", _GoldTrackingClient(model_id="deepseek-chat"))]
    comp = compare_local_vs_cloud(
        CASE, ds, "llama3.1:8b", local, cloud, seed=SEED,
        requested_providers=["deepseek", "qwen-max", "gpt-4o"],
        skipped_providers=["qwen-max", "gpt-4o"],
    )
    assert comp.requested_providers == ("deepseek", "qwen-max", "gpt-4o")
    assert comp.skipped_providers == ("qwen-max", "gpt-4o")
    assert {c.provider for c in comp.cloud} == {"deepseek"}
    # The serialized JSON carries the bookkeeping — distinguishable from a deliberately-narrow 1-way
    # request (json arrays, regardless of the in-memory tuple representation).
    d = json.loads(json.dumps(comp.to_dict()))
    assert d["requested_providers"] == ["deepseek", "qwen-max", "gpt-4o"]
    assert d["skipped_providers"] == ["qwen-max", "gpt-4o"]


def test_compare_infers_skipped_from_requested_minus_scored() -> None:
    """When ``skipped_providers`` is not given, it is inferred as requested minus scored (order kept)."""
    ds = _safe_dataset(6)
    cloud = [("deepseek", "deepseek-chat", _GoldTrackingClient(model_id="deepseek-chat"))]
    comp = compare_local_vs_cloud(
        CASE, ds, "llama3.1:8b", _GoldTrackingClient(), cloud, seed=SEED,
        requested_providers=["deepseek", "gpt-4o"],
    )
    assert comp.skipped_providers == ("gpt-4o",)


def test_compare_defaults_requested_to_scored_when_unset() -> None:
    """With no requested set given, ``requested_providers`` defaults to the scored ones (no skips)."""
    ds = _safe_dataset(6)
    cloud = [("deepseek", "deepseek-chat", _GoldTrackingClient(model_id="deepseek-chat"))]
    comp = compare_local_vs_cloud(CASE, ds, "llama3.1:8b", _GoldTrackingClient(), cloud, seed=SEED)
    assert comp.requested_providers == ("deepseek",)
    assert comp.skipped_providers == ()


def test_score_provider_cell_requires_two_parsed_encounters() -> None:
    ds = _safe_dataset(4)

    class _AlwaysFails(BaseLLMClient):
        model_id = "broken"
        n_calls = 0
        n_parse_failures = 0
        n_refusals = 0

        def complete_json(self, system: str, user: str, *, task: str) -> dict:
            from aivmt.llm.base import LLMOutputError

            self.n_calls += 1
            self.n_parse_failures += 1
            raise LLMOutputError("boom")

        def chat_text(self, system: str, messages: list[dict]) -> str:
            return ""

    with pytest.raises(ValueError, match="< 2"):
        score_provider_cell("broken", "cloud", "broken", CASE, ds, _AlwaysFails(), seed=SEED)


# === ARTIFACT + CONTRACT ==========================================================================
def _write_real_shaped(tmp_path: Path) -> Path:
    ds = _safe_dataset(8)
    local = _GoldTrackingClient(model_id="llama3.1:8b")
    cloud = [("deepseek", "deepseek-chat", _GoldTrackingClient(model_id="deepseek-chat"))]
    comp = compare_local_vs_cloud(CASE, ds, "llama3.1:8b", local, cloud, seed=SEED)
    json_path, _ = write_local_vs_cloud_artifacts(comp, tmp_path)
    return json_path


def test_contract_accepts_real_shaped_artifact(tmp_path) -> None:
    check_local_vs_cloud_inputs(_write_real_shaped(tmp_path))  # must not raise


def test_contract_rejects_non_safe_provenance(tmp_path) -> None:
    path = _write_real_shaped(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["provenance"] = "real_phi"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(AssertionError, match="off-device safe"):
        check_local_vs_cloud_inputs(path)


def test_contract_rejects_nan_in_non_degenerate_cell(tmp_path) -> None:
    path = _write_real_shaped(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["local"]["overall_icc2_1"] = float("nan")  # nan but NOT flagged degenerate
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(AssertionError, match="no silent number"):
        check_local_vs_cloud_inputs(path)


def test_contract_rejects_uniformly_degenerate_mock_artifact(tmp_path) -> None:
    """Every cell degenerate (the constant-mock signature) -> reject (no-silent-fallback)."""
    ds = _safe_dataset(6)
    # MockLLMClient returns CONSTANT scores -> every cell degenerate -> the mock-masquerade signature.
    comp = compare_local_vs_cloud(
        CASE, ds, "mock-local", MockLLMClient("mock-local"),
        [("deepseek", "mock", MockLLMClient("mock-cloud"))], seed=SEED,
    )
    json_path, _ = write_local_vs_cloud_artifacts(comp, tmp_path)
    with pytest.raises(AssertionError, match="uniformly degenerate"):
        check_local_vs_cloud_inputs(json_path)


def test_contract_accepts_partial_run_bookkeeping(tmp_path) -> None:
    """A partial run (scored deepseek; skipped qwen-max/gpt-4o) is a CONSISTENT, accepted artifact."""
    path = _write_real_shaped(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["requested_providers"] = ["deepseek", "qwen-max", "gpt-4o"]
    data["skipped_providers"] = ["qwen-max", "gpt-4o"]  # scored == {deepseek}
    path.write_text(json.dumps(data), encoding="utf-8")
    check_local_vs_cloud_inputs(path)  # must not raise


def test_contract_rejects_provider_both_scored_and_skipped(tmp_path) -> None:
    path = _write_real_shaped(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["requested_providers"] = ["deepseek"]
    data["skipped_providers"] = ["deepseek"]  # deepseek is ALSO a scored cloud cell -> contradiction
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(AssertionError, match="both scored and skipped"):
        check_local_vs_cloud_inputs(path)


def test_contract_rejects_scored_provider_not_in_requested(tmp_path) -> None:
    path = _write_real_shaped(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["requested_providers"] = ["qwen-max"]  # deepseek WAS scored but is not in requested
    data["skipped_providers"] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(AssertionError, match="not in requested set"):
        check_local_vs_cloud_inputs(path)


def test_contract_rejects_requested_not_covered_by_scored_or_skipped(tmp_path) -> None:
    path = _write_real_shaped(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    # requested gpt-4o but it is neither scored (only deepseek) nor skipped -> phantom request
    data["requested_providers"] = ["deepseek", "gpt-4o"]
    data["skipped_providers"] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(AssertionError, match="must be exactly one of scored/skipped"):
        check_local_vs_cloud_inputs(path)


def test_contract_backward_compatible_without_bookkeeping(tmp_path) -> None:
    """An older artifact with neither requested_providers nor skipped_providers still validates."""
    path = _write_real_shaped(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("requested_providers", None)
    data.pop("skipped_providers", None)
    path.write_text(json.dumps(data), encoding="utf-8")
    check_local_vs_cloud_inputs(path)  # must not raise


def test_contract_accepts_one_degenerate_cloud_cell(tmp_path) -> None:
    """A single collapsed cloud cell is legitimate (ECOSBot collapse); only UNIFORM collapse rejected."""
    path = _write_real_shaped(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    # Force the cloud cell degenerate; the local cell stays valid -> not uniform.
    cloud = data["cloud"][0]
    cloud["overall_degenerate"] = True
    cloud["overall_icc2_1"] = float("nan")
    cloud["overall_icc2_k"] = float("nan")
    for dom in cloud["domains"]:
        dom["degenerate"] = True
        dom["icc2_1"] = float("nan")
        dom["icc2_k"] = float("nan")
    # the delta vs this provider becomes nan (degenerate on one side) — allowed
    data["deltas"][0]["delta_overall"] = float("nan")
    data["deltas"][0]["delta_by_domain"] = {d: float("nan") for d in SEGUE_DOMAINS}
    path.write_text(json.dumps(data), encoding="utf-8")
    check_local_vs_cloud_inputs(path)  # must not raise


# === PHASE WIRING =================================================================================
def test_phase_registered() -> None:
    assert "phase_local_vs_cloud" in PHASE_REGISTRY
    assert PHASE_REGISTRY["phase_local_vs_cloud"] is PhaseLocalVsCloud


def test_benchmark_pending_when_no_artifact(tmp_path, monkeypatch) -> None:
    phase = PhaseLocalVsCloud()
    monkeypatch.setattr(phase, "inputs", [tmp_path / "absent" / "local_vs_cloud.json"])
    out = phase.benchmark()
    assert out["status"] == "PENDING_REAL_DATA"
    assert out["ni_margin"] == 0.10
    assert out["fixture_true_icc"] >= 0.6
    assert out["fixture_shuffled_icc"] <= 0.3


def test_benchmark_computed_with_artifact(tmp_path, monkeypatch) -> None:
    json_path = _write_real_shaped(tmp_path / "phase")
    phase = PhaseLocalVsCloud()
    monkeypatch.setattr(phase, "inputs", [json_path])
    monkeypatch.setattr(phase, "outputs", [json_path])
    out = phase.benchmark()
    assert out["status"] == "COMPUTED"
    loaded = phase.run()
    assert loaded["comparison"]["local_model"] == "llama3.1:8b"
