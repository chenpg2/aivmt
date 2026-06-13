"""Local-vs-cloud comparison logic: score each model through the SAME scorers, compute ICC deltas.

Given the local model and a set of cloud providers, every model scores the IDENTICAL off-device-safe
synthetic golded set through the identical scorers (``score_with_domains``), and we compute, per
model, ICC(2,1)/(2,k)-vs-gold on the weighted overall AND on each SEGUE domain (reusing the quant
lane's ``validity_icc`` so the estimator and the degenerate->nan rule are shared). The local-minus-cloud
deltas feed the pre-registered non-inferiority test (margin delta = 0.10, HYPOTHESIS.md).

PHI safety is structural: :func:`compare_local_vs_cloud` accepts ONLY a :class:`CloudSafeDataset`
(``assert_dataset_cloud_safe`` re-checks it) — a raw transcript list that could originate from real
data is refused before any model is called.
"""

from __future__ import annotations

import logging
from typing import Sequence

from ..llm.base import BaseLLMClient, LLMOutputError
from ..quant.metrics import validity_icc
from ..schemas import Case
from ..scoring import ScorerVariant
from .provenance import CloudSafeDataset, assert_dataset_cloud_safe
from .scoring import SEGUE_DOMAINS, score_with_domains
from .types import (
    DomainValidity,
    LocalVsCloudComparison,
    LocalVsCloudDelta,
    ProviderCell,
)

logger = logging.getLogger(__name__)

#: Pre-registered non-inferiority margin (HYPOTHESIS.md §"Statistical test", delta = 0.10).
DEFAULT_NI_MARGIN: float = 0.10


def _delta(local: float, cloud: float) -> float:
    """Local-minus-cloud ICC, propagating ``nan`` (a degenerate cell on either side) explicitly."""
    return float("nan") if (local != local or cloud != cloud) else local - cloud  # nan-safe


def score_provider_cell(
    provider: str,
    role: str,
    model_id: str,
    case: Case,
    dataset: CloudSafeDataset,
    client: BaseLLMClient,
    *,
    seed: int,
    variant: ScorerVariant = "zero_shot",
) -> ProviderCell:
    """Score the cloud-safe golded set through ``client`` and build the per-model validity cell.

    Computes overall ICC-vs-gold and per-SEGUE-domain ICC-vs-gold. An encounter whose scorer fails to
    parse is dropped from that model's vectors and counted (fail-loud per-call, never a fake zero);
    ICC then uses the encounters that did parse. Requires >=2 parsed encounters (ICC needs n>=2).

    Raises:
        ValueError: if fewer than two encounters scored successfully.
    """
    safe = assert_dataset_cloud_safe(dataset)  # defensive re-check at the transmission boundary
    golds: list[float] = []
    overall_scores: list[float] = []
    domain_scores: dict[str, list[float]] = {d: [] for d in SEGUE_DOMAINS}

    n_calls = 0
    n_parse_failures = 0
    n_refusals = 0
    for transcript, gold in safe.transcripts:
        try:
            ds = score_with_domains(case, transcript, client, variant)
        except LLMOutputError as exc:
            n_parse_failures += 1
            logger.warning("[%s] parse failure on %s: %s", provider, transcript.encounter_id, exc)
            continue
        overall_scores.append(ds.overall)
        for d in SEGUE_DOMAINS:
            domain_scores[d].append(ds.segue[d])
        golds.append(gold)

    # Pull the wrapped client's counters (the scorer increments n_calls/n_parse_failures/n_refusals).
    n_calls = int(getattr(client, "n_calls", len(overall_scores)) or len(overall_scores))
    n_parse_failures = int(getattr(client, "n_parse_failures", n_parse_failures))
    n_refusals = int(getattr(client, "n_refusals", n_refusals))

    if len(overall_scores) < 2:
        raise ValueError(
            f"provider {provider!r} produced only {len(overall_scores)} parsed encounters "
            "(< 2); cannot compute ICC"
        )

    overall_icc2_1, overall_icc2_k, overall_degenerate = validity_icc(overall_scores, golds)
    domains: list[DomainValidity] = []
    for d in SEGUE_DOMAINS:
        i1, ik, deg = validity_icc(domain_scores[d], golds)
        domains.append(DomainValidity(domain=d, icc2_1=i1, icc2_k=ik, degenerate=deg))

    denom = max(n_calls, 1)
    cell = ProviderCell(
        provider=provider,
        role=role,
        model_id=model_id,
        seed=seed,
        n_transcripts=len(overall_scores),
        variant=variant,
        overall_icc2_1=overall_icc2_1,
        overall_icc2_k=overall_icc2_k,
        overall_degenerate=overall_degenerate,
        parse_success_rate=round(1.0 - n_parse_failures / denom, 4),
        refusal_rate=round(n_refusals / denom, 4),
        domains=tuple(domains),
    )
    logger.info(
        "[%s/%s] overall_icc2_1=%s parse=%.3f (n=%d)",
        role, provider, overall_icc2_1, cell.parse_success_rate, cell.n_transcripts,
    )
    return cell


