"""Input contract for the scorer-robustness phase.

Input:
  - robustness_json: the batch-runner artifact (``results/phase_robustness/robustness.json``), a
    list of per (model x variant) reports. Each must carry a paraphrase-sensitivity block (with one
    finite-or-nan ICC per paraphrase) and zero or more test-retest cells.

No silent fallback: a malformed or impossible value (ICC outside [-1, 1], a paraphrase count below
the declared minimum, a non-degenerate cell whose retest ICC is nan) raises instead of being
worked around.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Union

from aivmt.robustness.paraphrase import PARAPHRASE_TEMPLATES

PathLike = Union[str, Path]

#: Minimum number of paraphrase templates the spread must be computed over (>=5 non-identity + base).
MIN_PARAPHRASES = 5
_VALID_VARIANTS = {"zero_shot", "few_shot"}

#: Float tolerance on the ICC range check: the ANOVA estimator can legitimately land an epsilon
#: above 1.0 (e.g. 1.0000000000000007 on a perfectly deterministic temp-0 retest).
ICC_FLOAT_EPS = 1e-9


def _check_icc_value(value: object, ctx: str, *, allow_nan: bool) -> None:
    v = float(value)  # type: ignore[arg-type]
    if math.isnan(v):
        assert allow_nan, f"{ctx}: unexpected nan (degenerate variance must be flagged explicitly)"
        return
    assert -1.0 - ICC_FLOAT_EPS <= v <= 1.0 + ICC_FLOAT_EPS, f"{ctx}: ICC {v} outside [-1, 1]"


#: A paraphrase ICC at or below this magnitude is treated as numerically zero (the mock LLM emits a
#: constant score, so every ICC collapses to ~±1e-16). Real-model spread is orders of magnitude larger.
_ZERO_ICC_TOL = 1e-9


def _assert_not_uniformly_degenerate(reports: list, path: Path) -> None:
    """Fail loud on the signature of a mock/offline run masquerading as real-model evidence.

    A genuine multi-model robustness batch cannot have *every* paraphrase ICC ~0 AND *every*
    test-retest cell degenerate across *all* reports — that uniform collapse is the deterministic
    mock client (constant scores -> zero variance everywhere). Degenerate cells are legitimate in
    isolation (nan is the honest value), so we only reject when the WHOLE artifact is degenerate,
    which no real run produces. Per the no-silent-fallback rule we refuse rather than let it read as
    COMPUTED in the evidence table.
    """
    all_paraphrase_zero = True
    all_retest_degenerate = True
    saw_retest = False
    for r in reports:
        per = (r.get("paraphrase") or {}).get("per_paraphrase_icc") or {}
        for val in per.values():
            v = float(val)
            if math.isnan(v) or abs(v) > _ZERO_ICC_TOL:
                all_paraphrase_zero = False
        for t in r.get("test_retest", []):
            saw_retest = True
            if not t.get("degenerate", False):
                all_retest_degenerate = False
    if reports and all_paraphrase_zero and saw_retest and all_retest_degenerate:
        raise AssertionError(
            f"{path}: artifact is uniformly degenerate (every paraphrase ICC ~0 and every "
            "test-retest cell degenerate). This is the signature of a mock/offline run, not "
            "real-model evidence; refusing to validate it as COMPUTED. Run scripts/robustness.py "
            "against real models (drop --mock) before reporting this phase."
        )


def check_robustness_inputs(robustness_json: PathLike) -> None:
    path = Path(robustness_json)
    assert path.is_file(), f"robustness artifact missing: {path}"
    reports = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(reports, list) and reports, f"empty/non-list robustness artifact: {path}"

    _assert_not_uniformly_degenerate(reports, path)

    for r in reports:
        for key in ("model_id", "variant", "seed", "paraphrase"):
            assert key in r, f"report missing key '{key}'"
        assert r["variant"] in _VALID_VARIANTS, f"unknown variant {r['variant']!r}"

        p = r["paraphrase"]
        assert p["n_paraphrases"] >= MIN_PARAPHRASES, (
            f"{r['model_id']}: only {p['n_paraphrases']} paraphrases (< {MIN_PARAPHRASES})"
        )
        assert p["n_paraphrases"] == len(PARAPHRASE_TEMPLATES), (
            f"{r['model_id']}: paraphrase count {p['n_paraphrases']} != registered "
            f"{len(PARAPHRASE_TEMPLATES)}"
        )
        per = p["per_paraphrase_icc"]
        assert isinstance(per, dict) and per, f"{r['model_id']}: empty per_paraphrase_icc"
        for name, val in per.items():
            _check_icc_value(val, f"{r['model_id']}.paraphrase[{name}]", allow_nan=True)

        for t in r.get("test_retest", []):
            ctx = f"{r['model_id']}.retest(temp={t['temperature']})"
            assert t["n_repeats"] >= 2, f"{ctx}: K={t['n_repeats']} (< 2)"
            # A non-degenerate cell must report a real ICC; a degenerate one MUST be nan.
            _check_icc_value(t["retest_icc"], ctx, allow_nan=True)
            if t["degenerate"]:
                assert math.isnan(float(t["retest_icc"])), (
                    f"{ctx}: flagged degenerate but retest_icc is not nan"
                )
            else:
                assert not math.isnan(float(t["retest_icc"])), (
                    f"{ctx}: non-degenerate cell has nan retest_icc (no silent number allowed)"
                )
