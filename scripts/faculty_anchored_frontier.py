"""Faculty-anchored validity for stepped-down scoring configurations (Reviewer 2, point 5).

Reviewer 2 observed that the validity-cost frontier is characterised only against a
synthetic gold standard, so the configuration a resource-limited site would actually
deploy has no faculty-anchored evidence behind it. This script closes that gap without
collecting any new human data: it re-scores the SAME 162 real student transcripts with a
smaller or quantized model and computes agreement against the SAME blinded faculty
consensus used for the primary endpoint.

For each configuration it runs the two existing, already-validated stages:
  1. scripts/score_real_encounters.py  -> data/encounters/real_students_<tag>/
  2. scripts/validity_real_students.py -> results/phase_faculty_anchored_frontier/<tag>/

Nothing here re-implements scoring or statistics; both stages are invoked as-is so the
numbers are produced by the same code path that produced the primary endpoint.

Usage:
  uv run python scripts/faculty_anchored_frontier.py --configs qwen2.5:7b-instruct-q8_0
  uv run python scripts/faculty_anchored_frontier.py --configs mock   # offline dry run, no model
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger("aivmt.faculty_frontier")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "transcripts" / "real_students"
FAC = ROOT / "data" / "faculty_ratings_real.csv"
RESULTS = ROOT / "results" / "phase_faculty_anchored_frontier"


def _tag(model: str) -> str:
    """Filesystem-safe tag for a model id."""
    return model.replace(":", "_").replace("/", "_").replace(".", "")


def run_config(model: str, base_url: str, python: str) -> dict:
    """Score all real transcripts with ``model`` and compute faculty agreement."""
    tag = _tag(model)
    enc = ROOT / "data" / "encounters" / f"real_students_{tag}"
    out = RESULTS / tag
    out.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    logger.info("[%s] scoring %s transcripts", model, len(list(SRC.glob("*.json"))))
    subprocess.run(
        [python, str(ROOT / "scripts" / "score_real_encounters.py"),
         "--src", str(SRC), "--out", str(enc), "--model", model, "--base-url", base_url],
        check=True, cwd=ROOT,
    )
    score_s = time.perf_counter() - t0

    logger.info("[%s] computing faculty agreement", model)
    subprocess.run(
        [python, str(ROOT / "scripts" / "validity_real_students.py"),
         "--enc", str(enc), "--fac", str(FAC), "--out", str(out)],
        check=True, cwd=ROOT,
    )

    suite = json.loads((out / "validity_suite.json").read_text(encoding="utf-8"))
    return {"model": model, "tag": tag, "scoring_seconds": round(score_s, 1),
            "encounters_dir": str(enc), "results_dir": str(out), "suite": suite}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--configs", nargs="+", required=True, help="ollama model ids to evaluate")
    ap.add_argument("--base-url", default="http://localhost:11434/v1")
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()

    if not FAC.is_file():
        raise SystemExit(f"FAIL: faculty ratings not found at {FAC}")
    n_src = len(list(SRC.glob("*.json")))
    if n_src == 0:
        raise SystemExit(f"FAIL: no transcripts in {SRC}")
    logger.info("faculty file: %s | transcripts: %d", FAC.name, n_src)

    RESULTS.mkdir(parents=True, exist_ok=True)
    rows = []
    for model in args.configs:
        try:
            rows.append(run_config(model, args.base_url, args.python))
        except subprocess.CalledProcessError as exc:
            logger.error("[%s] FAILED: %s", model, exc)
            rows.append({"model": model, "error": str(exc)})

    (RESULTS / "frontier.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = ["# Faculty-anchored frontier (real encounters, real faculty consensus)", "",
             "Same 162 real student transcripts and the same three blinded faculty as the",
             "primary endpoint; only the scoring model differs. No new human data.", "",
             "| Configuration | overall ICC(2,1) | 95% CI | history_completion | scoring time |",
             "|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['model']} | FAILED | - | - | - |")
            continue
        icc = r["suite"]["system_vs_consensus_icc"]
        ov = icc["overall"]["icc2_1"]
        hc = icc.get("history_completion", {}).get("icc2_1", {})
        lines.append(
            f"| `{r['model']}` | {ov['point']:.3f} | [{ov['ci_lower']:.3f}, {ov['ci_upper']:.3f}] "
            f"| {hc.get('point', float('nan')):.3f} | {r['scoring_seconds']:.0f} s |")
    (RESULTS / "frontier.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
