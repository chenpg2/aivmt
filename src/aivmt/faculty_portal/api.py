"""JSON API for the blinded faculty-scoring portal.

Endpoints (all under ``/api``):

* ``GET  /session/{rater_id}``  — start/resume: progress + the rater's order,
* ``GET  /next/{rater_id}``     — the next unscored transcript (blinded) or null,
* ``GET  /progress/{rater_id}`` — ``{scored, total, remaining}`` for the rater,
* ``POST /score``               — validate + append one rating row.

Blinding is a hard requirement and is enforced structurally: the only transcript
payload the API can build is :meth:`TranscriptStore.blinded_payload`, which has
no score/gold/condition field to leak. The API never reads system scores.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from .scoring import validate_submission
from .storage import (
    DuplicateRatingError,
    RatingStore,
    TranscriptStore,
    UnknownEncounterError,
)

logger = logging.getLogger(__name__)

__all__ = ["build_router"]


def _progress(transcripts: TranscriptStore, ratings: RatingStore, rater_id: str) -> dict[str, Any]:
    ordered = transcripts.ordered_ids(rater_id)
    scored = ratings.scored_encounter_ids(rater_id)
    remaining = [eid for eid in ordered if eid not in scored]
    return {
        "rater_id": rater_id,
        "total": len(ordered),
        "scored": len(ordered) - len(remaining),
        "remaining": len(remaining),
        "next_encounter_id": remaining[0] if remaining else None,
    }


def build_router(transcripts: TranscriptStore, ratings: RatingStore) -> APIRouter:
    """Build the API router bound to one transcript set and ratings file."""
    router = APIRouter()

    @router.get("/session/{rater_id}")
    def session(rater_id: str) -> dict[str, Any]:
        rid = rater_id.strip()
        if not rid:
            raise HTTPException(status_code=422, detail="评分者编号 rater_id 不能为空")
        return _progress(transcripts, ratings, rid)

    @router.get("/progress/{rater_id}")
    def progress(rater_id: str) -> dict[str, Any]:
        rid = rater_id.strip()
        if not rid:
            raise HTTPException(status_code=422, detail="评分者编号 rater_id 不能为空")
        return _progress(transcripts, ratings, rid)

    @router.get("/next/{rater_id}")
    def next_transcript(rater_id: str) -> dict[str, Any]:
        rid = rater_id.strip()
        if not rid:
            raise HTTPException(status_code=422, detail="评分者编号 rater_id 不能为空")
        prog = _progress(transcripts, ratings, rid)
        eid = prog["next_encounter_id"]
        if eid is None:
            return {"done": True, "progress": prog, "transcript": None}
        return {
            "done": False,
            "progress": prog,
            "transcript": transcripts.blinded_payload(eid),
        }

    @router.post("/score")
    def submit_score(
        submission: dict[str, Any] = Body(...),
        overwrite: bool = Body(False),
    ) -> dict[str, Any]:
        validated, issues = validate_submission(submission)
        if validated is None:
            raise HTTPException(
                status_code=422,
                detail={"errors": [issue.to_json() for issue in issues]},
            )
        # The encounter must belong to the served set — fail loud otherwise.
        try:
            transcripts.load(validated.encounter_id)
        except UnknownEncounterError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        try:
            ratings.append(validated.to_row(), overwrite=overwrite)
        except DuplicateRatingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"ok": True, "progress": _progress(transcripts, ratings, validated.rater_id)}

    return router
