"""Input contract for the ASR-robustness ICC-degradation phase.

Input:
  - asr_json: the batch-runner artifact (``results/phase_asr_robustness/asr_robustness.json``), a
    list of per (model x variant) ICC-degradation curves. Each curve carries an ordered set of
    points (target_wer, achieved_cer, icc_vs_gold, degenerate) and the metric label "cer".

No silent fallback: a malformed or impossible value (ICC outside [-1, 1], a non-degenerate point
whose ICC is nan, a CER outside [0, 1], a missing clean WER=0 anchor) raises instead of being worked
around. As with the scorer-robustness contract, a UNIFORMLY degenerate artifact (every point
degenerate across all curves) is the signature of a mock/offline run and is refused — degenerate
points are legitimate only in isolation.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]

_VALID_VARIANTS = {"zero_shot", "few_shot"}
#: Minimum number of corruption levels a usable degradation curve must sweep (incl. the WER=0 anchor).
MIN_LEVELS = 2
#: An ICC at or below this magnitude is treated as numerically zero (mock LLM emits a constant
#: score, so every ICC collapses to ~±1e-16). Real-model curves move orders of magnitude more.
_ZERO_ICC_TOL = 1e-9

#: Float tolerance on the ICC range check: the ANOVA estimator can legitimately land an epsilon
#: above 1.0 (e.g. 1.0000000000000007 on a perfectly deterministic temp-0 rescoring).
ICC_FLOAT_EPS = 1e-9


def _check_icc_value(value: object, ctx: str, *, allow_nan: bool) -> None:
    v = float(value)  # type: ignore[arg-type]
    if math.isnan(v):
        assert allow_nan, f"{ctx}: unexpected nan (degenerate variance must be flagged explicitly)"
        return
    assert -1.0 - ICC_FLOAT_EPS <= v <= 1.0 + ICC_FLOAT_EPS, f"{ctx}: ICC {v} outside [-1, 1]"


def _assert_not_uniformly_degenerate(curves: list, path: Path) -> None:
    """Refuse an artifact whose EVERY point is degenerate (the offline/mock signature).

    A genuine multi-model curve cannot have every ICC ~0/nan AND every point flagged degenerate
    across all curves — that uniform collapse is the deterministic mock (constant scores -> zero
    variance everywhere). Per the no-silent-fallback rule we reject rather than let it read as
    COMPUTED. Isolated degenerate points (e.g. the scramble ceiling collapsing one level) are fine.
    """
    all_degenerate = True
    saw_point = False
    for c in curves:
        for p in c.get("points", []):
            saw_point = True
            v = float(p.get("icc_vs_gold"))
            non_zero_icc = (not math.isnan(v)) and abs(v) > _ZERO_ICC_TOL
            if not p.get("degenerate", False) and non_zero_icc:
                all_degenerate = False
    if curves and saw_point and all_degenerate:
        raise AssertionError(
            f"{path}: artifact is uniformly degenerate (every curve point degenerate / ICC ~0). "
            "This is the signature of a mock/offline run, not real-model evidence; refusing to "
            "validate it as COMPUTED. Run scripts/asr_robustness.py against real models (drop "
            "--mock) before reporting this phase."
        )


def check_asr_robustness_inputs(asr_json: PathLike) -> None:
    path = Path(asr_json)
    assert path.is_file(), f"asr-robustness artifact missing: {path}"
    curves = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(curves, list) and curves, f"empty/non-list asr-robustness artifact: {path}"

    _assert_not_uniformly_degenerate(curves, path)

    for c in curves:
        for key in ("model_id", "variant", "seed", "metric", "points"):
            assert key in c, f"curve missing key '{key}'"
        assert c["variant"] in _VALID_VARIANTS, f"unknown variant {c['variant']!r}"
        assert c["metric"] == "cer", f"{c['model_id']}: metric {c['metric']!r} != 'cer'"

        points = c["points"]
        assert isinstance(points, list) and len(points) >= MIN_LEVELS, (
            f"{c['model_id']}: needs >= {MIN_LEVELS} curve points, got {len(points)}"
        )
        levels = [float(p["target_wer"]) for p in points]
        assert 0.0 in levels, f"{c['model_id']}: missing clean WER=0 anchor point"

        for p in points:
            ctx = f"{c['model_id']}.point(wer={p['target_wer']})"
            assert 0.0 <= float(p["target_wer"]) <= 1.0, f"{ctx}: target_wer outside [0, 1]"
            assert 0.0 <= float(p["achieved_cer"]) <= 1.0, f"{ctx}: achieved_cer outside [0, 1]"
            _check_icc_value(p["icc_vs_gold"], ctx, allow_nan=True)
            if p["degenerate"]:
                assert math.isnan(float(p["icc_vs_gold"])), (
                    f"{ctx}: flagged degenerate but icc_vs_gold is not nan"
                )
            else:
                assert not math.isnan(float(p["icc_vs_gold"])), (
                    f"{ctx}: non-degenerate point has nan icc_vs_gold (no silent number allowed)"
                )


__all__ = ["MIN_LEVELS", "check_asr_robustness_inputs"]
