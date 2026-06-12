"""AIVMT — AI Virtual Medical Teacher scoring pipeline."""

from .case_schema import (
    TODO_COLLAB,
    CaseValidationError,
    ClinicalCase,
    Demographics,
    HiddenInfoItem,
    HPI,
    OBGYNBlock,
    RedHerring,
    clinical_case_from_dict,
    load_clinical_case,
)
from .persona import (
    DIFFICULTY_LEVELS,
    DIFFICULTY_PROFILES,
    CompiledPersona,
    DifficultyProfile,
    compile_persona,
    compile_persona_sections,
    wrap_persona_text,
)
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
    # Stream B: structured case schema + persona compiler
    "TODO_COLLAB",
    "CaseValidationError",
    "ClinicalCase",
    "Demographics",
    "HPI",
    "HiddenInfoItem",
    "OBGYNBlock",
    "RedHerring",
    "clinical_case_from_dict",
    "load_clinical_case",
    "DIFFICULTY_LEVELS",
    "DIFFICULTY_PROFILES",
    "CompiledPersona",
    "DifficultyProfile",
    "compile_persona",
    "compile_persona_sections",
    "wrap_persona_text",
]

__version__ = "0.0.1"
