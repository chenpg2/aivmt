"""Quantization-frontier analysis for SQ3 (edge-deployability axis of the validity-cost frontier).

Answers, for an LMIC dean: "how small/cheap a model still scores at acceptable validity?" — a 2-D
surface over (model size x quant level) reporting, per cell:
  - ICC(2,1)/ICC(2,k)-vs-gold over the SAME designed-quality synthetic golded set the robustness lane
    uses (so the two lanes are directly comparable), plus JSON-parse / refusal robustness;
  - per-encounter latency (median + p90, optional tokens/s);
  - loaded RAM/VRAM parsed from ``ollama ps``; and
  - on-disk model size parsed from ``ollama list``.

Every number flows through the registered ``phase_quant_frontier`` harness phase (contract +
negative controls) so the manuscript figures are reproducible from ``configs/seed.yaml``. Degenerate
variance yields an explicit ``nan`` (flagged), never a silent number (AI4S no-silent-fallback).
"""

from __future__ import annotations

from .metering import MeteredClient
from .metrics import latency_stats, validity_cell, validity_icc
from .ollama_probe import (
    OllamaProbeError,
    parse_ollama_list,
    parse_ollama_ps,
    parse_size,
    probe_disk_size,
    probe_loaded_memory,
)
from .report import render_markdown, write_quant_frontier_artifacts
from .runner import DiskProbe, MemoryProbe, run_quant_cell
from .types import DiskUsage, LatencyStats, MemoryUsage, QuantCell, ValidityCell

__all__ = [
    # types
    "ValidityCell",
    "LatencyStats",
    "MemoryUsage",
    "DiskUsage",
    "QuantCell",
    # metrics
    "validity_icc",
    "validity_cell",
    "latency_stats",
    # metering
    "MeteredClient",
    # ollama probes
    "OllamaProbeError",
    "parse_size",
    "parse_ollama_list",
    "parse_ollama_ps",
    "probe_disk_size",
    "probe_loaded_memory",
    # runner
    "run_quant_cell",
    "MemoryProbe",
    "DiskProbe",
    # report
    "render_markdown",
    "write_quant_frontier_artifacts",
]
