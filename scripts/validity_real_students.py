"""Compute the Phase 2 (real student) validity suite, separate from Phase 1.

Runs the SAME validated agreement suite as the ``phase_scoring_validity`` harness
phase (ICC(2,1) and ICC(2,k), per-domain agreement, Bland-Altman, generalizability
theory, decision consistency) but pointed at the REAL-STUDENT scored encounters and
the REAL faculty ratings, writing artifacts to a separate results dir so the Phase 1
synthetic estimate is never pooled with Phase 2.

This subclasses the registered phase and only overrides its input/output paths, so
the agreement computation, input contract, and artifact writer are reused verbatim.

Inputs:
  --enc   dir of scored real-student encounters (default data/encounters/real_students/)
  --fac   real faculty ratings CSV (long format, >= 2 raters)
  --out   results dir (default results/phase_scoring_validity_real/)

Usage:
  uv run python scripts/validity_real_students.py --fac data/faculty_ratings_real.csv
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# ``harness`` is in-tree orchestration (not pip-installed); put the repo root on the
# path before importing it, mirroring what conftest.py does for the test suite.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.registry import SEED, PhaseScoringValidity  # noqa: E402

logger = logging.getLogger("aivmt.validity_real")


class RealStudentValidity(PhaseScoringValidity):
    """Phase 2: the validity suite pointed at the real-student set."""

    def __init__(self, enc_dir: Path, fac_csv: Path, out_dir: Path) -> None:
        self.inputs = [Path(enc_dir), Path(fac_csv)]
        self.outputs = [Path(out_dir) / "validity_suite.json"]
        self.seed = SEED


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Phase 2 real-student validity suite.")
    ap.add_argument(
        "--enc",
        default=str(ROOT / "data" / "encounters" / "real_students"),
        help="dir of scored real-student encounters",
    )
    ap.add_argument(
        "--fac",
        default=str(ROOT / "data" / "faculty_ratings_real.csv"),
        help="real faculty ratings CSV (long format, >= 2 raters)",
    )
    ap.add_argument(
        "--out",
        default=str(ROOT / "results" / "phase_scoring_validity_real"),
        help="results dir for the Phase 2 validity artifacts",
    )
    args = ap.parse_args()

    phase = RealStudentValidity(Path(args.enc), Path(args.fac), Path(args.out))
    result = phase.run()

    from aivmt.metrics import headline_metrics

    head = headline_metrics(result)
    logger.info("Phase 2 (real student) validity:")
    for key, value in head.items():
        logger.info("  %s = %s", key, value)
    print(json.dumps({"phase2_real_student": head}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
