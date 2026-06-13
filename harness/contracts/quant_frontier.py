"""Input contract for the quantization-frontier phase (SQ3 edge-deployability).

Input:
  - quant_json: the batch-runner artifact (``results/phase_quant_frontier/quant_frontier.json``), a
    list of per ``(model_tag x quant level)`` cells. Each carries a ``validity`` block (ICC-vs-gold +
    parse/refusal robustness), a ``latency`` block (median/p90 wall seconds, optional tokens/s), and
    ``memory`` + ``disk`` footprints.

No silent fallback: a malformed or impossible value (ICC outside [-1, 1], a non-degenerate cell whose
ICC is nan, a rate outside [0, 1], p90 below the median, a non-positive memory/disk size, a missing
footprint) raises instead of being worked around. As with the robustness / ASR contracts, a
UNIFORMLY degenerate artifact (every cell degenerate across all cells) is the signature of a
mock/offline run and is refused — degenerate cells are legitimate only in isolation.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]

#: ICC needs n>=2 targets, so a usable cell must have scored at least this many transcripts.
MIN_TRANSCRIPTS = 2
_VALID_VARIANTS = {"zero_shot", "few_shot"}

#: An ICC at or below this magnitude is treated as numerically zero (a constant mock score collapses
#: every ICC to ~±1e-16). Real-model cells move orders of magnitude more.
_ZERO_ICC_TOL = 1e-9

#: Float tolerance on the ICC range check: the ANOVA estimator can legitimately land an epsilon above
#: 1.0 (e.g. 1.0000000000000007 on a perfectly deterministic temp-0 rescoring).
ICC_FLOAT_EPS = 1e-9

#: p90 must be >= median; allow a hair of float slack so rounding noise does not trip the check.
_LATENCY_EPS = 1e-6


def _check_icc_value(value: object, ctx: str, *, allow_nan: bool) -> None:
    v = float(value)  # type: ignore[arg-type]
    if math.isnan(v):
        assert allow_nan, f"{ctx}: unexpected nan (degenerate variance must be flagged explicitly)"
        return
    assert -1.0 - ICC_FLOAT_EPS <= v <= 1.0 + ICC_FLOAT_EPS, f"{ctx}: ICC {v} outside [-1, 1]"


def _assert_not_uniformly_degenerate(cells: list, path: Path) -> None:
    """Refuse an artifact whose EVERY cell is degenerate (the offline/mock signature).

    A genuine frontier cannot have every cell flagged degenerate AND every ICC ~0/nan across all
    cells — that uniform collapse is the deterministic mock (constant scores -> zero variance
    everywhere). Per the no-silent-fallback rule we reject rather than let it read as COMPUTED.
    Isolated degenerate cells (e.g. an over-quantized model that stops discriminating) are fine.
    """
    all_degenerate = True
    saw_cell = False
    for c in cells:
        saw_cell = True
        v = c.get("validity") or {}
        icc = float(v.get("icc2_1"))
        non_zero_icc = (not math.isnan(icc)) and abs(icc) > _ZERO_ICC_TOL
        if not v.get("degenerate", False) and non_zero_icc:
            all_degenerate = False
    if cells and saw_cell and all_degenerate:
        raise AssertionError(
            f"{path}: artifact is uniformly degenerate (every cell degenerate / ICC ~0). This is "
            "the signature of a mock/offline run, not real-model evidence; refusing to validate it "
            "as COMPUTED. Run scripts/quant_frontier.py against real models (drop --mock) before "
            "reporting this phase."
        )


def _check_validity(v: dict, ctx: str) -> None:
    for key in ("icc2_1", "icc2_k", "n_scored", "parse_success_rate", "refusal_rate", "degenerate"):
        assert key in v, f"{ctx}: validity missing key '{key}'"
    _check_icc_value(v["icc2_1"], f"{ctx}.icc2_1", allow_nan=True)
    _check_icc_value(v["icc2_k"], f"{ctx}.icc2_k", allow_nan=True)
    assert 0.0 <= float(v["parse_success_rate"]) <= 1.0, f"{ctx}: parse_success_rate outside [0, 1]"
    assert 0.0 <= float(v["refusal_rate"]) <= 1.0, f"{ctx}: refusal_rate outside [0, 1]"
    if v["degenerate"]:
        assert math.isnan(float(v["icc2_1"])) and math.isnan(float(v["icc2_k"])), (
            f"{ctx}: flagged degenerate but ICC is not nan"
        )
    else:
        assert not math.isnan(float(v["icc2_1"])), (
            f"{ctx}: non-degenerate cell has nan ICC (no silent number allowed)"
        )


def _check_latency(lat: dict, ctx: str) -> None:
    for key in ("n", "median_s", "p90_s", "mean_s", "tokens_per_s"):
        assert key in lat, f"{ctx}: latency missing key '{key}'"
    assert int(lat["n"]) >= 1, f"{ctx}: latency n={lat['n']} (< 1)"
    median, p90, mean = float(lat["median_s"]), float(lat["p90_s"]), float(lat["mean_s"])
    assert median >= 0.0 and p90 >= 0.0 and mean >= 0.0, f"{ctx}: negative latency"
    assert p90 >= median - _LATENCY_EPS, f"{ctx}: p90 {p90} below median {median}"
    if lat["tokens_per_s"] is not None:
        assert float(lat["tokens_per_s"]) > 0.0, f"{ctx}: non-positive tokens_per_s"


def _check_footprint(cell: dict, ctx: str) -> None:
    mem = cell["memory"]
    assert mem is not None, f"{ctx}: memory footprint missing (must be measured while loaded)"
    assert int(mem["size_bytes"]) > 0, f"{ctx}: memory size_bytes must be positive"
    disk = cell["disk"]
    assert disk is not None, f"{ctx}: disk footprint missing"
    assert int(disk["size_bytes"]) > 0, f"{ctx}: disk size_bytes must be positive"


def check_quant_frontier_inputs(quant_json: PathLike) -> None:
    path = Path(quant_json)
    assert path.is_file(), f"quant-frontier artifact missing: {path}"
    cells = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(cells, list) and cells, f"empty/non-list quant-frontier artifact: {path}"

    _assert_not_uniformly_degenerate(cells, path)

    for c in cells:
        for key in (
            "model_tag", "label", "seed", "n_transcripts", "variant",
            "validity", "latency", "memory", "disk",
        ):
            assert key in c, f"cell missing key '{key}'"
        tag = c["model_tag"]
        assert isinstance(tag, str) and tag, "cell has empty model_tag"
        assert c["variant"] in _VALID_VARIANTS, f"{tag}: unknown variant {c['variant']!r}"
        assert int(c["n_transcripts"]) >= MIN_TRANSCRIPTS, (
            f"{tag}: only {c['n_transcripts']} transcripts (< {MIN_TRANSCRIPTS})"
        )
        ctx = f"{tag}[{c['label']}]"
        _check_validity(c["validity"], ctx)
        _check_latency(c["latency"], ctx)
        _check_footprint(c, ctx)


__all__ = ["MIN_TRANSCRIPTS", "ICC_FLOAT_EPS", "check_quant_frontier_inputs"]
