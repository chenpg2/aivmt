"""Storage for the blinded faculty-scoring portal: transcripts in, ratings out.

Two read/write concerns, kept separate and side-effect-honest:

* :class:`TranscriptStore` — read-only access to a directory of de-identified
  transcripts (the eval set Stream B produces). It exposes ONLY transcript text
  and ids; it never reads, derives, or surfaces a system score, gold label, or
  condition. Blinding is structural: the dict this returns simply has no score
  field to leak.
* :class:`RatingStore` — append-one-row access to ``data/faculty_ratings.csv``
  in the exact :data:`aivmt.dataio.FACULTY_SHEET_FIELDS` order. Appends are
  atomic (rewrite a temp file + ``os.replace``) and refuse a duplicate
  ``(rater_id, encounter_id)`` pair unless an explicit re-score is requested.

All raters are served encounters in one FIXED canonical order (by case, then
encounter_id) that matches the offline scoring packet, so an operator entering
an off-network faculty's paper scores walks the web tool in lock-step with the PDF.
"""

from __future__ import annotations

import csv
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

from ..dataio import FACULTY_SHEET_FIELDS, transcript_from_dict
from ..schemas import Transcript

logger = logging.getLogger(__name__)

__all__ = [
    "FacultyPortalError",
    "DuplicateRatingError",
    "UnknownEncounterError",
    "TranscriptStore",
    "RatingStore",
    "default_transcript_dir",
    "default_ratings_csv",
    "TRANSCRIPT_DIR_ENV",
    "RATINGS_CSV_ENV",
]

#: Numeric scoring fields the rater fills (all constrained to [0, 1]).
SCORE_FIELDS: tuple[str, ...] = tuple(
    f for f in FACULTY_SHEET_FIELDS if f not in ("encounter_id", "rater_id", "notes")
)

#: Environment variable overriding the default transcript directory.
TRANSCRIPT_DIR_ENV = "AIVMT_EVAL_TRANSCRIPT_DIR"
#: Environment variable overriding the default ratings CSV path.
RATINGS_CSV_ENV = "AIVMT_FACULTY_RATINGS_CSV"


class FacultyPortalError(RuntimeError):
    """Base error for faculty-portal storage failures."""


class DuplicateRatingError(FacultyPortalError):
    """Raised when a (rater_id, encounter_id) pair already has a rating."""


class UnknownEncounterError(FacultyPortalError):
    """Raised when a rating is submitted for an encounter not in the served set."""


def default_transcript_dir() -> Path:
    """Resolve the eval transcript directory: env override or ``data/eval_transcripts``."""
    return Path(os.environ.get(TRANSCRIPT_DIR_ENV, "data/eval_transcripts"))


def default_ratings_csv() -> Path:
    """Resolve the faculty ratings CSV: env override or ``data/faculty_ratings.csv``."""
    return Path(os.environ.get(RATINGS_CSV_ENV, "data/faculty_ratings.csv"))


#: Canonical case order for serving — MUST match the offline scoring packet
#: (``scripts/build_scoring_packet.py`` CASE_ORDER) so the web tool serves encounters in the SAME
#: order the off-network faculty see on paper, making operator data-entry a straight sequential pass.
CANONICAL_CASE_ORDER: tuple[str, ...] = (
    "obgyn_ectopic_zh_01",
    "obgyn_aub_zh_01",
    "obgyn_vaginitis_zh_01",
)


def _canonical_key(encounter_id: str) -> tuple[int, str]:
    """Sort key matching the packet: by case (CANONICAL_CASE_ORDER), then by encounter_id.

    The case is parsed from the id (``eval_<case_id>_<nn>``); an unknown case sorts last but stays
    deterministic by id.
    """
    case = encounter_id[len("eval_"):].rsplit("_", 1)[0] if encounter_id.startswith("eval_") else ""
    rank = CANONICAL_CASE_ORDER.index(case) if case in CANONICAL_CASE_ORDER else len(CANONICAL_CASE_ORDER)
    return (rank, encounter_id)