def compare_local_vs_cloud(
    case: Case,
    dataset: CloudSafeDataset,
    local_model: str,
    local_client: BaseLLMClient,
    cloud: Sequence[tuple[str, str, BaseLLMClient]],
    *,
    seed: int,
    variant: ScorerVariant = "zero_shot",
    ni_margin: float = DEFAULT_NI_MARGIN,
    requested_providers: Sequence[str] | None = None,
    skipped_providers: Sequence[str] | None = None,
) -> LocalVsCloudComparison:
    """Run the local-vs-cloud head-to-head over a cloud-safe synthetic dataset.

    Args:
        case: the SP case the synthetic transcripts belong to.
        dataset: the off-device-safe golded set (PHI-guarded; a raw list is refused).
        local_model: tag of the local model (e.g. ``"llama3.1:8b"``).
        local_client: client for the local model (mock or Ollama-backed).
        cloud: ``(provider_name, model_id, client)`` triples for each cloud comparator with a key.
        seed: reproducibility seed (from ``configs/seed.yaml``).
        variant: scorer prompting arm.
        ni_margin: pre-registered non-inferiority margin (default 0.10).
        requested_providers: every cloud provider the caller asked for (scored + skipped). When
            ``None`` it defaults to the scored providers, so the artifact never under-claims what was
            requested. Recorded in the artifact so a partial head-to-head is auditable.
        skipped_providers: requested providers dropped because their key was unset (real mode). When
            ``None`` it is inferred as ``requested_providers`` minus the scored providers.

    Returns:
        A :class:`LocalVsCloudComparison` with the local cell, cloud cells, per-provider deltas, and
        the requested-vs-skipped provider sets (so a partial run leaves a durable trace).
    """
    safe = assert_dataset_cloud_safe(dataset)

    local_cell = score_provider_cell(
        local_model, "local", local_model, case, safe, local_client, seed=seed, variant=variant
    )

    cloud_cells: list[ProviderCell] = []
    deltas: list[LocalVsCloudDelta] = []
    failed: list[str] = []
    for provider_name, model_id, client in cloud:
        # Per-provider isolation: a flaky aggregator proxy that errors out (timeout, 5xx, refusal
        # storm) after the client's own retries must NOT lose the providers that already scored. The
        # failed provider is recorded as skipped so a multi-cloud panel degrades gracefully.
        try:
            cell = score_provider_cell(
                provider_name, "cloud", model_id, case, safe, client, seed=seed, variant=variant
            )
        except Exception as exc:  # noqa: BLE001 — isolate one provider's failure from the panel
            logger.error("cloud provider %s failed, recording as skipped: %s", provider_name, exc)
            failed.append(provider_name)
            continue
        cloud_cells.append(cell)
        deltas.append(
            LocalVsCloudDelta(
                cloud_provider=provider_name,
                delta_overall=_delta(local_cell.overall_icc2_1, cell.overall_icc2_1),
                delta_by_domain={
                    d.domain: _delta(local_cell.domain_icc(d.domain), d.icc2_1)
                    for d in cell.domains
                },
            )
        )

    scored_names = tuple(c.provider for c in cloud_cells)
    requested = tuple(requested_providers) if requested_providers is not None else scored_names
    base_skipped = tuple(skipped_providers) if skipped_providers is not None else tuple(
        name for name in requested if name not in set(scored_names)
    )
    # Merge runtime failures into the skipped set (preserve order, dedup).
    skipped = tuple(dict.fromkeys((*base_skipped, *failed)))

    return LocalVsCloudComparison(
        local_model=local_model,
        seed=seed,
        n_transcripts=len(safe),
        variant=variant,
        provenance=safe.provenance,
        non_inferiority_margin=ni_margin,
        local=local_cell,
        cloud=tuple(cloud_cells),
        deltas=tuple(deltas),
        requested_providers=requested,
        skipped_providers=skipped,
    )


__all__ = [
    "DEFAULT_NI_MARGIN",
    "score_provider_cell",
    "compare_local_vs_cloud",
]
