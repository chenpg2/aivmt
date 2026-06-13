"""Unit tests for the quant lane's measurement primitives (deterministic, mock/shim only).

Covers: the ``ollama ps`` / ``ollama list`` parsers against CAPTURED sample CLI output (no shelling
out), the validity-ICC + latency-stats math, the token-metering wrapper with and without an exposed
``usage`` block, and the end-to-end cell runner with injected fake probes. No real model or
subprocess is touched."""

from __future__ import annotations

import math

import numpy as np
import pytest

from aivmt.llm.mock import MockLLMClient
from aivmt.quant import (
    MeteredClient,
    OllamaProbeError,
    latency_stats,
    parse_ollama_list,
    parse_ollama_ps,
    parse_size,
    run_quant_cell,
    validity_cell,
    validity_icc,
)
from aivmt.quant.types import DiskUsage, MemoryUsage
from aivmt.robustness import build_golded_dataset

# --- CAPTURED sample CLI output (real `ollama list` / `ollama ps` on the dev box, 2026-06-13) ------
# Embedded as fixtures so the parsers are tested WITHOUT shelling out to ollama.
LIST_SAMPLE = """NAME                                              ID              SIZE      MODIFIED
huatuogpt-o1:8b                                   6f0662e4c74b    4.9 GB    8 hours ago
hf.co/QuantFactory/HuatuoGPT-o1-8B-GGUF:Q4_K_M    6f0662e4c74b    4.9 GB    8 hours ago
qwen2.5:14b                                       7cdf5a0187d5    9.0 GB    2 days ago
llama3.1:8b                                       46e0c10c039e    4.9 GB    2 days ago
qwen2.5:7b                                        845dbda0ea48    4.7 GB    2 days ago
qwen2.5:3b                                        357c53fb659c    1.9 GB    2 days ago
mxbai-embed-large:latest                          468836162de7    669 MB    9 months ago
gpt-oss:20b                                       f2b8351c629c    13 GB     10 months ago
"""

PS_SAMPLE = """NAME           ID              SIZE     PROCESSOR    CONTEXT    UNTIL
qwen2.5:14b    7cdf5a0187d5    15 GB    100% GPU     32768      57 minutes from now
llama3.1:8b    46e0c10c039e    22 GB    100% GPU     131072     56 seconds from now
"""

_GB = 1000**3
_MB = 1000**2


# --- parse_size -----------------------------------------------------------------------------------
def test_parse_size_gb_with_decimal() -> None:
    by, disp = parse_size("4.7 GB")
    assert by == int(round(4.7 * _GB))
    assert disp == "4.7 GB"


def test_parse_size_mb_and_integer_gb() -> None:
    assert parse_size("669 MB")[0] == 669 * _MB
    assert parse_size("13 GB")[0] == 13 * _GB


def test_parse_size_rejects_garbage() -> None:
    with pytest.raises(OllamaProbeError, match="unparseable size"):
        parse_size("not-a-size")


# --- parse_ollama_list ----------------------------------------------------------------------------
def test_parse_list_disk_size() -> None:
    disk = parse_ollama_list(LIST_SAMPLE, "qwen2.5:7b")
    assert disk.model_tag == "qwen2.5:7b"
    assert disk.size_bytes == int(round(4.7 * _GB))
    assert disk.size_display == "4.7 GB"


def test_parse_list_integer_gb_tag() -> None:
    assert parse_ollama_list(LIST_SAMPLE, "gpt-oss:20b").size_bytes == 13 * _GB


def test_parse_list_handles_slash_and_colon_in_name() -> None:
    """A HF-style tag with slashes/colons in the NAME column must still match exactly."""
    disk = parse_ollama_list(LIST_SAMPLE, "hf.co/QuantFactory/HuatuoGPT-o1-8B-GGUF:Q4_K_M")
    assert disk.size_bytes == int(round(4.9 * _GB))


def test_parse_list_missing_tag_fails_loud() -> None:
    with pytest.raises(OllamaProbeError, match="not found in 'ollama list'"):
        parse_ollama_list(LIST_SAMPLE, "qwen2.5:0.5b-instruct-q3_K_M")


# --- parse_ollama_ps ------------------------------------------------------------------------------
def test_parse_ps_memory_processor_and_context() -> None:
    mem = parse_ollama_ps(PS_SAMPLE, "qwen2.5:14b")
    assert mem.size_bytes == 15 * _GB
    assert mem.size_display == "15 GB"
    assert mem.processor == "100% GPU"
    assert mem.context == 32768


def test_parse_ps_second_row() -> None:
    mem = parse_ollama_ps(PS_SAMPLE, "llama3.1:8b")
    assert mem.size_bytes == 22 * _GB
    assert mem.context == 131072


def test_parse_ps_not_loaded_fails_loud() -> None:
    """A model present on disk but NOT in `ollama ps` is not loaded -> cannot measure memory."""
    with pytest.raises(OllamaProbeError, match="not loaded"):
        parse_ollama_ps(PS_SAMPLE, "qwen2.5:7b")


# --- validity ICC ---------------------------------------------------------------------------------
def test_validity_icc_high_when_correlated() -> None:
    rng = np.random.default_rng(0)
    gold = rng.uniform(0.1, 0.9, 20)
    system = np.clip(gold + rng.normal(0, 0.03, 20), 0, 1)
    icc2_1, icc2_k, degenerate = validity_icc(system.tolist(), gold.tolist())
    assert degenerate is False
    assert icc2_1 >= 0.6
    assert icc2_k >= icc2_1  # average-measure ICC is >= single-measure


