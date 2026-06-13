"""Immutable, JSON-serializable result dataclasses for the local-vs-cloud lane (scoop defense).

One :class:`ProviderCell` is the validity of ONE scorer model (the local model, or a cloud
comparator) vs the designed-quality synthetic gold: overall ICC(2,1)/(2,k) AND per-SEGUE-domain ICC,
plus JSON-parse / refusal robustness. One :class:`LocalVsCloudComparison` bundles the local cell, the
cloud cells, and the local-minus-cloud deltas (overall + per domain) the manuscript reports against
the pre-registered non-inferiority margin (delta = 0.10, HYPOTHESIS.md).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DomainValidity:
    """ICC-vs-gold for one scorer on one SEGUE domain. ``nan`` + ``degenerate`` when no variance."""

    domain: str
    icc2_1: float
    icc2_k: float
    degenerate: bool


@dataclass(frozen=True)
class ProviderCell:
    """Validity of one scorer model (local or a cloud provider) vs the synthetic gold.

    ``overall_*`` is the headline ICC on the weighted overall score; ``domains`` carries the per-SEGUE
    domain ICCs (where cloud models are known to collapse). ``role`` is ``"local"`` or ``"cloud"``.
    """

    provider: str
    role: str
    model_id: str
    seed: int
    n_transcripts: int
    variant: str
    overall_icc2_1: float
    overall_icc2_k: float
    overall_degenerate: bool
    parse_success_rate: float
    refusal_rate: float
    domains: tuple[DomainValidity, ...]

    def domain_icc(self, domain: str) -> float:
        for d in self.domains:
            if d.domain == domain:
                return d.icc2_1
        raise KeyError(f"no domain {domain!r} in provider cell {self.provider!r}")


@dataclass(frozen=True)
class LocalVsCloudDelta:
    """Local-minus-cloud ICC gap for one cloud provider (overall + per SEGUE domain).

    Positive => the LOCAL model agrees with gold MORE than the cloud comparator on that axis. The
    pre-registered non-inferiority claim is ``delta_overall >= -margin`` (margin = 0.10): the local
    model is non-inferior to cloud if it is at most ``margin`` below it. ``nan`` deltas (a degenerate
    cell on either side) are reported explicitly, never coerced to a number.
    """

    cloud_provider: str
    delta_overall: float
    delta_by_domain: dict[str, float]


@dataclass(frozen=True)
class LocalVsCloudComparison:
    """Full local-vs-cloud head-to-head, ready to serialize.

    ``provenance`` records that the scored transcripts were the off-device-safe synthetic/de-identified
    set (the PHI guard's stamp) — proof in the artifact that no real data was transmitted.

    ``requested_providers`` / ``skipped_providers`` make a PARTIAL head-to-head auditable: a provider
    the user explicitly requested but whose API key was unset is recorded here (not just warned to the
    log), so a downstream reader can tell "ran a 1-way comparison because two keys were missing" apart
    from "only asked for one provider". ``cloud`` lists the providers that WERE scored;
    ``skipped_providers`` lists requested-but-keyless ones; their union is ``requested_providers``.
    """

    local_model: str
    seed: int
    n_transcripts: int
    variant: str
    provenance: str
    non_inferiority_margin: float
    local: ProviderCell
    cloud: tuple[ProviderCell, ...] = ()
    deltas: tuple[LocalVsCloudDelta, ...] = ()
    #: Every cloud provider the caller asked for (scored + skipped). Empty tuple == not recorded.
    requested_providers: tuple[str, ...] = ()
    #: Requested providers dropped because their env key was unset (real mode); auditable, not log-only.
    skipped_providers: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


__all__ = [
    "DomainValidity",
    "ProviderCell",
    "LocalVsCloudDelta",
    "LocalVsCloudComparison",
]
