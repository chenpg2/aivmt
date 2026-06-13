"""FastAPI app factory for the 病历录入门户 (case-entry portal).

Offline-friendly by construction: API docs endpoints are disabled (they pull
CDN assets) and every static asset is served from the local ``static/`` dir.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import build_router
from .storage import CaseStore, default_case_dir

logger = logging.getLogger(__name__)

__all__ = ["create_app"]

_STATIC_DIR = Path(__file__).parent / "static"


def create_app(case_dir: Optional[Union[str, Path]] = None) -> FastAPI:
    """Build the portal app rooted at ``case_dir`` (default: $AIVMT_CASE_DIR or conf/case).

    Raises:
        FileNotFoundError: if the case directory does not exist (fail loud —
            the portal never silently creates or relocates the case library).
    """
    resolved = Path(case_dir) if case_dir is not None else default_case_dir()
    store = CaseStore(case_dir=resolved)  # raises FileNotFoundError if missing
    logger.info("portal: case directory = %s", resolved)

    app = FastAPI(
        title="AIVMT 病历录入门户",
        docs_url=None,  # offline: no CDN-backed swagger assets
        redoc_url=None,
        openapi_url=None,
    )
    app.include_router(build_router(store), prefix="/api")
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    return app
