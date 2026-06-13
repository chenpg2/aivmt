"""Run one quantization-frontier cell: score the golded set, time it, and probe memory + disk.

Reuses (read-only) ``aivmt.robustness.score_overall`` so the scored quantity is IDENTICAL to the
validity / robustness / ASR lanes — the frontier is therefore directly comparable. The ``ollama``
probes are injected (defaulting to the real CLI wrappers) so the runner is fully unit-testable with
fakes; no subprocess is launched in tests.
"""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Callable, Sequence

from ..llm.base import BaseLLMClient
from ..robustness import GoldedTranscript, score_overall
from ..schemas import Case
from ..scoring import ScorerVariant
from .metering import MeteredClient
from .metrics import latency_stats, validity_cell
from .ollama_probe import probe_disk_size, probe_loaded_memory
from .types import DiskUsage, MemoryUsage, QuantCell

logger = logging.getLogger(__name__)

#: A probe maps a model tag to its measured footprint; injected for testability.
MemoryProbe = Callable[[str], MemoryUsage]
DiskProbe = Callable[[str], DiskUsage]

__all__ = ["MemoryProbe", "DiskProbe", "run_quant_cell"]


def run_quant_cell(
    model_tag: str,
    label: str,
    case: Case,
    dataset: Sequence[GoldedTranscript],
    client: BaseLLMClient,
    *,
    seed: int,
    variant: ScorerVariant = "zero_shot",
    probe_memory: MemoryProbe | None = None,
    probe_disk: DiskProbe | None = None,
) -> QuantCell:
    """Measure validity, latency, memory and disk for one ``(model_tag x quant level)``.

    The model is scored first (which loads it under Ollama), then ``ollama ps`` is read while it is
    still resident to capture the runtime footprint, then ``ollama list`` for the on-disk size. A
    probe that cannot find/parse its target raises (fail-loud) and sinks this cell only.

    Raises:
        ValueError: if fewer than two transcripts are supplied (ICC needs n>=2 targets).
    """
    if len(dataset) < 2:
        raise ValueError("run_quant_cell needs >=2 transcripts (ICC requires n>=2 targets)")

    metered = client if isinstance(client, MeteredClient) else MeteredClient(client)
    golds = [g for _, g in dataset]

    # Warm-up: score the first transcript untimed to absorb model cold-load, then reset the
    # counters so the warm-up pollutes neither the latency sample nor the parse/refusal rates.
    score_overall(case, dataset[0][0], metered, variant)
    metered.reset()

    durations: list[float] = []
    sys_scores: list[float] = []
    for transcript, _gold in dataset:
        t0 = perf_counter()
        sys_scores.append(score_overall(case, transcript, metered, variant))
        durations.append(perf_counter() - t0)

    inner = metered.inner
    validity = validity_cell(
        sys_scores,
        golds,
        n_calls=inner.n_calls,
        n_parse_failures=inner.n_parse_failures,
        n_refusals=inner.n_refusals,
    )
    latency = latency_stats(durations, total_tokens=metered.total_tokens)

    pm = probe_memory if probe_memory is not None else probe_loaded_memory
    pd = probe_disk if probe_disk is not None else probe_disk_size
    memory = pm(model_tag)
    disk = pd(model_tag)

    logger.info(
        "[%s/%s] icc2_1=%s parse=%.3f median_s=%.3f p90_s=%.3f mem=%s disk=%s",
        model_tag, label, validity.icc2_1, validity.parse_success_rate,
        latency.median_s, latency.p90_s, memory.size_display, disk.size_display,
    )
    return QuantCell(
        model_tag=model_tag,
        label=label,
        seed=seed,
        n_transcripts=len(dataset),
        variant=variant,
        validity=validity,
        latency=latency,
        memory=memory,
        disk=disk,
    )