@dataclass(frozen=True)
class TranscriptStore:
    """Read-only access to a directory of de-identified transcripts.

    Raises:
        FileNotFoundError: if the directory does not exist (fail loud — the
            portal never silently creates or relocates the transcript set).
    """

    transcript_dir: Path
    base_seed: int

    def __post_init__(self) -> None:
        if not self.transcript_dir.is_dir():
            raise FileNotFoundError(
                f"评分转写目录不存在 (transcript directory not found): {self.transcript_dir}"
            )

    def _path_for(self, encounter_id: str) -> Optional[Path]:
        for path in self._paths():
            if self._encounter_id(path) == encounter_id:
                return path
        return None

    def _paths(self) -> list[Path]:
        return sorted(self.transcript_dir.glob("*.json"))

    @staticmethod
    def _encounter_id(path: Path) -> str:
        data = TranscriptStore._read_raw(path)
        eid = data.get("encounter_id")
        if not isinstance(eid, str) or not eid:
            raise FacultyPortalError(
                f"转写文件缺少 encounter_id (missing encounter_id): {path.name}"
            )
        return eid

    @staticmethod
    def _read_raw(path: Path) -> dict[str, Any]:
        import json

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise FacultyPortalError(f"无法读取转写文件 {path.name}: {exc}") from exc
        if not isinstance(data, dict):
            raise FacultyPortalError(f"转写文件 {path.name} 顶层必须是对象 (object)")
        return data

    def encounter_ids(self) -> list[str]:
        """All encounter ids in canonical (filename-sorted) order."""
        return [self._encounter_id(p) for p in self._paths()]

    def ordered_ids(self, rater_id: str) -> list[str]:
        """Encounter ids in the FIXED canonical serving order (same for every rater).

        The order matches the offline scoring packet (by case, then encounter_id), so an operator
        entering an off-network faculty's paper scores walks the web tool in lock-step with the PDF.
        ``rater_id`` is accepted for interface stability but no longer permutes the order. (Order
        effects on independent per-transcript faculty ratings are negligible; sequential parity with
        the packet matters more for correct data entry.)
        """
        return sorted(self.encounter_ids(), key=_canonical_key)

    def load(self, encounter_id: str) -> Transcript:
        """Load one transcript as a :class:`Transcript` (text + turns only)."""
        path = self._path_for(encounter_id)
        if path is None:
            raise UnknownEncounterError(f"转写不存在 (unknown encounter): {encounter_id}")
        return transcript_from_dict(self._read_raw(path))

    def blinded_payload(self, encounter_id: str) -> dict[str, Any]:
        """Blinded transcript payload for the rater: ids + turns ONLY.

        By construction this never contains a system score, gold label, model
        id, or condition — the only keys are de-identified transcript text.
        """
        transcript = self.load(encounter_id)
        return {
            "encounter_id": transcript.encounter_id,
            "case_id": transcript.case_id,
            "language": transcript.language,
            "turns": [
                {"speaker": t.speaker, "text": t.text} for t in transcript.turns
            ],
        }


@dataclass(frozen=True)
class RatingStore:
    """Append-only access to the faculty ratings CSV (atomic, dedup-aware)."""

    csv_path: Path

    def _read_rows(self) -> list[dict[str, str]]:
        if not self.csv_path.is_file():
            return []
        with self.csv_path.open(encoding="utf-8", newline="") as fh:
            return [dict(row) for row in csv.DictReader(fh)]

    def scored_encounter_ids(self, rater_id: str) -> set[str]:
        """Encounter ids this rater has already scored (a numeric row exists)."""
        scored: set[str] = set()
        for row in self._read_rows():
            if row.get("rater_id") != rater_id:
                continue
            eid = row.get("encounter_id")
            # A header-only blank row (export sheet) carries an encounter_id but no
            # scores; only count rows where this rater actually entered an overall.
            if eid and (row.get("overall") or "").strip() != "":
                scored.add(eid)
        return scored

    def has_rating(self, rater_id: str, encounter_id: str) -> bool:
        """True if a scored row for this (rater, encounter) already exists."""
        return encounter_id in self.scored_encounter_ids(rater_id)

    def append(self, row: dict[str, str], *, overwrite: bool = False) -> None:
        """Atomically append (or re-score) one row in FACULTY_SHEET_FIELDS order.

        Steps: read existing rows, drop a prior (rater, encounter) row only when
        ``overwrite`` is set, append the new row, then rewrite the whole file via
        a temp file + ``os.replace`` so a reader never sees a half-written CSV.

        Raises:
            DuplicateRatingError: an unscored re-submit without ``overwrite``.
            FacultyPortalError: on write failure.
        """
        rater_id = row["rater_id"]
        encounter_id = row["encounter_id"]
        rows = self._read_rows()

        existing = [
            r
            for r in rows
            if r.get("rater_id") == rater_id
            and r.get("encounter_id") == encounter_id
            and (r.get("overall") or "").strip() != ""
        ]
        if existing and not overwrite:
            raise DuplicateRatingError(
                f"该评分者已为本病例评分 (already scored): "
                f"rater={rater_id} encounter={encounter_id}"
            )

        kept = [
            r
            for r in rows
            if not (
                overwrite
                and r.get("rater_id") == rater_id
                and r.get("encounter_id") == encounter_id
            )
        ]
        kept.append({field: row.get(field, "") for field in FACULTY_SHEET_FIELDS})
        self._rewrite(kept)
        logger.info(
            "faculty_portal: recorded rating rater=%s encounter=%s", rater_id, encounter_id
        )

    def _rewrite(self, rows: list[dict[str, str]]) -> None:
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".faculty_ratings.", suffix=".tmp", dir=self.csv_path.parent
        )
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=FACULTY_SHEET_FIELDS)
                writer.writeheader()
                for row in rows:
                    writer.writerow({f: row.get(f, "") for f in FACULTY_SHEET_FIELDS})
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.csv_path)
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            raise FacultyPortalError(f"写入评分文件失败: {exc}") from exc


PathLike = Union[str, Path]
