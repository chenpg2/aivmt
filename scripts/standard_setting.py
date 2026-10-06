"""Standard setting for the pass/fail cut score (Reviewer 2, point 10).

Reviewer 2 noted that the decision-consistency analysis rests entirely on a cut of 0.6
with no standard-setting rationale, and that an unjustified cut is itself a validity
concern for everything downstream of it. This script supplies that rationale using the
two standard methods that the existing data can support.

The pre-specified cut is the department's customary 60-mark pass threshold, fixed before
analysis. The question these methods answer is whether that administrative threshold is
defensible as a competence standard on this instrument, not whether it can be re-derived
from the data it was applied to.

Angoff and its variants require a panel to judge each checklist item for a hypothetical
borderline candidate, which cannot be reconstructed after the fact, so it is not run here.

Method 1, borderline regression. Faculty supplied two independent judgements per
encounter: seven domain scores, which combine into the pre-registered composite, and a
separate holistic overall rating. Regressing the composite on the holistic rating and
reading off the composite at the holistic pass boundary gives the composite score that
corresponds to a just-passing performance in the raters' own holistic judgement. A
percentile bootstrap gives its confidence interval.

Method 2, contrasting groups. Splitting encounters into those the faculty judged
competent and not competent on the holistic rating, the cut on the *system* score that
best separates the two groups is located by maximising Youden's J. This asks a different
question from method 1: given the faculty standard, where should the automated score be
cut so that its decisions reproduce it.

Both methods use only the existing 162 encounters and the existing three blinded faculty.

Usage:
  uv run python scripts/standard_setting.py
  uv run python scripts/standard_setting.py --holistic-pass 0.6 --out results/phase_standard_setting
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import statistics as st
from collections import defaultdict
from pathlib import Path
from typing import Sequence

logger = logging.getLogger("aivmt.standard_setting")

ROOT = Path(__file__).resolve().parents[1]
SEGUE = ("set_the_stage", "elicit_information", "give_information",
         "understand_perspective", "end_encounter")
W_HISTORY, W_SEGUE, W_REASONING = 0.4, 0.4, 0.2


def _composite(row: dict) -> float:
    """Pre-registered composite from one rater's seven domain scores."""
    return (W_HISTORY * float(row["history_completion"])
            + W_SEGUE * st.mean(float(row[d]) for d in SEGUE)
            + W_REASONING * float(row["reasoning"]))


def _ols(x: Sequence[float], y: Sequence[float]) -> tuple[float, float]:
    """Least-squares slope and intercept; raises if x has no spread."""
    mx, my = st.mean(x), st.mean(y)
    sxx = sum((a - mx) ** 2 for a in x)
    if sxx == 0.0:
        raise ValueError("FAIL: predictor has zero variance; cannot regress")
    slope = sum((a - mx) * (b - my) for a, b in zip(x, y)) / sxx
    return slope, my - slope * mx


def borderline_regression(holistic: Sequence[float], composite: Sequence[float],
                          pass_point: float, seed: int, n_boot: int = 2000) -> dict:
    """Composite score predicted at the holistic pass boundary, with a bootstrap CI."""
    slope, intercept = _ols(holistic, composite)
    cut = slope * pass_point + intercept
    rng = random.Random(seed)
    n = len(holistic)
    boot: list[float] = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        try:
            s, i = _ols([holistic[k] for k in idx], [composite[k] for k in idx])
        except ValueError:
            continue
        boot.append(s * pass_point + i)
    boot.sort()
    lo = boot[int(0.025 * len(boot))]
    hi = boot[int(0.975 * len(boot)) - 1]
    return {"method": "borderline_regression", "holistic_pass_point": pass_point,
            "slope": slope, "intercept": intercept, "cut_score": cut,
            "ci_lower": lo, "ci_upper": hi, "n": n, "n_bootstrap": len(boot), "seed": seed}


def contrasting_groups(system: Sequence[float], competent: Sequence[bool]) -> dict:
    """System-score cut maximising Youden's J against the faculty competence grouping."""
    n_pos = sum(competent)
    n_neg = len(competent) - n_pos
    if n_pos == 0 or n_neg == 0:
        raise ValueError("FAIL: contrasting groups requires both groups to be non-empty")
    best: dict[str, float] = {"cut_score": 0.0, "sensitivity": 0.0,
                              "specificity": 0.0, "youden_j": -1.0}
    for cand in sorted({round(v, 4) for v in system} | {0.0, 1.0}):
        tp = sum(1 for s, c in zip(system, competent) if c and s >= cand)
        tn = sum(1 for s, c in zip(system, competent) if not c and s < cand)
        sens, spec = tp / n_pos, tn / n_neg
        j = sens + spec - 1.0
        if j > best["youden_j"]:
            best = {"cut_score": cand, "sensitivity": sens, "specificity": spec, "youden_j": j}
    return {"method": "contrasting_groups", "n_competent": n_pos,
            "n_not_competent": n_neg, **best}


