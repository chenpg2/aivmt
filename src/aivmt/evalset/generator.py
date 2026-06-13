"""Deterministic, case-grounded generator of quality-diverse zh OB/GYN transcripts.

This is the Stream-B *path-A* apparatus: a seeded generator that turns the three
collaborator-reviewed zh OB/GYN :class:`~aivmt.case_schema.ClinicalCase` files
into a ladder of synthetic STUDENT<->SP history-taking dialogues spanning low to
high quality. It is the analogue of
:func:`aivmt.robustness.fixtures.build_golded_dataset` (chest-pain one-liners),
extended to realistic multi-turn zh OB/GYN encounters.

Quality variation is produced by ONE knob: *which subset of the case's
``history_checklist`` items the simulated student asks*. A strong student covers
the whole checklist in order (earning hidden_info via the matching triggers and
probing reasoning at the end); a weak student covers only the first few items and
never reaches the reasoning probe. Every patient utterance is resolved by
:mod:`aivmt.evalset.grounding` strictly from the case YAML — no clinical fact is
invented here. Each transcript carries a designed ``designed_quality`` in [0, 1]
that is monotone non-decreasing in the number of checklist items covered; it is
for reference/validation only and is NEVER shown to a faculty rater.

Determinism: identical ``(case, seed)`` always yields byte-identical transcripts.
The seed only selects *coverage fractions* (the quality tiers) and a stable
per-transcript opening marker; it never alters clinical content.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..case_schema import ClinicalCase
from ..schemas import Telemetry, Transcript, Turn
from .grounding import GroundedTurnPair, ground_checklist

logger = logging.getLogger(__name__)

__all__ = [
    "GeneratedTranscript",
    "QUALITY_TIERS",
    "GREETING_ZH",
    "REASONING_PROBE_ZH",
    "REASONING_REPLY_ZH",
    "CLOSING_ZH",
    "REASONING_COVERAGE_THRESHOLD",
    "GREETING_COVERAGE_THRESHOLD",
    "generate_for_case",
    "designed_quality",
    "apparatus_tokens",
]

#: Coverage fractions (of the checklist) for the quality ladder, low -> high. The
#: weakest tier asks almost nothing; the strongest covers the whole checklist.
QUALITY_TIERS: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)

#: Apparatus utterances (study scaffolding, NOT clinical facts). A student who
#: greets/introduces earns set_the_stage; reaching the reasoning probe lets the
#: student verbalize a differential. These strings contain no case-specific facts.
GREETING_ZH = "您好,我是医学生,今天想了解一下您的情况,可以问您几个问题吗?"
REASONING_PROBE_ZH = "请说出您的鉴别诊断及理由,以及下一步建议的检查或处理。"
REASONING_REPLY_ZH = "好的,谢谢您的耐心。"
CLOSING_ZH = "我大概了解了,稍后会跟上级医生讨论后再向您说明下一步,谢谢您的配合。"

#: A greeting is emitted once coverage reaches this fraction (a stronger student greets).
GREETING_COVERAGE_THRESHOLD = 0.4
#: The reasoning probe + closing are emitted once coverage reaches this fraction.
REASONING_COVERAGE_THRESHOLD = 0.6

#: designed_quality structural bonuses (added before normalisation to [0, 1]).
_GREETING_BONUS = 0.05
_REASONING_BONUS = 0.10


@dataclass(frozen=True)
class GeneratedTranscript:
    """A generated transcript plus its designed (reference-only) quality."""

    transcript: Transcript
    designed_quality: float
    #: item_ids the simulated student covered, in order (for traceability/tests).
    covered_item_ids: tuple[str, ...]


def _n_covered(n_items: int, fraction: float) -> int:
    """Number of checklist items a student at ``fraction`` coverage asks (>=0)."""
    return max(0, min(n_items, round(fraction * n_items)))


def _has_greeting(fraction: float) -> bool:
    return fraction >= GREETING_COVERAGE_THRESHOLD


def _has_reasoning(fraction: float) -> bool:
    return fraction >= REASONING_COVERAGE_THRESHOLD


def designed_quality(n_items: int, fraction: float) -> float:
    """Designed reference quality in [0, 1] for a coverage ``fraction``.

    Monotone non-decreasing in coverage: it is the covered-fraction plus small
    structural bonuses for greeting and reasoning (both gated on coverage), then
    clamped to [0, 1]. Pure/deterministic.
    """
    n_cov = _n_covered(n_items, fraction)
    base = n_cov / n_items if n_items else 0.0
    bonus = 0.0
    if _has_greeting(fraction):
        bonus += _GREETING_BONUS
    if _has_reasoning(fraction):
        bonus += _REASONING_BONUS
    return max(0.0, min(1.0, base + bonus))


def _build_turns(
    grounded: tuple[GroundedTurnPair, ...],
    chief_complaint: str,
    fraction: float,
    marker: str,
) -> tuple[tuple[str, tuple[Turn, ...]], tuple[str, ...]]:
    """Assemble the (turns, covered_item_ids) for one coverage fraction.

    The encounter always opens with the chief complaint (the case's verbatim
    opening). A greeting precedes it at higher coverage; covered checklist items
    follow in order; a reasoning probe + closing close a strong encounter.
    ``marker`` makes otherwise-identical-coverage transcripts distinct without
    adding clinical content (appended to the opening student line only).
    """
    turns: list[Turn] = []
    if _has_greeting(fraction):
        turns.append(Turn("student", GREETING_ZH))
    # Opening: student invites the complaint; SP states ONLY the chief complaint.
    open_q = "您今天哪里不舒服?" + (f"(#{marker})" if marker else "")
    turns.append(Turn("student", open_q))
    turns.append(Turn("patient", chief_complaint))

    n_cov = _n_covered(len(grounded), fraction)
    covered: list[str] = []
    for pair in grounded[:n_cov]:
        turns.append(Turn("student", pair.student_question))
        turns.append(Turn("patient", pair.patient_answer))
        covered.append(pair.item_id)

    if _has_reasoning(fraction):
        turns.append(Turn("student", REASONING_PROBE_ZH))
        turns.append(Turn("patient", REASONING_REPLY_ZH))
        turns.append(Turn("student", CLOSING_ZH))

    return ("", tuple(turns)), tuple(covered)


def generate_for_case(
    case: ClinicalCase,
    *,
    seed: int,
    n_transcripts: int,
) -> list[GeneratedTranscript]:
    """Generate ``n_transcripts`` graded transcripts for one OB/GYN ``case``.

    Coverage fractions cycle through :data:`QUALITY_TIERS` (low->high), so the
    designed quality is spread across the ladder. ``seed`` is folded into the
    per-transcript opening marker only; it never changes clinical content, so the
    output is deterministic for a fixed ``(case, seed, n_transcripts)``.

    Raises:
        ValueError: if ``n_transcripts < 2`` (downstream ICC needs >=2 targets).
    """
    if n_transcripts < 2:
        raise ValueError("generate_for_case needs n_transcripts >= 2 (ICC requires n>=2 targets)")
    grounded = ground_checklist(case)
    out: list[GeneratedTranscript] = []
    for i in range(n_transcripts):
        fraction = QUALITY_TIERS[i % len(QUALITY_TIERS)]
        marker = f"{seed:d}_{i:02d}"
        (_, turns), covered = _build_turns(grounded, case.chief_complaint, fraction, marker)
        encounter_id = f"eval_{case.case_id}_{i:02d}"
        transcript = Transcript(
            encounter_id=encounter_id,
            case_id=case.case_id,
            language=case.language,
            turns=turns,
            telemetry=Telemetry(),
        )
        out.append(
            GeneratedTranscript(
                transcript=transcript,
                designed_quality=designed_quality(len(grounded), fraction),
                covered_item_ids=covered,
            )
        )
    return out


def apparatus_tokens() -> frozenset[str]:
    """Non-clinical scaffolding strings the generator may emit verbatim.

    Tests union these with :func:`aivmt.evalset.grounding.case_content_tokens` to
    form the closed vocabulary of legitimate patient utterances.
    """
    return frozenset({REASONING_REPLY_ZH})
