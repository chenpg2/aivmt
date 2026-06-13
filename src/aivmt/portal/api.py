"""JSON API for the case-entry portal.

Endpoints (all under ``/api``):

* ``GET  /cases``            — list cases with reused lint status,
* ``GET  /cases/{case_id}``  — raw case dict + lint findings,
* ``POST /validate``         — validate a draft (200 with ok/errors/warnings),
* ``POST /cases``            — atomic save; 422 invalid (nothing written), 409 exists,
* ``POST /preview``          — deterministic persona compile for all difficulties.

The preview NEVER calls an LLM: it is :func:`aivmt.persona.compile_persona_sections`.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from ..case_lint import lint_path
from ..persona import DIFFICULTY_LEVELS, compile_persona_sections
from .draft import DraftResult, validate_draft
from .storage import CaseExistsError, CaseStore, PortalStorageError

logger = logging.getLogger(__name__)

__all__ = ["build_router"]


def _result_json(result: DraftResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "errors": [issue.to_json() for issue in result.errors],
        "warnings": [issue.to_json() for issue in result.warnings],
    }


def _validated_or_422(draft: dict[str, Any]) -> DraftResult:
    """Validate a draft; raise HTTP 422 with structured errors when invalid."""
    result = validate_draft(draft)
    if not result.ok:
        raise HTTPException(status_code=422, detail=_result_json(result))
    return result


def build_router(store: CaseStore) -> APIRouter:
    """Build the API router bound to one :class:`CaseStore`."""
    router = APIRouter()

    @router.get("/cases")
    def list_cases() -> list[dict[str, Any]]:
        return [summary.to_json() for summary in store.list_cases()]

    @router.get("/cases/{case_id}")
    def load_case(case_id: str) -> dict[str, Any]:
        try:
            raw = store.load(case_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PortalStorageError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        report = lint_path(store.path_for(case_id))
        return {
            "case": raw,
            "lint": {"errors": list(report.errors), "warnings": list(report.warnings)},
        }

    @router.post("/validate")
    def validate(draft: dict[str, Any] = Body(...)) -> dict[str, Any]:
        result = validate_draft(draft)
        payload = _result_json(result)
        payload["normalized"] = result.normalized
        return payload

    @router.post("/cases")
    def save_case(
        case: dict[str, Any] = Body(...),
        overwrite: bool = Body(False),
    ) -> dict[str, Any]:
        result = _validated_or_422(case)
        assert result.normalized is not None  # ok=True implies normalized
        try:
            path = store.save(result.normalized, overwrite=overwrite)
        except CaseExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except PortalStorageError as exc:
            logger.error("portal: save failed — %s", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        payload = _result_json(result)
        payload["path"] = path.name
        return payload

    @router.post("/preview")
    def preview(draft: dict[str, Any] = Body(...)) -> dict[str, Any]:
        result = _validated_or_422(draft)
        assert result.case is not None  # ok=True implies a built case
        previews: dict[str, Any] = {}
        for difficulty in DIFFICULTY_LEVELS:
            compiled = compile_persona_sections(result.case, difficulty)
            previews[difficulty] = {
                "prompt": compiled.render(),
                "sections": {key: body for key, body in compiled.sections},
            }
        return {"language": result.case.language, "previews": previews}

    return router
