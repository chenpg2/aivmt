"""FastAPI app factory for the 教师评分门户 (blinded faculty-scoring portal).

Offline-friendly by construction: API docs endpoints are disabled (they pull CDN
assets) and every static asset is served from the local ``static/`` dir. The app
is rooted at one transcript directory (the eval set) and one ratings CSV; it
serves de-identified transcripts to a faculty rater and appends their scores.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import build_router
from .storage import (
    RatingStore,
    TranscriptStore,
    default_ratings_csv,
    default_transcript_dir,
)

logger = logging.getLogger(__name__)

__all__ = ["create_app", "DEFAULT_SEED"]

_STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_SEED = 42  # mirrors configs/seed.yaml; overridden by create_app(seed=...)


def create_app(
    transcript_dir: Optional[Union[str, Path]] = None,
    ratings_csv: Optional[Union[str, Path]] = None,
    *,
    seed: int = DEFAULT_SEED,
) -> FastAPI:
    """Build the faculty portal app.

    Args:
        transcript_dir: eval transcript directory (default: ``$AIVMT_EVAL_TRANSCRIPT_DIR``
            or ``data/eval_transcripts``).
        ratings_csv: faculty ratings CSV path (default: ``$AIVMT_FACULTY_RATINGS_CSV``
            or ``data/faculty_ratings.csv``).
        seed: base seed for the per-rater serving order (mirror configs/seed.yaml).

    Raises:
        FileNotFoundError: if the transcript directory does not exist (fail loud).
    """
    tdir = Path(transcript_dir) if transcript_dir is not None else default_transcript_dir()
    cpath = Path(ratings_csv) if ratings_csv is not None else default_ratings_csv()
    transcripts = TranscriptStore(transcript_dir=tdir, base_seed=seed)  # raises if missing
    ratings = RatingStore(csv_path=cpath)
    logger.info("faculty_portal: transcripts=%s ratings=%s seed=%d", tdir, cpath, seed)

    app = FastAPI(
        title="AIVMT 教师评分门户",
        docs_url=None,  # offline: no CDN-backed swagger assets
        redoc_url=None,
        openapi_url=None,
    )
    app.include_router(build_router(transcripts, ratings), prefix="/api")
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    return app
