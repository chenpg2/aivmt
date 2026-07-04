"""Ingest device-archived AIVMT encounters into scorer-ready transcripts.

The embodied device POSTs each finished encounter to the server's
``/aivmt/encounter`` endpoint, which archives one JSON per encounter under
``AIVMT_ENCOUNTER_DIR`` (default ``data/aivmt_encounters/``). Those files use the
device wire format: ``transcript`` as ``[{role, text}]`` turns,
``telemetry.duration_seconds``, no ``language`` and no ``provenance``.

This tool converts each archived encounter into the canonical transcript JSON
that the scoring pipeline reads (``turns`` with ``speaker``/``t_start``/``t_end``,
``telemetry.duration_s``), stamps ``provenance = "real_student"``, fills
``language`` from the case definition, and writes the result under
``data/transcripts/real_students/`` keyed by the device filename stem. These are
raw (unscored) transcripts; the scorer then turns each into a scored encounter,
kept separate from the Phase 1 synthetic set so the two are never pooled.

Real student audio (``.wav``) is captured and stored separately on the local
collection station and is never copied or committed. If a ``.wav`` with the same
stem sits next to the archived encounter, its path is recorded under
``audio_ref`` for the ASR word-error-rate subset; the audio itself is not moved.

Usage:
  uv run python scripts/ingest_real_encounters.py
  uv run python scripts/ingest_real_encounters.py --src data/aivmt_encounters \\
      --out data/transcripts/real_students
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

from aivmt.cases import load_case

logger = logging.getLogger("aivmt.ingest")

ROOT = Path(__file__).resolve().parents[1]
CONF_CASE = ROOT / "conf" / "case"

#: Device 'role' values; they are identical to the scorer's 'speaker' enum.
_VALID_ROLES = {"student", "patient"}


def _language_for_case(case_id: str) -> str:
    """Resolve the encounter language from the case file (fail loud if absent)."""
    case_path = CONF_CASE / f"{case_id}.yaml"
    if not case_path.exists():
        raise FileNotFoundError(
            f"case file not found for case_id={case_id!r}: {case_path}. "
            "Real-student ingest requires the case definition to resolve language."
        )
    return load_case(case_path).language


def convert_encounter(
    device: dict, encounter_id: str, audio_ref: Optional[str] = None
) -> dict:
    """Convert one device-wire encounter dict into the canonical transcript dict.

    Args:
        device: Parsed device archive JSON (participant_code, case_id, transcript, ...).
        encounter_id: Stable id for the encounter (the device filename stem).
        audio_ref: Path to a paired .wav, if one was found next to the archive file.

    Returns:
        A dict in the canonical Transcript shape plus provenance/audit fields.

    Raises:
        ValueError: On a missing required field or an unrecognised turn role.
    """
    for field in ("participant_code", "case_id", "transcript"):
        if field not in device:
            raise ValueError(f"encounter {encounter_id}: missing required field {field!r}")

    case_id = str(device["case_id"]).strip()
    raw_turns = device["transcript"]
    if not isinstance(raw_turns, list) or not raw_turns:
        raise ValueError(f"encounter {encounter_id}: transcript must be a non-empty list")

    turns = []
    for i, turn in enumerate(raw_turns):
        role = turn.get("role") if isinstance(turn, dict) else None
        if role not in _VALID_ROLES:
            raise ValueError(
                f"encounter {encounter_id} turn {i}: role={role!r} not in {sorted(_VALID_ROLES)}"
            )
        turns.append(
            {
                "speaker": role,  # device 'role' == scorer 'speaker'
                "text": str(turn.get("text", "")),
                "t_start": float(turn.get("t_start", 0.0)),
                "t_end": float(turn.get("t_end", 0.0)),
            }
        )

    tel = device.get("telemetry") or {}
    telemetry = {
        # device wire key is duration_seconds; the canonical schema key is duration_s
        "duration_s": float(tel.get("duration_s", tel.get("duration_seconds", 0.0)) or 0.0),
        "n_student_questions": int(tel.get("n_student_questions", 0) or 0),
        "n_voluntary_repeats": int(tel.get("n_voluntary_repeats", 0) or 0),
    }

    record = {
        "encounter_id": encounter_id,
        "case_id": case_id,
        "language": _language_for_case(case_id),
        "turns": turns,
        "telemetry": telemetry,
        "provenance": "real_student",
        "participant_code": str(device["participant_code"]).strip(),
        "source_meta": device.get("meta", {}),
        "received_at": device.get("received_at"),
    }
    if audio_ref:
        record["audio_ref"] = audio_ref
    return record


def ingest(src: Path, out: Path) -> list[Path]:
    """Convert every device archive JSON in ``src`` into ``out``; return written paths."""
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    files = sorted(p for p in src.glob("*.json") if not p.name.endswith(".tmp"))
    if not files:
        logger.warning("no device encounters found under %s", src)
        return written

    for f in files:
        try:
            device = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("skip %s: cannot read JSON (%s)", f.name, exc)
            continue
        encounter_id = f.stem
        wav = f.with_suffix(".wav")
        audio_ref = str(wav) if wav.exists() else None
        try:
            record = convert_encounter(device, encounter_id, audio_ref)
        except (ValueError, FileNotFoundError) as exc:
            logger.error("skip %s: %s", f.name, exc)
            continue
        dest = out / f"{encounter_id}.json"
        dest.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(dest)
        logger.info(
            "ingested %s -> %s (%d turns, %.0fs, audio=%s)",
            f.name,
            dest.name,
            len(record["turns"]),
            record["telemetry"]["duration_s"],
            "yes" if audio_ref else "no",
        )

    logger.info("ingested %d/%d encounters into %s", len(written), len(files), out)
    return written


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(
        description="Ingest device AIVMT encounters into scorer-ready transcripts."
    )
    ap.add_argument(
        "--src",
        default=str(ROOT / "data" / "aivmt_encounters"),
        help="device archive dir (the server's AIVMT_ENCOUNTER_DIR)",
    )
    ap.add_argument(
        "--out",
        default=str(ROOT / "data" / "transcripts" / "real_students"),
        help="output dir for canonical (unscored) real-student transcripts",
    )
    args = ap.parse_args()
    ingest(Path(args.src), Path(args.out))


if __name__ == "__main__":
    main()
