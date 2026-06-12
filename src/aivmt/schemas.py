"""Typed, immutable data schemas for the AIVMT scoring pipeline.

Frozen dataclasses ensure configuration/records are not mutated in place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

Language = Literal["en", "zh"]  # English primary, Chinese supported
Speaker = Literal["student", "patient"]
Difficulty = Literal["simple", "moderate", "complex"]


@dataclass(frozen=True)
class Turn:
    """A single utterance in an encounter transcript."""

    speaker: Speaker
    text: str
    t_start: float = 0.0
    t_end: float = 0.0


@dataclass(frozen=True)
class ChecklistItem:
    """One expected history-taking action, with a scoring weight."""

    item_id: str
    text: str
    weight: float = 1.0


@dataclass(frozen=True)
class Telemetry:
    """Device-side behavioral telemetry feeding the H2 engagement composite."""

    duration_s: float = 0.0
    n_student_questions: int = 0
    n_voluntary_repeats: int = 0


@dataclass(frozen=True)
class Case:
    """A standardized-patient case definition."""

    case_id: str
    title: str
    language: Language
    persona: str
    history_checklist: tuple[ChecklistItem, ...]
    difficulty: Difficulty = "moderate"


@dataclass(frozen=True)
class Transcript:
    """A recorded student-patient encounter."""

    encounter_id: str
    case_id: str
    language: Language
    turns: tuple[Turn, ...]
    telemetry: Telemetry = field(default_factory=Telemetry)


@dataclass(frozen=True)
class ItemScore:
    """Whether a single checklist item was covered, with supporting evidence."""

    item_id: str
    covered: bool
    evidence: Optional[str] = None


@dataclass(frozen=True)
class CompetencyScore:
    """Aggregated competency scores (all sub-scores in [0, 1])."""

    history_completion: float
    segue: dict[str, float]
    reasoning: float
    overall: float
    item_scores: tuple[ItemScore, ...] = ()


@dataclass(frozen=True)
class Feedback:
    """Structured formative feedback returned to the learner."""

    summary: str
    strengths: tuple[str, ...] = ()
    improvements: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScoringResult:
    """The full output for one encounter — the unit validated against faculty (H1)."""

    encounter_id: str
    model_id: str
    score: CompetencyScore
    feedback: Feedback
