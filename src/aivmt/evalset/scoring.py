"""System-score the eval set into the ``data/encounters/`` layout the validity suite reads.

This bridges the path-A apparatus to ``PhaseScoringValidity``: it runs the
production scoring pipeline over each eval transcript and writes one encounter
JSON per transcript via :func:`aivmt.dataio.save_encounter`, exactly the format
``PhaseScoringValidity._load_system_scores`` / ``check_scoring_validity_inputs``
expect (overall + history_completion + reasoning + the five SEGUE domains).

The LLM client is injected so the same code path runs offline on the
deterministic mock (for verification) and on the real local model (deferred while
the GPU is busy). It also exports a blank blinded faculty-rating sheet for the
scored encounter_ids so the rating workflow has a CSV fallback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Union

from ..case_schema import ClinicalCase
from ..dataio import export_faculty_rating_sheet, save_encounter
from ..llm.base import BaseLLMClient
from ..pipeline import ScoringPipeline
from ..schemas import ScoringResult, Transcript

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

__all__ = ["ScoredEncounter", "score_eval_set", "REAL_SCORE_COMMAND"]

#: The exact deferred real-model command (GPU is busy — verify on mock first).
REAL_SCORE_COMMAND = (
    "uv run --extra serve python scripts/score_eval_set.py "
    "--model gpt-oss:20b --base-url http://localhost:11434/v1"
)


@dataclass(frozen=True)
class ScoredEncounter:
    """A scored eval encounter plus the path its JSON was written to."""

    encounter_id: str
    case_id: str
    overall: float
    path: Path


def _case_by_id(cases: Sequence[ClinicalCase]) -> dict[str, ClinicalCase]:
    return {c.case_id: c for c in cases}


def score_eval_set(
    transcripts: Sequence[Transcript],
    cases: Sequence[ClinicalCase],
    llm: BaseLLMClient,
    out_dir: PathLike,
) -> list[ScoredEncounter]:
    """Score every transcript with ``llm`` and write its encounter JSON to ``out_dir``.

    Each transcript's ``case_id`` must resolve to one of ``cases`` (fail-loud: no
    silent skip of an unmatched transcript).

    Returns the scored encounters in input order.
    """
    by_id = _case_by_id(cases)
    pipeline = ScoringPipeline(llm)
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)

    scored: list[ScoredEncounter] = []
    for tx in transcripts:
        case = by_id.get(tx.case_id)
        if case is None:
            raise KeyError(
                f"transcript {tx.encounter_id!r} references unknown case_id {tx.case_id!r}; "
                f"known cases: {sorted(by_id)}"
            )
        result: ScoringResult = pipeline.run(case.to_case(), tx)
        path = save_encounter(result, tx, base / f"{tx.encounter_id}.json")
        scored.append(
            ScoredEncounter(
                encounter_id=tx.encounter_id,
                case_id=tx.case_id,
                overall=result.score.overall,
                path=path,
            )
        )
        logger.debug("scored %s -> overall=%.3f", tx.encounter_id, result.score.overall)

    logger.info("scored %d eval encounters -> %s", len(scored), base)
    return scored


def export_blank_faculty_sheet(scored: Sequence[ScoredEncounter], path: PathLike) -> Path:
    """Write a blank blinded faculty-rating sheet for the scored encounter_ids."""
    return export_faculty_rating_sheet([s.encounter_id for s in scored], path)
