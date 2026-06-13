"""Formal, validated standardized-patient case schema (Stream B data layer).

A :class:`ClinicalCase` is the typed, immutable representation behind the LMIC
SP authoring portal. It is a *superset* of the legacy :class:`aivmt.schemas.Case`:
every ``ClinicalCase`` can emit the flat ``Case`` that the scoring pipeline
(``aivmt.scoring.checklist``) consumes today, so this schema stays backward
compatible with the existing pipeline and with ``aivmt.cases.load_case``.

Placeholders: clinical fields that have not yet been collaboratively authored
carry the literal sentinel :data:`TODO_COLLAB`. The schema treats these as
*structurally* valid; the linter (``aivmt.case_lint``) reports them as WARNINGS.
Missing clinical content is never invented here.

Note on difficulty: the case file's ``difficulty`` key (simple/moderate/complex)
is a descriptive *clinical-complexity* label kept for legacy compatibility. The
standardized-patient *behavioral* difficulty (easy/standard/hard) is NOT stored
in the case — it is a compile-time parameter of :mod:`aivmt.persona`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

from .schemas import Case, ChecklistItem, Language

logger = logging.getLogger(__name__)

#: Sentinel for a required clinical field that still needs collaborative authoring.
TODO_COLLAB = "TODO_COLLAB"

#: Upper bound on a checklist item weight — keeps the scoring normalisation (sum of weights)
#: positive and prevents a single item from dominating; negative weights are rejected outright.
MAX_CHECKLIST_WEIGHT = 10.0

_LANGUAGES: tuple[str, ...] = ("en", "zh")
_CLINICAL_COMPLEXITY: tuple[str, ...] = ("simple", "moderate", "complex")

__all__ = [
    "TODO_COLLAB",
    "MAX_CHECKLIST_WEIGHT",
    "CaseValidationError",
    "Demographics",
    "HPI",
    "HiddenInfoItem",
    "RedHerring",
    "OBGYNBlock",
    "ClinicalCase",
    "clinical_case_from_dict",
    "load_clinical_case",
    "is_placeholder",
]


class CaseValidationError(ValueError):
    """Raised when a case dict violates the schema. Message is ``source:field — why``."""


def is_placeholder(value: object) -> bool:
    """Return True if ``value`` is the literal TODO_COLLAB sentinel."""
    return isinstance(value, str) and value.strip() == TODO_COLLAB


@dataclass(frozen=True)
class Demographics:
    """Patient demographics. ``age``/``sex`` are required clinical facts."""

    age: str
    sex: str
    occupation: str = TODO_COLLAB
    marital_status: str = TODO_COLLAB


@dataclass(frozen=True)
class HPI:
    """Structured history of present illness (OPQRST-style dimensions)."""

    onset: str = TODO_COLLAB
    location: str = TODO_COLLAB
    duration: str = TODO_COLLAB
    character: str = TODO_COLLAB
    aggravating: str = TODO_COLLAB
    relieving: str = TODO_COLLAB
    timing: str = TODO_COLLAB
    severity: str = TODO_COLLAB
    associated_symptoms: tuple[str, ...] = ()


@dataclass(frozen=True)
class HiddenInfoItem:
    """A fact the SP reveals ONLY when a specific question (the trigger) is asked."""

    info_id: str
    content: str
    trigger: str


@dataclass(frozen=True)
class RedHerring:
    """A benign-but-distracting finding; surfaced only at higher difficulty."""

    herring_id: str
    content: str
    note: str = ""


@dataclass(frozen=True)
class OBGYNBlock:
    """OB/GYN specialty block (the first supported specialty-specific extension)."""

    lmp: str = TODO_COLLAB
    menstrual_history: str = TODO_COLLAB
    obstetric_history: str = TODO_COLLAB
    contraception: str = TODO_COLLAB
    sexual_history: str = TODO_COLLAB


@dataclass(frozen=True)
class ClinicalCase:
    """A fully structured standardized-patient case."""

    case_id: str
    version: str
    language: Language
    specialty: str
    title: str
    demographics: Demographics
    chief_complaint: str
    hpi: HPI
    pmh: tuple[str, ...]
    medications: tuple[str, ...]
    allergies: tuple[str, ...]
    family_history: tuple[str, ...]
    social_history: tuple[str, ...]
    hidden_info: tuple[HiddenInfoItem, ...]
    history_checklist: tuple[ChecklistItem, ...]
    emotional_state: str
    disclosure_profile: str
    persona_text: str
    #: Clinically load-bearing negatives ("no fever", "discharge normal") that the SP
    #: must disclose truthfully when asked. Structured here so the compiler renders them
    #: (the structured ``from_clinical_case`` path does NOT read ``persona_text``); without
    #: this, the behavior block would make the SP answer "none" and contradict the source.
    pertinent_negatives: tuple[str, ...] = ()
    red_herrings: tuple[RedHerring, ...] = ()
    obgyn: Optional[OBGYNBlock] = None
    clinical_complexity: str = "moderate"

    def to_case(self, persona: Optional[str] = None) -> Case:
        """Project to the legacy flat ``Case`` consumed by the scoring pipeline.

        ``persona`` overrides the free-text persona (e.g. a compiled prompt); by
        default the verbatim ``persona_text`` is used so existing behavior is kept.
        """
        return Case(
            case_id=self.case_id,
            title=self.title,
            language=self.language,
            persona=self.persona_text if persona is None else persona,
            history_checklist=self.history_checklist,
            difficulty=self.clinical_complexity,  # type: ignore[arg-type]
        )

    def placeholder_paths(self) -> tuple[str, ...]:
        """Dotted paths of every field still holding the TODO_COLLAB sentinel."""
        return tuple(_walk_placeholders(self))


# --------------------------------------------------------------------------- #
# Validation / construction
# --------------------------------------------------------------------------- #
def _require(cond: bool, source: str, field_path: str, why: str) -> None:
    if not cond:
        raise CaseValidationError(f"{source}:{field_path} — {why}")


def _as_str(data: dict, key: str, source: str, *, required: bool = True) -> str:
    if key not in data:
        _require(not required, source, key, "missing required field")
        return TODO_COLLAB
    value = data[key]
    _require(isinstance(value, str), source, key, f"must be a string, got {type(value).__name__}")
    _require(value.strip() != "", source, key, "must not be empty")
    return value


def _as_str_tuple(data: dict, key: str, source: str) -> tuple[str, ...]:
    if key not in data:
        raise CaseValidationError(f"{source}:{key} — missing required field (list of strings)")
    return _coerce_str_tuple(data[key], key, source)


def _as_opt_str_tuple(data: dict, key: str, source: str) -> tuple[str, ...]:
    """Like :func:`_as_str_tuple` but absence yields an empty tuple (optional field)."""
    if key not in data or data[key] is None:
        return ()
    return _coerce_str_tuple(data[key], key, source)


def _coerce_str_tuple(value: Any, key: str, source: str) -> tuple[str, ...]:
    _require(isinstance(value, (list, tuple)), source, key, "must be a list")
    out: list[str] = []
    for i, item in enumerate(value):
        _require(isinstance(item, str), source, f"{key}[{i}]", "must be a string")
        out.append(item)
    return tuple(out)


def _demographics_from(data: Any, source: str) -> Demographics:
    _require(isinstance(data, dict), source, "demographics", "must be a mapping")
    return Demographics(
        age=_as_str(data, "age", f"{source}:demographics"),
        sex=_as_str(data, "sex", f"{source}:demographics"),
        occupation=_as_str(data, "occupation", f"{source}:demographics", required=False),
        marital_status=_as_str(data, "marital_status", f"{source}:demographics", required=False),
    )


def _hpi_from(data: Any, source: str) -> HPI:
    _require(isinstance(data, dict), source, "hpi", "must be a mapping")
    s = f"{source}:hpi"
    assoc = data.get("associated_symptoms", [])
    _require(isinstance(assoc, (list, tuple)), s, "associated_symptoms", "must be a list")
    return HPI(
        onset=_as_str(data, "onset", s, required=False),
        location=_as_str(data, "location", s, required=False),
        duration=_as_str(data, "duration", s, required=False),
        character=_as_str(data, "character", s, required=False),
        aggravating=_as_str(data, "aggravating", s, required=False),
        relieving=_as_str(data, "relieving", s, required=False),
        timing=_as_str(data, "timing", s, required=False),
        severity=_as_str(data, "severity", s, required=False),
        associated_symptoms=tuple(str(x) for x in assoc),
    )


def _hidden_from(data: Any, source: str) -> tuple[HiddenInfoItem, ...]:
    _require(isinstance(data, (list, tuple)), source, "hidden_info", "must be a list")
    items: list[HiddenInfoItem] = []
    for i, raw in enumerate(data):
        s = f"{source}:hidden_info[{i}]"
        _require(isinstance(raw, dict), source, f"hidden_info[{i}]", "must be a mapping")
        items.append(
            HiddenInfoItem(
                info_id=_as_str(raw, "info_id", s),
                content=_as_str(raw, "content", s),
                trigger=_as_str(raw, "trigger", s),
            )
        )
    return tuple(items)


def _red_herrings_from(data: Any, source: str) -> tuple[RedHerring, ...]:
    if data is None:
        return ()
    _require(isinstance(data, (list, tuple)), source, "red_herrings", "must be a list")
    items: list[RedHerring] = []
    for i, raw in enumerate(data):
        s = f"{source}:red_herrings[{i}]"
        _require(isinstance(raw, dict), source, f"red_herrings[{i}]", "must be a mapping")
        items.append(
            RedHerring(
                herring_id=_as_str(raw, "herring_id", s),
                content=_as_str(raw, "content", s),
                note=raw.get("note", ""),
            )
        )
    return tuple(items)


def _checklist_from(data: Any, source: str) -> tuple[ChecklistItem, ...]:
    _require(isinstance(data, (list, tuple)), source, "history_checklist", "must be a list")
    _require(len(data) > 0, source, "history_checklist", "must have at least one item")
    items: list[ChecklistItem] = []
    seen: set[str] = set()
    for i, raw in enumerate(data):
        s = f"history_checklist[{i}]"
        _require(isinstance(raw, dict), source, s, "must be a mapping")
        item_id = _as_str(raw, "item_id", f"{source}:{s}")
        _require(item_id not in seen, source, f"{s}.item_id", f"duplicate item_id '{item_id}'")
        seen.add(item_id)
        text = _as_str(raw, "text", f"{source}:{s}")
        weight = raw.get("weight", 1.0)
        _require(
            isinstance(weight, (int, float)) and not isinstance(weight, bool),
            source, f"{s}.weight", "must be a number",
        )
        _require(
            0.0 <= float(weight) <= MAX_CHECKLIST_WEIGHT,
            source, f"{s}.weight", f"must be within [0, {MAX_CHECKLIST_WEIGHT}]",
        )
        items.append(ChecklistItem(item_id=item_id, text=text, weight=float(weight)))
    return tuple(items)


def _obgyn_from(data: Any, source: str) -> Optional[OBGYNBlock]:
    if data is None:
        return None
    _require(isinstance(data, dict), source, "obgyn", "must be a mapping")
    s = f"{source}:obgyn"
    return OBGYNBlock(
        lmp=_as_str(data, "lmp", s, required=False),
        menstrual_history=_as_str(data, "menstrual_history", s, required=False),
        obstetric_history=_as_str(data, "obstetric_history", s, required=False),
        contraception=_as_str(data, "contraception", s, required=False),
        sexual_history=_as_str(data, "sexual_history", s, required=False),
    )


def clinical_case_from_dict(data: dict, *, source: str = "<dict>") -> ClinicalCase:
    """Build and validate a :class:`ClinicalCase` from a plain dict.

    Raises:
        CaseValidationError: on any structural / type violation (``source:field``).
    """
    _require(isinstance(data, dict), source, "<root>", "case file must be a mapping")

    language = _as_str(data, "language", source)
    _require(language in _LANGUAGES, source, "language", f"must be one of {_LANGUAGES}")

    complexity = data.get("difficulty", "moderate")
    _require(
        complexity in _CLINICAL_COMPLEXITY, source, "difficulty",
        f"clinical-complexity label must be one of {_CLINICAL_COMPLEXITY}",
    )

    return ClinicalCase(
        case_id=_as_str(data, "case_id", source),
        version=_as_str(data, "version", source),
        language=language,  # type: ignore[arg-type]
        specialty=_as_str(data, "specialty", source),
        title=_as_str(data, "title", source),
        demographics=_demographics_from(data.get("demographics"), source),
        chief_complaint=_as_str(data, "chief_complaint", source),
        hpi=_hpi_from(data.get("hpi"), source),
        pmh=_as_str_tuple(data, "pmh", source),
        medications=_as_str_tuple(data, "medications", source),
        allergies=_as_str_tuple(data, "allergies", source),
        family_history=_as_str_tuple(data, "family_history", source),
        social_history=_as_str_tuple(data, "social_history", source),
        hidden_info=_hidden_from(data.get("hidden_info"), source),
        history_checklist=_checklist_from(data.get("history_checklist"), source),
        emotional_state=_as_str(data, "emotional_state", source),
        disclosure_profile=_as_str(data, "disclosure_profile", source),
        persona_text=_as_str(data, "persona", source),
        pertinent_negatives=_as_opt_str_tuple(data, "pertinent_negatives", source),
        red_herrings=_red_herrings_from(data.get("red_herrings"), source),
        obgyn=_obgyn_from(data.get("obgyn"), source),
        clinical_complexity=complexity,
    )


def load_clinical_case(path: Union[str, Path]) -> ClinicalCase:
    """Load and validate a :class:`ClinicalCase` from a YAML file via OmegaConf."""
    from omegaconf import OmegaConf  # noqa: PLC0415 — keep heavy dep import lazy

    cfg = OmegaConf.load(str(path))
    data = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(data, dict):
        raise CaseValidationError(f"{path}:<root> — YAML must define a mapping")
    return clinical_case_from_dict(data, source=str(path))


_SCALAR_FIELDS: tuple[str, ...] = (
    "case_id", "version", "specialty", "title", "chief_complaint",
    "emotional_state", "disclosure_profile", "persona_text",
)


def _walk_placeholders(case: ClinicalCase) -> list[str]:
    paths: list[str] = []
    for name in _SCALAR_FIELDS:
        if is_placeholder(getattr(case, name)):
            paths.append(name)
    for name in ("age", "sex", "occupation", "marital_status"):
        if is_placeholder(getattr(case.demographics, name)):
            paths.append(f"demographics.{name}")
    for name in (
        "onset", "location", "duration", "character",
        "aggravating", "relieving", "timing", "severity",
    ):
        if is_placeholder(getattr(case.hpi, name)):
            paths.append(f"hpi.{name}")
    for list_name in (
        "pmh", "medications", "allergies", "family_history", "social_history",
        "pertinent_negatives",
    ):
        for i, value in enumerate(getattr(case, list_name)):
            if is_placeholder(value):
                paths.append(f"{list_name}[{i}]")
    for i, item in enumerate(case.hidden_info):
        if is_placeholder(item.content):
            paths.append(f"hidden_info[{i}].content")
    if case.obgyn is not None:
        for name in ("lmp", "menstrual_history", "obstetric_history", "contraception", "sexual_history"):
            if is_placeholder(getattr(case.obgyn, name)):
                paths.append(f"obgyn.{name}")
    return paths
