"""教师评分门户 (blinded faculty-scoring portal).

A zero-build, offline-friendly FastAPI app that lets a clinical faculty rater
score de-identified standardized-patient transcripts through a Chinese web form.
The rater is BLINDED: the tool never shows the system score, gold label, model
id, or experimental condition — only de-identified transcript text. Each rated
encounter appends one row to ``data/faculty_ratings.csv`` in the exact
:data:`aivmt.dataio.FACULTY_SHEET_FIELDS` order, which feeds the SQ1
system-vs-faculty ICC (``aivmt.metrics.run_validity_suite``).
"""

from .app import create_app
from .scoring import ScoreIssue, ValidatedScore, validate_submission
from .storage import (
    DuplicateRatingError,
    FacultyPortalError,
    RatingStore,
    TranscriptStore,
    UnknownEncounterError,
    default_ratings_csv,
    default_transcript_dir,
)

__all__ = [
    "create_app",
    "TranscriptStore",
    "RatingStore",
    "FacultyPortalError",
    "DuplicateRatingError",
    "UnknownEncounterError",
    "ScoreIssue",
    "ValidatedScore",
    "validate_submission",
    "default_transcript_dir",
    "default_ratings_csv",
]
