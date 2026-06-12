"""AIVMT — AI Virtual Medical Teacher scoring pipeline."""

from .schemas import (
    Case,
    ChecklistItem,
    CompetencyScore,
    Feedback,
    ItemScore,
    ScoringResult,
    Telemetry,
    Transcript,
    Turn,
)

__all__ = [
    "Case",
    "ChecklistItem",
    "CompetencyScore",
    "Feedback",
    "ItemScore",
    "ScoringResult",
    "Telemetry",
    "Transcript",
    "Turn",
]

__version__ = "0.0.1"
