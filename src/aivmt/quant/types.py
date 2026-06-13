"""Immutable, JSON-serializable result dataclasses for the quantization-frontier lane (SQ3).

One :class:`QuantCell` is the unit of the validity-cost frontier: for a single
``(model_tag x quant level)`` it bundles (a) the validity of the local-model automated scores vs the
designed-quality gold (ICC + parse/refusal robustness), (b) per-encounter latency, (c) loaded
RAM/VRAM, and (d) on-disk model size. These are the per-cell paper numbers the manuscript reports as
the edge-deployability surface.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ValidityCell:
    """Validity of one model's automated scores vs the designed-quality gold.

    ``degenerate`` is True when the scorer produced no between-encounter variance (it could not
    discriminate the transcripts); the ICCs are then an explicit ``nan``, never a silent number.
    """

    icc2_1: float
    icc2_k: float
    n_scored: int
    parse_success_rate: float
    refusal_rate: float
    degenerate: bool


@dataclass(frozen=True)
class LatencyStats:
    """Per-encounter wall-clock latency for one cell.

    ``tokens_per_s`` is populated only when the underlying client exposes token usage; otherwise it
    is ``None`` (reported honestly as unavailable rather than fabricated).
    """

    n: int
    median_s: float
    p90_s: float
    mean_s: float
    tokens_per_s: float | None


@dataclass(frozen=True)
class MemoryUsage:
    """Loaded model footprint parsed from ``ollama ps`` (the runtime RAM/VRAM while resident)."""

    model_tag: str
    size_bytes: int
    size_display: str
    processor: str
    context: int | None


@dataclass(frozen=True)
class DiskUsage:
    """On-disk model size parsed from ``ollama list`` for one tag."""

    model_tag: str
    size_bytes: int
    size_display: str


@dataclass(frozen=True)
class QuantCell:
    """The full validity-cost result for one ``(model_tag x quant level)``, ready to serialize."""

    model_tag: str
    label: str
    seed: int
    n_transcripts: int
    variant: str
    validity: ValidityCell
    latency: LatencyStats
    memory: MemoryUsage | None = None
    disk: DiskUsage | None = field(default=None)

    def to_dict(self) -> dict:
        return asdict(self)


__all__ = [
    "ValidityCell",
    "LatencyStats",
    "MemoryUsage",
    "DiskUsage",
    "QuantCell",
]
