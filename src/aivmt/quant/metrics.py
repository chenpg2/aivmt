"""Pure measurement functions for the quantization-frontier lane.

Everything here is deterministic given its inputs and calls the metrics package read-only for ICC, so
the frontier numbers are reproducible from ``configs/seed.yaml``. No number is fabricated when
variance is degenerate: a constant system-score column yields an explicit ``nan`` + ``degenerate``
flag, mirroring the robustness / ASR lanes.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from ..metrics import icc
from .types import LatencyStats, ValidityCell


def validity_icc(sys_scores: Sequence[float], golds: Sequence[float]) -> tuple[float, float, bool]:
    """ICC(2,1) and ICC(2,k) between system scores and gold; ``(nan, nan, True)`` if degenerate.

    Degenerate <=> either column has no variance (the scorer cannot discriminate the encounters, or
    the gold is constant): ICC has no signal to attribute, so we flag it and return an explicit nan
    instead of a silently fabricated number.

    Raises:
        ValueError: if fewer than two encounters are supplied (ICC needs n>=2 targets).
    """
    if len(sys_scores) < 2 or len(golds) < 2:
        raise ValueError("validity_icc needs >=2 encounters (ICC requires n>=2 targets)")
    if len(sys_scores) != len(golds):
        raise ValueError(
            f"sys/gold length mismatch ({len(sys_scores)} != {len(golds)})"
        )
    arr = np.column_stack([np.asarray(sys_scores, dtype=float), np.asarray(golds, dtype=float)])
    if np.any(np.isclose(arr.std(axis=0), 0.0)):
        return float("nan"), float("nan"), True
    return float(icc(arr, "icc2_1")), float(icc(arr, "icc2_k")), False


def validity_cell(
    sys_scores: Sequence[float],
    golds: Sequence[float],
    *,
    n_calls: int,
    n_parse_failures: int,
    n_refusals: int,
) -> ValidityCell:
    """Assemble a :class:`ValidityCell` from the scored encounters and the client's call counters."""
    icc2_1, icc2_k, degenerate = validity_icc(sys_scores, golds)
    denom = max(n_calls, 1)
    return ValidityCell(
        icc2_1=icc2_1,
        icc2_k=icc2_k,
        n_scored=len(sys_scores),
        parse_success_rate=round(1.0 - n_parse_failures / denom, 4),
        refusal_rate=round(n_refusals / denom, 4),
        degenerate=degenerate,
    )


def latency_stats(
    durations_s: Sequence[float], *, total_tokens: int | None = None
) -> LatencyStats:
    """Median / p90 / mean per-encounter wall seconds, with optional tokens/s.

    ``tokens_per_s`` is computed only when ``total_tokens`` is supplied (the client exposed usage)
    and the total wall time is positive; otherwise it stays ``None`` (unavailable, not fabricated).

    Raises:
        ValueError: if ``durations_s`` is empty (no encounter was timed).
    """
    if len(durations_s) == 0:
        raise ValueError("latency_stats needs at least one timed encounter")
    arr = np.asarray(durations_s, dtype=float)
    if np.any(arr < 0.0):
        raise ValueError("encounter durations must be non-negative")
    total_time = float(arr.sum())
    tokens_per_s: float | None = None
    if total_tokens is not None and total_time > 0.0:
        tokens_per_s = round(total_tokens / total_time, 3)
    return LatencyStats(
        n=int(arr.size),
        median_s=round(float(np.median(arr)), 4),
        p90_s=round(float(np.percentile(arr, 90)), 4),
        mean_s=round(float(arr.mean()), 4),
        tokens_per_s=tokens_per_s,
    )


__all__ = ["validity_icc", "validity_cell", "latency_stats"]
