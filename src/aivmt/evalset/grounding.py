"""Ground a checklist item to the SP answer it earns — strictly from the case YAML.

The eval-set generator never invents clinical facts. For each
:class:`~aivmt.schemas.ChecklistItem` of a structured
:class:`~aivmt.case_schema.ClinicalCase`, this module resolves *what the
standardized patient says when the item is asked* by reading ONLY the case's
structured fields:

* a ``hidden_info`` item is earned by the checklist item its ``trigger`` names
  (the trigger string ends with ``(<item_id>)`` — see the OB/GYN case YAMLs),
  and the SP utterance is that item's verbatim ``content``;
* otherwise the SP answer is assembled from the matching structured background
  fields (HPI / OB-GYN block / demographics / pertinent-negatives) by keyword
  overlap between the checklist item's ``text`` and a fixed field vocabulary;
* if the case supplies no content for an item, the SP gives the case's own
  default non-answer ("没有/不清楚"), exactly as the persona compiler mandates.

The *student question* text is derived from the checklist item's ``text`` (a
pure rephrasing of the rubric label) — it is study apparatus, not a clinical
fact. The mapping is deterministic: identical cases always yield identical
``(question, answer)`` pairs.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from ..case_schema import ClinicalCase, is_placeholder
from ..schemas import ChecklistItem

logger = logging.getLogger(__name__)

__all__ = [
    "GroundedTurnPair",
    "DEFAULT_NONANSWER_ZH",
    "ground_checklist_item",
    "ground_checklist",
    "trigger_item_id",
    "case_content_tokens",
]

#: The SP's case-mandated default when asked about an unspecified detail (persona rule).
DEFAULT_NONANSWER_ZH = "没有,不清楚。"

#: Trailing ``(item_id)`` marker in a hidden_info trigger string, e.g. "...(hx_bleeding)".
_TRIGGER_ITEM_RE = re.compile(r"\(([a-z][a-z0-9_]*)\)\s*$")

#: Keyword -> structured-field resolver vocabulary. Each entry maps a set of zh
#: keywords (that may appear in a checklist item's ``text``) to a function that
#: pulls the corresponding verbatim value(s) from the case. Order matters: the
#: first vocabulary entry whose keywords overlap the item text wins. This keeps
#: resolution deterministic and auditable (every answer is a case field).
_KW_LMP = ("末次月经", "停经")
_KW_MENSTRUAL = ("月经史", "月经周期", "周期", "经期", "月经量")
_KW_OBSTETRIC = ("孕产", "孕次", "产次", "流产")
_KW_CONTRACEPTION = ("避孕", "节育环", "上环")
_KW_SEXUAL = ("性生活", "性伴侣", "伴侣")
_KW_ONSET = ("起病", "起始时间", "演变", "加重")
_KW_LOCATION = ("部位",)
_KW_CHARACTER = ("性质", "性状", "颜色", "气味", "分泌物", "白带")
_KW_PAIN = ("腹痛", "疼痛")


@dataclass(frozen=True)
class GroundedTurnPair:
    """One student question paired with the case-grounded SP answer for a checklist item."""

    item_id: str
    student_question: str
    patient_answer: str
    #: Provenance tag of the answer: "hidden_info" | "background" | "nonanswer".
    answer_source: str


def trigger_item_id(trigger: str) -> str | None:
    """Return the checklist item_id named at the end of a hidden_info ``trigger``.

    The OB/GYN cases encode the earning item as a trailing ``(item_id)`` in each
    trigger string (e.g. "询问阴道流血的量、颜色、持续时间(hx_bleeding)"). Returns
    ``None`` when no such marker is present.
    """
    match = _TRIGGER_ITEM_RE.search(trigger.strip())
    return match.group(1) if match else None


def _hidden_by_item(case: ClinicalCase) -> dict[str, str]:
    """Map checklist item_id -> hidden_info content it earns (skips placeholders)."""
    out: dict[str, str] = {}
    for item in case.hidden_info:
        if is_placeholder(item.content):
            continue
        earned_by = trigger_item_id(item.trigger)
        if earned_by is not None:
            out[earned_by] = item.content
    return out


def _structured_background(case: ClinicalCase, item_text: str) -> str | None:
    """Assemble an SP answer from structured background fields by keyword overlap.

    Returns the joined verbatim field value(s), or ``None`` if no vocabulary entry
    matches (the caller then falls back to the case's default non-answer).
    """
    ob = case.obgyn

    def has(keywords: tuple[str, ...]) -> bool:
        return any(kw in item_text for kw in keywords)

    def usable(value: str) -> bool:
        return not is_placeholder(value) and value.strip() != ""

    # OB/GYN block fields (highest specificity first).
    if ob is not None:
        if has(_KW_LMP) and usable(ob.lmp):
            return ob.lmp
        if has(_KW_MENSTRUAL) and usable(ob.menstrual_history):
            return ob.menstrual_history
        if has(_KW_OBSTETRIC) and usable(ob.obstetric_history):
            return ob.obstetric_history
        if has(_KW_CONTRACEPTION) and usable(ob.contraception):
            return ob.contraception
        if has(_KW_SEXUAL) and usable(ob.sexual_history):
            return ob.sexual_history
    # HPI dimensions.
    hpi = case.hpi
    if has(_KW_CHARACTER) and usable(hpi.character):
        return hpi.character
    if has(_KW_PAIN) and usable(hpi.character) and usable(hpi.location):
        return f"{hpi.location},{hpi.character}"
    if has(_KW_PAIN) and usable(hpi.character):
        return hpi.character
    if has(_KW_ONSET) and usable(hpi.onset):
        return hpi.onset
    if has(_KW_LOCATION) and usable(hpi.location):
        return hpi.location
    return None


def _student_question(item: ChecklistItem) -> str:
    """Phrase a student question from a checklist label (apparatus text, not a fact).

    The label is already an action phrase ("询问末次月经/停经时间"); we strip the
    leading "询问" and render it as a direct question. No clinical content is added.
    """
    text = item.text.strip()
    stem = text[2:] if text.startswith("询问") else text
    stem = stem.strip()
    return f"请问您{stem},能跟我说说吗?"


def ground_checklist_item(case: ClinicalCase, item: ChecklistItem) -> GroundedTurnPair:
    """Resolve one checklist item to a grounded (question, SP-answer) pair.

    Resolution order (all sources are the case YAML, never invented):
    1. a ``hidden_info`` item whose trigger names this ``item_id`` -> its content;
    2. else structured background fields matched by keyword -> verbatim value(s);
    3. else the case's default non-answer ("没有/不清楚").
    """
    hidden = _hidden_by_item(case)
    if item.item_id in hidden:
        return GroundedTurnPair(item.item_id, _student_question(item), hidden[item.item_id], "hidden_info")
    bg = _structured_background(case, item.text)
    if bg is not None:
        return GroundedTurnPair(item.item_id, _student_question(item), bg, "background")
    return GroundedTurnPair(item.item_id, _student_question(item), DEFAULT_NONANSWER_ZH, "nonanswer")


def ground_checklist(case: ClinicalCase) -> tuple[GroundedTurnPair, ...]:
    """Ground every checklist item of ``case`` in checklist order (deterministic)."""
    return tuple(ground_checklist_item(case, item) for item in case.history_checklist)


def case_content_tokens(case: ClinicalCase) -> frozenset[str]:
    """Every verbatim clinical string the SP may legitimately utter for this case.

    This is the closed vocabulary used by tests to prove no patient utterance
    contains out-of-case clinical content: the chief complaint, all structured
    background fields, every hidden_info content, and the pertinent negatives.
    Apparatus strings (the default non-answer, greetings) are added by the caller.
    """
    tokens: set[str] = set()

    def add(value: str) -> None:
        if not is_placeholder(value) and value.strip():
            tokens.add(value.strip())

    add(case.chief_complaint)
    add(case.emotional_state)
    hpi = case.hpi
    for value in (
        hpi.onset, hpi.location, hpi.duration, hpi.character,
        hpi.aggravating, hpi.relieving, hpi.timing, hpi.severity,
    ):
        add(value)
    for value in hpi.associated_symptoms:
        add(value)
    for group in (case.pmh, case.medications, case.allergies, case.family_history, case.social_history):
        for value in group:
            add(value)
    for value in case.pertinent_negatives:
        add(value)
    if case.obgyn is not None:
        ob = case.obgyn
        for value in (ob.lmp, ob.menstrual_history, ob.obstetric_history, ob.contraception, ob.sexual_history):
            add(value)
    for item in case.hidden_info:
        add(item.content)
    return frozenset(tokens)
