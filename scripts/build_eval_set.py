"""Build the path-A zh OB/GYN eval set into ``data/eval_transcripts/``.

This is the FIRST step of the path-A real-data lane: it materializes the
deterministic, case-grounded synthetic transcript set the Stream-A blinded
faculty tool serves (and that ``score_eval_set.py`` later system-scores). Every
clinical fact comes from the three collaborator-reviewed zh OB/GYN case YAMLs;
every record is tagged ``provenance='synthetic'`` and carries a designed
(reference-only) quality the faculty tool MUST NOT surface.

The seed is read from ``configs/seed.yaml`` (never hardcoded). Output is
quality-diverse over the whole ladder and stable across runs.

Usage:
    uv run python scripts/build_eval_set.py [--per-case N] [--out DIR]

Defaults: ``--per-case 14`` (3 cases -> 42 transcripts), ``--out data/eval_transcripts``.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from omegaconf import OmegaConf

from aivmt.evalset import build_eval_set, default_eval_dir, load_obgyn_cases, write_eval_set

logger = logging.getLogger("aivmt.scripts.build_eval_set")

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_seed() -> int:
    """Read the project seed from ``configs/seed.yaml`` (single source of truth)."""
    cfg = OmegaConf.load(_PROJECT_ROOT / "configs" / "seed.yaml")
    return int(cfg.seed)  # type: ignore[attr-defined]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Build the path-A zh OB/GYN eval set.")
    parser.add_argument(
        "--per-case", type=int, default=14,
        help="transcripts generated per case (default 14 -> 42 total over 3 cases).",
    )
    parser.add_argument(
        "--out", type=Path, default=default_eval_dir(),
        help="output directory for the generated transcript JSONs.",
    )
    args = parser.parse_args()

    seed = load_seed()
    cases = load_obgyn_cases()
    dataset = build_eval_set(cases, seed=seed, per_case=args.per_case)
    written = write_eval_set(dataset, args.out)

    qualities = sorted({round(g.designed_quality, 3) for g in dataset})
    logger.info(
        "DONE: %d transcripts (%d/case x %d cases) -> %s",
        len(written), args.per_case, len(cases), args.out,
    )
    logger.info("designed-quality spread (reference only, blinded from faculty): %s", qualities)
    logger.info("provenance=synthetic on every record; no clinical fact is invented.")


if __name__ == "__main__":
    main()
