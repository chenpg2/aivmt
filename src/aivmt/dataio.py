"""Encounter data capture & export (WS-F).

- Persist a scored encounter (transcript + telemetry + scores + feedback) as JSON.
- Export a blinded faculty-rating sheet (CSV) — system scores withheld.
- Pair system vs faculty overall scores into the (n, 2) matrix for ICC (H1).
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Sequence, Union

import numpy as np

from .schemas import ScoringResult, Telemetry, Transcript, Turn

PathLike = Union[str, Path]

#: Columns a faculty rater fills in (blinded to the system's scores).
FACULTY_SHEET_FIELDS = [
    "encounter_id",
    "rater_id",
    "set_the_stage",
    "elicit_information",
    "give_information",
    "understand_perspective",
    "end_encounter",
    "history_completion",
    "reasoning",
    "overall",
    "notes",
]


def encounter_to_dict(result: ScoringResult, transcript: Transcript) -> dict:
    """Serialize a scored encounter to a plain dict."""
    return {
        "encounter_id": result.encounter_id,
        "case_id": transcript.case_id,
        "language": transcript.language,
        "model_id": result.model_id,
        "transcript": asdict(transcript),
        "score": asdict(result.score),
        "feedback": asdict(result.feedback),
    }


def save_encounter(result: ScoringResult, transcript: Transcript, path: PathLike) -> Path:
    """Write a scored encounter as UTF-8 JSON (Chinese preserved)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(encounter_to_dict(result, transcript), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out


def load_encounter(path: PathLike) -> dict:
    """Load a saved encounter dict."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def transcript_from_dict(data: dict) -> Transcript:
    """Rebuild a Transcript from its serialized dict."""
    turns = tuple(
        Turn(
            speaker=t["speaker"],
            text=t["text"],
            t_start=float(t.get("t_start", 0.0)),
            t_end=float(t.get("t_end", 0.0)),
        )
        for t in data["turns"]
    )
    tel = data.get("telemetry") or {}
    telemetry = Telemetry(
        duration_s=float(tel.get("duration_s", 0.0)),
        n_student_questions=int(tel.get("n_student_questions", 0)),
        n_voluntary_repeats=int(tel.get("n_voluntary_repeats", 0)),
    )
    return Transcript(
        encounter_id=data["encounter_id"],
        case_id=data["case_id"],
        language=data["language"],
        turns=turns,
        telemetry=telemetry,
    )


def export_faculty_rating_sheet(encounter_ids: Sequence[str], path: PathLike) -> Path:
    """Write a blank CSV for blinded faculty scoring (one row per encounter)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FACULTY_SHEET_FIELDS)
        writer.writeheader()
        for eid in encounter_ids:
            writer.writerow({"encounter_id": eid})
    return out


def build_pairs(system_overall: Sequence[float], faculty_overall: Sequence[float]) -> np.ndarray:
    """Stack paired overall scores into an (n, 2) matrix for ICC."""
    sys_arr = np.asarray(system_overall, dtype=float)
    fac_arr = np.asarray(faculty_overall, dtype=float)
    if sys_arr.shape != fac_arr.shape or sys_arr.ndim != 1 or sys_arr.size == 0:
        raise ValueError("system_overall and faculty_overall must be equal-length 1-D sequences")
    return np.column_stack([sys_arr, fac_arr])


def save_transcript(transcript: Transcript, path: PathLike) -> Path:
    """Persist a raw (unscored) transcript as UTF-8 JSON (from the collection front-end)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asdict(transcript), ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def load_transcript(path: PathLike) -> Transcript:
    """Load a raw transcript saved by save_transcript."""
    return transcript_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
