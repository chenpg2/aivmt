"""Batch-score ingested real-student transcripts with the local model.

Reads the canonical (unscored) transcripts produced by
``scripts/ingest_real_encounters.py`` (default ``data/transcripts/real_students/``),
scores each with the configured model through the standard ``ScoringPipeline``, and
writes one scored encounter JSON per transcript (``aivmt.dataio.encounter_to_dict``
shape) to a Phase-2 output dir (default ``data/encounters/real_students/``), kept
separate from the Phase 1 synthetic set so the two are never pooled.

The case is loaded per transcript from its ``case_id`` (``conf/case/{case_id}.yaml``).
Scoring decodes at temperature 0 for determinism. One encounter's model error is
logged and skipped so it never kills the batch. Use ``--model mock`` for an offline
dry run of the full flow without a model.

Usage:
  uv run --extra serve python scripts/score_real_encounters.py \\
      --model qwen2.5:14b --base-url http://localhost:11434/v1
  uv run python scripts/score_real_encounters.py --model mock   # offline dry run
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from aivmt.cases import load_case
from aivmt.dataio import load_transcript, save_encounter
from aivmt.llm import LLMFactory
from aivmt.pipeline import ScoringPipeline
from aivmt.utils import set_seed

logger = logging.getLogger("aivmt.score_real")

ROOT = Path(__file__).resolve().parents[1]
CONF_CASE = ROOT / "conf" / "case"


def _build_llm(model: str, base_url: str):
    """Local ollama client by default; the 'mock' model gives an offline dry run."""
    if model == "mock":
        return LLMFactory("mock")
    return LLMFactory(
        "openai_compat",
        model_id=model,
        base_url=base_url,
        api_key="ollama",
        temperature=0.0,
    )


def score_dir(src: Path, out: Path, model: str, base_url: str) -> list[Path]:
    """Score every transcript in ``src``; write scored encounters to ``out``."""
    out.mkdir(parents=True, exist_ok=True)
    llm = _build_llm(model, base_url)
    pipeline = ScoringPipeline(llm)

    written: list[Path] = []
    files = sorted(src.glob("*.json"))
    if not files:
        logger.warning("no transcripts found under %s", src)
        return written

    for f in files:
        try:
            transcript = load_transcript(f)
        except (OSError, KeyError, ValueError) as exc:
            logger.error("skip %s: cannot load transcript (%s)", f.name, exc)
            continue
        case_path = CONF_CASE / f"{transcript.case_id}.yaml"
        if not case_path.exists():
            logger.error("skip %s: case file missing %s", f.name, case_path)
            continue
        case = load_case(case_path)
        try:
            result = pipeline.run(case, transcript)
        except Exception as exc:  # noqa: BLE001 - one model error must not kill the batch
            logger.error("skip %s: scoring failed (%s)", f.name, exc)
            continue
        dest = save_encounter(result, transcript, out / f"{transcript.encounter_id}.json")
        written.append(dest)
        logger.info("scored %s -> %s (overall=%.3f)", f.name, dest.name, result.score.overall)

    logger.info("scored %d/%d transcripts into %s", len(written), len(files), out)
    return written


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Batch-score ingested real-student transcripts.")
    ap.add_argument(
        "--src",
        default=str(ROOT / "data" / "transcripts" / "real_students"),
        help="dir of ingested (unscored) real-student transcripts",
    )
    ap.add_argument(
        "--out",
        default=str(ROOT / "data" / "encounters" / "real_students"),
        help="output dir for scored encounters (Phase 2; separate from Phase 1)",
    )
    ap.add_argument("--model", default="qwen2.5:14b", help="ollama model id, or 'mock' for offline")
    ap.add_argument("--base-url", default="http://localhost:11434/v1")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    set_seed(args.seed)
    score_dir(Path(args.src), Path(args.out), args.model, args.base_url)


if __name__ == "__main__":
    main()
