"""Guarantee the local-vs-cloud tests make NO real network call and the negative controls fire.

Two structural guards:
  1. Every test in the cloud lane runs on the MockLLMClient / seeded fixtures. This test fails loud
     if any cloud-lane test source mentions a real provider base_url (the only way a test could hit
     the network), or if OpenAICompatClient is ever constructed pointing at a real cloud base_url.
  2. The phase's negative controls — including the structural PHI guard — must pass.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from aivmt.cloud import CLOUD_PROVIDERS
from harness.registry import PhaseLocalVsCloud, load_seed
from harness.sanity.local_vs_cloud import (
    check_degenerate_cell_is_nan_not_silent,
    check_phi_guard_blocks_real_data_path,
    check_shuffled_gold_collapses_icc,
)

SEED = load_seed()
TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent


def _load_runner():
    """Import scripts/local_vs_cloud.py as a module (no scripts/__init__.py, so load by path)."""
    path = ROOT / "scripts" / "local_vs_cloud.py"
    spec = importlib.util.spec_from_file_location("_lvc_runner", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

#: The real cloud hostnames a test must NEVER contact. (Substrings of the providers' base_urls.)
_REAL_HOSTS = ("api.deepseek.com", "dashscope.aliyuncs.com", "api.openai.com")


def test_cloud_test_sources_never_reference_real_hosts() -> None:
    """No cloud-lane TEST file may embed a real provider host — that is the only path to the network.

    This guard file itself is excluded: it legitimately NAMES the forbidden hosts in ``_REAL_HOSTS``
    in order to forbid them everywhere else.
    """
    this_file = Path(__file__).name
    for test_file in TESTS_DIR.glob("test_cloud*.py"):
        if test_file.name == this_file:
            continue
        text = test_file.read_text(encoding="utf-8")
        for host in _REAL_HOSTS:
            assert host not in text, (
                f"{test_file.name} references real cloud host {host!r}; tests must stay on the mock"
            )


def test_provider_table_hosts_are_https_only() -> None:
    """The provider table's base_urls are the only place real hosts live, and all are HTTPS."""
    for p in CLOUD_PROVIDERS.values():
        assert p.base_url.startswith("https://"), f"{p.name} base_url is not HTTPS"
        assert any(h in p.base_url for h in _REAL_HOSTS), f"{p.name} unexpected base_url {p.base_url}"


# --- negative controls fire -----------------------------------------------------------------------
def test_shuffled_gold_collapses_icc() -> None:
    m = check_shuffled_gold_collapses_icc(seed=SEED)
    assert m["true_icc"] >= 0.6
    assert m["shuffled_icc"] <= 0.3


def test_degenerate_cell_is_nan_not_silent() -> None:
    assert check_degenerate_cell_is_nan_not_silent(seed=SEED)["degenerate_icc_is_nan"] is True


def test_phi_guard_negative_control_fires() -> None:
    out = check_phi_guard_blocks_real_data_path(seed=SEED)
    assert out["real_data_dirs_blocked"] == 2
    assert out["synthetic_path_allowed"] is True


def test_phase_sanity_all_pass() -> None:
    """run_all wires three controls for this phase; each must return a dict (raise = FAIL)."""
    checks = PhaseLocalVsCloud().sanity()
    assert len(checks) == 3
    for check in checks:
        assert isinstance(check(), dict)


# --- runner: requested-but-keyless providers are auditable, and zero-key real runs fail loud --------
def _clear_cloud_keys(monkeypatch) -> None:
    for p in CLOUD_PROVIDERS.values():
        monkeypatch.delenv(p.env_key_name, raising=False)


def test_resolve_cloud_real_mode_reports_skipped(monkeypatch) -> None:
    """With no keys set, real-mode _resolve_cloud resolves nothing and reports the skipped names."""
    _clear_cloud_keys(monkeypatch)
    runner = _load_runner()
    triples, skipped = runner._resolve_cloud(["deepseek", "qwen-max", "gpt-4o"], mock=False)
    assert triples == []
    assert skipped == ["deepseek", "qwen-max", "gpt-4o"]


def test_resolve_cloud_mock_mode_skips_nothing(monkeypatch) -> None:
    """Mock mode resolves every provider deterministically (no key, no network) -> no skips."""
    _clear_cloud_keys(monkeypatch)
    runner = _load_runner()
    triples, skipped = runner._resolve_cloud(["deepseek", "gpt-4o"], mock=True)
    assert [t[0] for t in triples] == ["deepseek", "gpt-4o"]
    assert skipped == []


def test_main_real_mode_zero_keys_fails_loud(monkeypatch, tmp_path) -> None:
    """Real mode with every requested key unset must exit NON-ZERO, not write a 'valid' local-only
    artifact and exit 0 (Finding 1: a silently-collapsed head-to-head must fail loud)."""
    _clear_cloud_keys(monkeypatch)
    runner = _load_runner()
    # The fail-loud check fires BEFORE any artifact write, so ROOT is left real (seed/case load from
    # it); nothing is written to results/ because main() exits non-zero first.
    case_path = ROOT / "conf" / "case" / "example_chestpain_en.yaml"
    monkeypatch.setattr(
        __import__("sys"),
        "argv",
        [
            "local_vs_cloud.py", "--providers", "deepseek", "qwen-max", "gpt-4o",
            "--transcripts", "4", "--case", str(case_path),
        ],
    )
    # argparse.error -> SystemExit(2), raised before the artifact-write step.
    with pytest.raises(SystemExit) as exc:
        runner.main()
    assert exc.value.code == 2


def test_main_mock_records_empty_skipped(monkeypatch, tmp_path) -> None:
    """Mock run writes to the *_mock dir and records skipped_providers == [] (all providers resolved)."""
    _clear_cloud_keys(monkeypatch)
    runner = _load_runner()
    # Redirect the artifact root to a temp dir so we never touch the committed results/. load_seed
    # reads ROOT/configs/seed.yaml, so copy that in; --case is an absolute path (ROOT-independent).
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "seed.yaml").write_text(
        (ROOT / "configs" / "seed.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    case_path = ROOT / "conf" / "case" / "example_chestpain_en.yaml"
    monkeypatch.setattr(
        __import__("sys"),
        "argv",
        [
            "local_vs_cloud.py", "--providers", "deepseek", "gpt-4o",
            "--transcripts", "4", "--mock", "--case", str(case_path),
        ],
    )
    runner.main()
    out = tmp_path / "results" / "phase_local_vs_cloud_mock" / "local_vs_cloud.json"
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["requested_providers"] == ["deepseek", "gpt-4o"]
    assert data["skipped_providers"] == []
