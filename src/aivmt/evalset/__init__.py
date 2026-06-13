"""Path-A eval set: case-grounded, quality-diverse zh OB/GYN history-taking transcripts.

This package turns the three collaborator-reviewed zh OB/GYN
:class:`~aivmt.case_schema.ClinicalCase` files into a deterministic ladder of
synthetic STUDENT<->SP dialogues with a designed (reference-only) quality
spread. It is the apparatus the Stream-A blinded faculty tool serves and that
``PhaseScoringValidity`` scores against, producing the first REAL
system-vs-faculty ICC while real encounters are collected in parallel.

No clinical fact is ever invented: every patient utterance is resolved strictly
from the case YAML (:mod:`aivmt.evalset.grounding`); every record is tagged
``provenance='synthetic'``; ``designed_quality`` is for validation only and is
never surfaced to a faculty rater.
"""

from __future__ import annotations

from .dataset import (
    OBGYN_CASE_FILES,
    PROVENANCE,
    build_eval_set,
    default_case_dir,
    default_eval_dir,
    default_keys_dir,
    eval_key_to_dict,
    eval_transcript_to_dict,
    load_eval_set,
    load_eval_transcript,
    load_obgyn_cases,
    write_eval_set,
)
from .generator import (
    QUALITY_TIERS,
    GeneratedTranscript,
    apparatus_tokens,
    designed_quality,
    generate_for_case,
)
from .grounding import (
    DEFAULT_NONANSWER_ZH,
    GroundedTurnPair,
    case_content_tokens,
    ground_checklist,
    ground_checklist_item,
    trigger_item_id,
)
from .scoring import (
    REAL_SCORE_COMMAND,
    ScoredEncounter,
    export_blank_faculty_sheet,
    score_eval_set,
)

__all__ = [
    # grounding
    "GroundedTurnPair",
    "DEFAULT_NONANSWER_ZH",
    "ground_checklist",
    "ground_checklist_item",
    "trigger_item_id",
    "case_content_tokens",
    # generator
    "GeneratedTranscript",
    "QUALITY_TIERS",
    "generate_for_case",
    "designed_quality",
    "eval_key_to_dict",
    "default_keys_dir",
    "apparatus_tokens",
    # dataset
    "OBGYN_CASE_FILES",
    "PROVENANCE",
    "default_case_dir",
    "default_eval_dir",
    "load_obgyn_cases",
    "build_eval_set",
    "eval_transcript_to_dict",
    "write_eval_set",
    "load_eval_transcript",
    "load_eval_set",
    # scoring (-> data/encounters/)
    "ScoredEncounter",
    "score_eval_set",
    "export_blank_faculty_sheet",
    "REAL_SCORE_COMMAND",
]
