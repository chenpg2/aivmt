"""Input contract for the local-vs-cloud phase (scoop-defense head-to-head).

Input:
  - lvc_json: the runner artifact (``results/phase_local_vs_cloud/local_vs_cloud.json``), one
    :class:`~aivmt.cloud.types.LocalVsCloudComparison`: a ``local`` provider cell, a list of ``cloud``
    cells, and per-provider ``deltas``. Each cell carries an overall ICC(2,1)/(2,k) and five
    per-SEGUE-domain ICCs, plus parse/refusal rates.

No silent fallback (mirrors the quant/robustness/ASR contracts): an ICC outside [-1, 1] (with the
shared ``ICC_FLOAT_EPS`` slack), a non-degenerate cell carrying a nan ICC, a rate outside [0, 1], a
provenance that is not off-device safe, or a missing key all RAISE rather than being worked around.

Mock-masquerade guard: a comparison whose EVERY scored cell (local + cloud) is degenerate / ICC ~0 is
the signature of a constant mock/offline run and is refused — it must not read as COMPUTED real
evidence. A single degenerate cell (e.g. a cloud model that collapses on one axis) is legitimate.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]

#: SEGUE domains every cell must report (kept local so the contract does not import src/ at module
#: load; cross-checked against the value in aivmt.cloud at runtime would couple the layers needlessly).
SEGUE_DOMAINS: tuple[str, ...] = (
    "set_the_stage",
    "elicit_information",
    "give_information",
    "understand_perspective",
    "end_encounter",
)

#: ICC needs n>=2 targets, so a usable cell must have scored at least this many transcripts.
MIN_TRANSCRIPTS = 2

#: Provenance values that prove the scored transcripts were off-device safe (no PHI transmitted).
_CLOUD_SAFE_PROVENANCE = frozenset({"synthetic", "deidentified"})

#: An ICC at or below this magnitude is treated as numerically zero (a constant mock score collapses
#: every ICC to ~±1e-16). Real-model cells move orders of magnitude more.
_ZERO_ICC_TOL = 1e-9

#: Float tolerance on the ICC range check (shared with the quant lane): the ANOVA estimator can land
#: an epsilon above 1.0 on a perfectly deterministic temp-0 rescoring.
ICC_FLOAT_EPS = 1e-9


def _check_icc_value(value: object, ctx: str, *, allow_nan: bool) -> None:
    v = float(value)  # type: ignore[arg-type]
    if math.isnan(v):
        assert allow_nan, f"{ctx}: unexpected nan (degenerate variance must be flagged explicitly)"
        return
    assert -1.0 - ICC_FLOAT_EPS <= v <= 1.0 + ICC_FLOAT_EPS, f"{ctx}: ICC {v} outside [-1, 1]"


def _check_domain(dom: dict, ctx: str) -> None:
    for key in ("domain", "icc2_1", "icc2_k", "degenerate"):
        assert key in dom, f"{ctx}: domain missing key '{key}'"
    _check_icc_value(dom["icc2_1"], f"{ctx}.{dom['domain']}.icc2_1", allow_nan=True)
    _check_icc_value(dom["icc2_k"], f"{ctx}.{dom['domain']}.icc2_k", allow_nan=True)
    if dom["degenerate"]:
        assert math.isnan(float(dom["icc2_1"])), f"{ctx}.{dom['domain']}: degenerate but ICC not nan"
    else:
        assert not math.isnan(float(dom["icc2_1"])), (
            f"{ctx}.{dom['domain']}: non-degenerate domain has nan ICC (no silent number allowed)"
        )


def _check_cell(cell: dict, ctx: str) -> None:
    for key in (
        "provider", "role", "model_id", "seed", "n_transcripts", "variant",
        "overall_icc2_1", "overall_icc2_k", "overall_degenerate",
        "parse_success_rate", "refusal_rate", "domains",
    ):
        assert key in cell, f"{ctx}: cell missing key '{key}'"
    assert cell["role"] in ("local", "cloud"), f"{ctx}: bad role {cell['role']!r}"
    assert int(cell["n_transcripts"]) >= MIN_TRANSCRIPTS, (
        f"{ctx}: only {cell['n_transcripts']} transcripts (< {MIN_TRANSCRIPTS})"
    )
    _check_icc_value(cell["overall_icc2_1"], f"{ctx}.overall_icc2_1", allow_nan=True)
    _check_icc_value(cell["overall_icc2_k"], f"{ctx}.overall_icc2_k", allow_nan=True)
    if cell["overall_degenerate"]:
        assert math.isnan(float(cell["overall_icc2_1"])), f"{ctx}: degenerate but overall ICC not nan"
    else:
        assert not math.isnan(float(cell["overall_icc2_1"])), (
            f"{ctx}: non-degenerate cell has nan overall ICC (no silent number allowed)"
        )
    assert 0.0 <= float(cell["parse_success_rate"]) <= 1.0, f"{ctx}: parse_success_rate outside [0,1]"
    assert 0.0 <= float(cell["refusal_rate"]) <= 1.0, f"{ctx}: refusal_rate outside [0,1]"
    domains = cell["domains"]
    seen = {d["domain"] for d in domains}
    assert seen == set(SEGUE_DOMAINS), f"{ctx}: domains {sorted(seen)} != SEGUE {sorted(SEGUE_DOMAINS)}"
    for dom in domains:
        _check_domain(dom, ctx)


def _cell_is_degenerate(cell: dict) -> bool:
    icc = float(cell["overall_icc2_1"])
    zero_or_nan = math.isnan(icc) or abs(icc) <= _ZERO_ICC_TOL
    return bool(cell.get("overall_degenerate", False) or zero_or_nan)


def _assert_not_uniformly_degenerate(comp: dict, path: Path) -> None:
    """Refuse a comparison whose EVERY cell (local + cloud) is degenerate / ICC ~0 (mock signature)."""
    cells = [comp["local"], *comp.get("cloud", [])]
    if cells and all(_cell_is_degenerate(c) for c in cells):
        raise AssertionError(
            f"{path}: comparison is uniformly degenerate (every cell degenerate / ICC ~0). This is "
            "the signature of a mock/offline run, not real-model evidence; refusing to validate it as "
            "COMPUTED. Run scripts/local_vs_cloud.py against real models (drop --mock) with at least "
            "one provider key set before reporting this phase."
        )


def check_local_vs_cloud_inputs(lvc_json: PathLike) -> None:
    path = Path(lvc_json)
    assert path.is_file(), f"local-vs-cloud artifact missing: {path}"
    comp = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(comp, dict), f"local-vs-cloud artifact is not an object: {path}"

    for key in (
        "local_model", "seed", "n_transcripts", "variant", "provenance",
        "non_inferiority_margin", "local", "cloud", "deltas",
    ):
        assert key in comp, f"artifact missing top-level key '{key}'"

    prov = comp["provenance"]
    assert prov in _CLOUD_SAFE_PROVENANCE, (
        f"PHI GUARD: artifact provenance {prov!r} is not off-device safe "
        f"{sorted(_CLOUD_SAFE_PROVENANCE)} — a real-data comparison must never have been written here"
    )
    margin = float(comp["non_inferiority_margin"])
    assert 0.0 < margin < 1.0, f"non-inferiority margin {margin} outside (0, 1)"

    _assert_not_uniformly_degenerate(comp, path)

    _check_cell(comp["local"], "local")
    assert comp["local"]["role"] == "local", "local cell must have role 'local'"
    cloud_names = []
    for cell in comp["cloud"]:
        ctx = f"cloud[{cell.get('provider', '?')}]"
        _check_cell(cell, ctx)
        assert cell["role"] == "cloud", f"{ctx}: role must be 'cloud'"
        cloud_names.append(cell["provider"])

    # Requested-vs-skipped provider bookkeeping (Finding-1 auditability). Optional for backward
    # compatibility, but when present it must be internally consistent so a partial head-to-head is
    # provably distinguishable from a deliberately-narrow request.
    requested = comp.get("requested_providers")
    skipped = comp.get("skipped_providers")
    if requested is not None or skipped is not None:
        requested = list(requested or [])
        skipped = list(skipped or [])
        scored = set(cloud_names)
        req_set = set(requested)
        skip_set = set(skipped)
        assert scored & skip_set == set(), (
            f"providers cannot be both scored and skipped: {sorted(scored & skip_set)}"
        )
        # Scored + skipped must each be within the requested set (no phantom providers), and together
        # they must cover every requested provider (a requested provider is either scored or skipped).
        assert scored <= req_set, f"scored cloud cells {sorted(scored - req_set)} not in requested set"
        assert skip_set <= req_set, f"skipped providers {sorted(skip_set - req_set)} not in requested set"
        assert scored | skip_set == req_set, (
            f"requested providers {sorted(req_set)} != scored {sorted(scored)} + skipped "
            f"{sorted(skip_set)} (a requested provider must be exactly one of scored/skipped)"
        )

    # Every delta must reference a scored cloud cell and report all SEGUE domains.
    for d in comp["deltas"]:
        for key in ("cloud_provider", "delta_overall", "delta_by_domain"):
            assert key in d, f"delta missing key '{key}'"
        assert d["cloud_provider"] in cloud_names, (
            f"delta references unknown cloud provider {d['cloud_provider']!r}"
        )
        _check_icc_value(d["delta_overall"], f"delta[{d['cloud_provider']}].overall", allow_nan=True)
        assert set(d["delta_by_domain"]) == set(SEGUE_DOMAINS), (
            f"delta[{d['cloud_provider']}]: domain set mismatch"
        )


__all__ = ["MIN_TRANSCRIPTS", "ICC_FLOAT_EPS", "SEGUE_DOMAINS", "check_local_vs_cloud_inputs"]
