"""System-score the path-A eval set into ``data/encounters/`` for PhaseScoringValidity.

Second step of the path-A lane: it loads the synthetic transcripts built by
``build_eval_set.py``, runs the production scoring pipeline over each, and writes
one encounter JSON per transcript in the exact format the SQ1 validity suite
ingests (``aivmt.dataio.encounter_to_dict``: overall + history_completion +
reasoning + five SEGUE domains). It also exports a blank blinded faculty-rating
sheet for the scored encounter_ids (CSV fallback for the rating workflow).

Two modes:
* ``--mock`` (default): the deterministic offline mock LLM — for verification and
  the no-network gates. Writes valid, loadable encounters without any model.
* real local model (``--model ... --base-url ...``): the actual scoring run. This
  is DEFERRED while the local Ollama GPU is busy; the exact command is printed by
  ``--mock`` so it can be run unchanged once the GPU frees up.

Usage:
    uv run python scripts/score_eval_set.py --mock
    uv run --extra serve python scripts/score_eval_set.py \
        --model gpt-oss:20b --base-url http://localhost:11434/v1   # DEFERRED (GPU busy)
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from aivmt.evalset import (
    REAL_SCORE_COMMAND,
    default_eval_dir,
    export_blank_faculty_sheet,
    load_eval_set,
    load_obgyn_cases,
    score_eval_set,
)
from aivmt.llm import LLMFactory
from aivmt.llm.base import BaseLLMClient

logger = logging.getLogger("aivmt.scripts.score_eval_set")

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _build_llm(args: argparse.Namespace) -> BaseLLMClient:
    """Construct the scoring LLM: deterministic mock, or the deferred real client."""
    if args.mock or not args.model:
        logger.info("using deterministic MOCK LLM (offline, no GPU).")
        return LLMFactory("mock")
    # Real local-model path. Imported lazily so the mock path needs no serve extra.
    from aivmt.llm.openai_compat import OpenAICompatClient  # noqa: PLC0415

    logger.info("using real local model %s @ %s", args.model, args.base_url)
    return OpenAICompatClient(
        model_id=args.model, base_url=args.base_url, api_key=args.api_key, temperature=0.0
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="System-score the path-A eval set.")
    parser.add_argument("--mock", action="store_true", help="use the deterministic offline mock LLM.")
    parser.add_argument("--model", type=str, default="", help="real local model id (e.g. gpt-oss:20b).")
    parser.add_argument(
        "--base-url", type=str, default="http://localhost:11434/v1",
        help="OpenAI-compatible base URL for the real local model.",
    )
    parser.add_argument("--api-key", type=str, default="ollama", help="API key for the local server.")
    parser.add_argument(
        "--eval-dir", type=Path, default=default_eval_dir(),
        help="input directory of generated eval transcripts.",
    )
    parser.add_argument(
        "--out", type=Path, default=_PROJECT_ROOT / "data" / "encounters",
        help="output directory of scored encounter JSONs (gitignored).",
    )
    parser.add_argument(
        "--faculty-sheet", type=Path,
        default=_PROJECT_ROOT / "data" / "faculty_rating_sheet.csv",
        help="path for the blank blinded faculty-rating sheet (CSV fallback).",
    )
    args = parser.parse_args()

    pairs = load_eval_set(args.eval_dir)
    transcripts = [tx for tx, _ in pairs]
    cases = load_obgyn_cases()
    llm = _build_llm(args)

    scored = score_eval_set(transcripts, cases, llm, args.out)
    sheet = export_blank_faculty_sheet(scored, args.faculty_sheet)

    logger.info("DONE: scored %d encounters -> %s", len(scored), args.out)
    logger.info("blank blinded faculty sheet -> %s", sheet)
    if args.mock or not args.model:
        logger.info(
            "NOTE: mock scores are deterministic placeholders. The REAL local-model run is "
            "DEFERRED (GPU busy). Run it unchanged once the GPU frees up:\n    %s",
            REAL_SCORE_COMMAND,
        )


if __name__ == "__main__":
    main()