def operating_point(system: Sequence[float], competent: Sequence[bool], cut: float) -> dict:
    """Sensitivity and specificity of a given system cut against the faculty grouping."""
    n_pos = sum(competent)
    n_neg = len(competent) - n_pos
    tp = sum(1 for s, c in zip(system, competent) if c and s >= cut)
    tn = sum(1 for s, c in zip(system, competent) if not c and s < cut)
    return {"cut_score": cut, "sensitivity": tp / n_pos, "specificity": tn / n_neg,
            "correct_classification": (tp + tn) / len(competent)}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--enc", default=str(ROOT / "data" / "encounters" / "real_students"))
    ap.add_argument("--fac", default=str(ROOT / "data" / "faculty_ratings_real.csv"))
    ap.add_argument("--out", default=str(ROOT / "results" / "phase_standard_setting"))
    ap.add_argument("--holistic-pass", type=float, default=0.6,
                    help="pass boundary on the faculty holistic scale (60 marks)")
    ap.add_argument("--prespecified-cut", type=float, default=0.6)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    fac_path = Path(args.fac)
    if not fac_path.is_file():
        raise SystemExit(f"FAIL: faculty ratings not found at {fac_path}")

    by_enc: dict[str, list[dict]] = defaultdict(list)
    for row in csv.DictReader(fac_path.open(encoding="utf-8-sig")):
        by_enc[row["encounter_id"]].append(row)

    sys_score: dict[str, float] = {}
    for path in Path(args.enc).glob("*.json"):
        rec = json.loads(path.read_text(encoding="utf-8"))
        sys_score[rec["encounter_id"]] = float(rec["score"]["overall"])

    ids = sorted(set(by_enc) & set(sys_score))
    if not ids:
        raise SystemExit("FAIL: no encounters join between ratings and scored encounters")
    logger.info("joined %d encounters (%d rated, %d scored)", len(ids), len(by_enc), len(sys_score))

    holistic = [st.mean(float(r["overall"]) for r in by_enc[i]) for i in ids]
    composite = [st.mean(_composite(r) for r in by_enc[i]) for i in ids]
    system = [sys_score[i] for i in ids]
    competent = [h >= args.holistic_pass for h in holistic]

    br = borderline_regression(holistic, composite, args.holistic_pass, args.seed)
    cg = contrasting_groups(system, competent)
    pre = operating_point(system, competent, args.prespecified_cut)
    opt = operating_point(system, competent, cg["cut_score"])

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload = {"n_encounters": len(ids), "n_raters": len(by_enc[ids[0]]), "seed": args.seed,
               "prespecified_cut": args.prespecified_cut,
               "borderline_regression": br, "contrasting_groups": cg,
               "prespecified_operating_point": pre, "optimal_operating_point": opt}
    (out / "standard_setting.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    md = [
        "# Standard setting for the pass/fail cut score",
        "",
        f"- encounters: **{len(ids)}**; faculty raters: **{len(by_enc[ids[0]])}**; seed: {args.seed}",
        f"- pre-specified cut (departmental 60-mark pass threshold): **{args.prespecified_cut:.2f}**",
        "",
        "## Borderline regression (faculty instrument)",
        "",
        "Faculty composite regressed on the faculty holistic rating; the cut is the composite",
        f"predicted at a holistic rating of {args.holistic_pass:.2f}.",
        "",
        f"- slope = {br['slope']:.3f}, intercept = {br['intercept']:.3f}",
        f"- **cut score = {br['cut_score']:.3f}** (95% percentile bootstrap CI "
        f"[{br['ci_lower']:.3f}, {br['ci_upper']:.3f}], {br['n_bootstrap']} resamples)",
        "",
        "## Contrasting groups (system score)",
        "",
        f"Faculty judged {cg['n_competent']} encounters competent and {cg['n_not_competent']} not,",
        "at the holistic pass boundary. The system cut maximising Youden's J is:",
        "",
        f"- **cut score = {cg['cut_score']:.3f}**, sensitivity {cg['sensitivity']:.3f}, "
        f"specificity {cg['specificity']:.3f}, Youden's J {cg['youden_j']:.3f}",
        "",
        "## Operating points compared",
        "",
        "| Cut | Sensitivity | Specificity | Correctly classified |",
        "|---|---|---|---|",
        f"| {pre['cut_score']:.3f} (pre-specified) | {pre['sensitivity']:.3f} | "
        f"{pre['specificity']:.3f} | {pre['correct_classification']:.3f} |",
        f"| {opt['cut_score']:.3f} (contrasting groups) | {opt['sensitivity']:.3f} | "
        f"{opt['specificity']:.3f} | {opt['correct_classification']:.3f} |",
        "",
    ]
    (out / "summary.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