def test_validity_icc_degenerate_is_nan() -> None:
    icc2_1, icc2_k, degenerate = validity_icc([0.5, 0.5, 0.5, 0.5], [0.1, 0.2, 0.3, 0.4])
    assert degenerate is True
    assert math.isnan(icc2_1) and math.isnan(icc2_k)


def test_validity_icc_requires_two() -> None:
    with pytest.raises(ValueError, match=">=2"):
        validity_icc([0.5], [0.5])


def test_validity_cell_rates() -> None:
    cell = validity_cell(
        [0.2, 0.5, 0.8], [0.25, 0.5, 0.75],
        n_calls=9, n_parse_failures=0, n_refusals=0,
    )
    assert cell.n_scored == 3
    assert cell.parse_success_rate == 1.0
    assert cell.refusal_rate == 0.0
    assert cell.degenerate is False


# --- latency stats --------------------------------------------------------------------------------
def test_latency_stats_orders_p90_ge_median() -> None:
    lat = latency_stats([1.0, 1.0, 1.0, 1.0, 10.0])
    assert lat.n == 5
    assert lat.median_s == 1.0
    assert lat.p90_s >= lat.median_s
    assert lat.tokens_per_s is None  # no tokens supplied


def test_latency_stats_tokens_per_second() -> None:
    lat = latency_stats([1.0, 1.0], total_tokens=300)
    assert lat.tokens_per_s == pytest.approx(150.0)  # 300 tokens / 2.0 s


def test_latency_stats_empty_fails_loud() -> None:
    with pytest.raises(ValueError, match="at least one"):
        latency_stats([])


# --- metering -------------------------------------------------------------------------------------
class _UsageMock(MockLLMClient):
    """Mock that exposes a `last_usage` block after each call (an Ollama-with-usage style client)."""

    def __init__(self, tokens_per_call: int = 50) -> None:
        super().__init__(model_id="usage-mock")
        self._tpc = tokens_per_call
        self.last_usage: dict | None = None

    def complete_json(self, system: str, user: str, *, task: str) -> dict:
        out = super().complete_json(system, user, task=task)
        self.last_usage = {"total_tokens": self._tpc}
        return out


def test_metered_client_accumulates_tokens_when_exposed() -> None:
    metered = MeteredClient(_UsageMock(tokens_per_call=40))
    metered.complete_json("s", "u", task="checklist")
    metered.complete_json("s", "u", task="segue")
    assert metered.total_tokens == 80
    assert metered.inner.n_calls == 2


def test_metered_client_tokens_none_when_no_usage() -> None:
    """The stock client never exposes usage -> tokens stay None (honest, not fabricated)."""
    metered = MeteredClient(MockLLMClient())
    metered.complete_json("s", "u", task="checklist")
    assert metered.total_tokens is None


# --- end-to-end cell runner (mock LLM + injected fake probes) --------------------------------------
def _fake_memory(tag: str) -> MemoryUsage:
    return MemoryUsage(tag, 4 * _GB, "4 GB", "100% GPU", 8192)


def _fake_disk(tag: str) -> DiskUsage:
    return DiskUsage(tag, 4 * _GB, "4 GB")


def test_run_quant_cell_with_quality_mock(tmp_path) -> None:
    """End-to-end cell on the controllable QualityMock + injected probes: validity is non-degenerate,
    latency is populated, and the memory/disk footprints come from the injected fakes (no subprocess)."""
    from tests.test_robustness import QualityMock, _CASE

    dataset = build_golded_dataset(_CASE, 8)
    cell = run_quant_cell(
        "quality-mock", "qmock", _CASE, dataset, QualityMock(),
        seed=42, probe_memory=_fake_memory, probe_disk=_fake_disk,
    )
    assert cell.model_tag == "quality-mock"
    assert cell.label == "qmock"
    assert cell.n_transcripts == 8
    assert cell.validity.degenerate is False
    assert not math.isnan(cell.validity.icc2_1)
    assert cell.latency.n == 8
    assert cell.latency.p90_s >= cell.latency.median_s
    assert cell.memory is not None and cell.memory.size_bytes == 4 * _GB
    assert cell.disk is not None and cell.disk.size_bytes == 4 * _GB


def test_run_quant_cell_constant_mock_is_degenerate() -> None:
    """The stock constant mock cannot discriminate -> the cell is degenerate with nan ICC (flagged)."""
    from tests.test_robustness import _CASE

    dataset = build_golded_dataset(_CASE, 6)
    cell = run_quant_cell(
        "mock", "mock", _CASE, dataset, MockLLMClient(),
        seed=42, probe_memory=_fake_memory, probe_disk=_fake_disk,
    )
    assert cell.validity.degenerate is True
    assert math.isnan(cell.validity.icc2_1)


def test_run_quant_cell_requires_two_transcripts() -> None:
    from tests.test_robustness import _CASE

    dataset = build_golded_dataset(_CASE, 2)[:1]
    with pytest.raises(ValueError, match=">=2 transcripts"):
        run_quant_cell(
            "mock", "mock", _CASE, dataset, MockLLMClient(),
            seed=42, probe_memory=_fake_memory, probe_disk=_fake_disk,
        )


def test_run_quant_cell_probe_failure_propagates() -> None:
    """A fail-loud probe (model not loaded) must sink the cell, not be silently swallowed."""
    from tests.test_robustness import QualityMock, _CASE

    def _boom(tag: str) -> MemoryUsage:
        raise OllamaProbeError(f"{tag} not loaded")

    dataset = build_golded_dataset(_CASE, 4)
    with pytest.raises(OllamaProbeError, match="not loaded"):
        run_quant_cell(
            "quality-mock", "qmock", _CASE, dataset, QualityMock(),
            seed=42, probe_memory=_boom, probe_disk=_fake_disk,
        )
