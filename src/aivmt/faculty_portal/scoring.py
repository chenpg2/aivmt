"""Server-side validation of a faculty score submission.

Every numeric domain must be a finite float in ``[0, 1]`` (matching the system's
scale). Validation fails loud — a single out-of-range or non-numeric field makes
the whole submission invalid and nothing is written (the API maps this to 422).
No silent clamping, no fallback defaults: a bad value is a data-quality signal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..dataio import FACULTY_SHEET_FIELDS
from .storage import SCORE_FIELDS

__all__ = ["ScoreIssue", "ValidatedScore", "validate_submission"]


@dataclass(frozen=True)
class ScoreIssue:
    """One validation error, addressed to a specific field."""

    field: str
    message: str

    def to_json(self) -> dict[str, str]:
        return {"field": self.field, "message": self.message}


@dataclass(frozen=True)
class ValidatedScore:
    """A submission proven to be a complete, in-range faculty rating."""

    encounter_id: str
    rater_id: str
    scores: dict[str, float]
    notes: str

    def to_row(self) -> dict[str, str]:
        """Render to a CSV row in exact :data:`FACULTY_SHEET_FIELDS` order."""
        row = {"encounter_id": self.encounter_id, "rater_id": self.rater_id, "notes": self.notes}
        for field in SCORE_FIELDS:
            # str() of a float keeps the value exactly; numeric loaders re-parse it.
            row[field] = repr(self.scores[field])
        return {field: row.get(field, "") for field in FACULTY_SHEET_FIELDS}


def _coerce_unit(value: Any) -> float:
    """Parse a value that must be a finite float in [0, 1]; raise on violation."""
    if isinstance(value, bool):  # bool is an int subclass — reject it explicitly
        raise ValueError("必须是 0 到 1 之间的数值")
    try:
        num = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("必须是数值") from exc
    if not math.isfinite(num):
        raise ValueError("必须是有限数值")
    if num < 0.0 or num > 1.0:
        raise ValueError("必须在 0 到 1 之间")
    return num


def validate_submission(payload: dict[str, Any]) -> tuple[ValidatedScore | None, list[ScoreIssue]]:
    """Validate a raw submission dict.

    Returns ``(validated, [])`` on success or ``(None, issues)`` with one issue
    per offending field. Identity fields (``encounter_id``, ``rater_id``) must be
    non-empty strings; every domain in :data:`SCORE_FIELDS` must be in ``[0, 1]``.
    """
    issues: list[ScoreIssue] = []

    encounter_id = str(payload.get("encounter_id", "")).strip()
    rater_id = str(payload.get("rater_id", "")).strip()
    if not encounter_id:
        issues.append(ScoreIssue("encounter_id", "缺少 encounter_id"))
    if not rater_id:
        issues.append(ScoreIssue("rater_id", "缺少评分者编号 rater_id"))

    scores: dict[str, float] = {}
    for field in SCORE_FIELDS:
        if field not in payload or payload[field] is None or payload[field] == "":
            issues.append(ScoreIssue(field, "该项必填"))
            continue
        try:
            scores[field] = _coerce_unit(payload[field])
        except ValueError as exc:
            issues.append(ScoreIssue(field, str(exc)))

    notes = str(payload.get("notes", "") or "")

    if issues:
        return None, issues
    return ValidatedScore(encounter_id, rater_id, scores, notes), []
