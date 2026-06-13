"""Draft normalization + validation for the case-entry portal.

The portal NEVER invents clinical content. Normalization only:

* trims whitespace and drops fully-empty rows/lines,
* replaces *empty optional clinical fields* with the ``TODO_COLLAB`` sentinel
  (the same convention :mod:`aivmt.case_lint` reports as WARNING),
* fills non-clinical metadata defaults (``version`` -> "1.0.0", checklist
  ``weight`` -> 1.0 — mirroring the schema's own defaults).

Validation truth stays in :func:`aivmt.case_schema.clinical_case_from_dict`;
this module adds teacher-friendly Chinese messages on top and a small set of
portal-level hard requirements (identity/metadata fields that the TODO_COLLAB
convention cannot stand in for, e.g. ``case_id`` which becomes the filename).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from ..case_schema import (
    TODO_COLLAB,
    CaseValidationError,
    ClinicalCase,
    clinical_case_from_dict,
)
from .storage import CASE_ID_RE

logger = logging.getLogger(__name__)

__all__ = ["FieldIssue", "DraftResult", "normalize_draft", "validate_draft"]


@dataclass(frozen=True)
class FieldIssue:
    """One structured problem, addressed to a dotted field path."""

    field: str
    message: str

    def to_json(self) -> dict[str, str]:
        """JSON-ready representation."""
        return {"field": self.field, "message": self.message}


@dataclass(frozen=True)
class DraftResult:
    """Outcome of validating one draft."""

    ok: bool
    errors: tuple[FieldIssue, ...]
    warnings: tuple[FieldIssue, ...]
    normalized: Optional[dict[str, Any]]
    case: Optional[ClinicalCase]


# --------------------------------------------------------------------------- #
# zh translations
# --------------------------------------------------------------------------- #
_FIELD_LABELS_ZH: dict[str, str] = {
    "case_id": "病例编号",
    "version": "版本号",
    "title": "病例标题",
    "language": "语言",
    "specialty": "专科",
    "difficulty": "临床复杂度",
    "demographics.age": "年龄",
    "demographics.sex": "性别",
    "chief_complaint": "主诉",
    "history_checklist": "评分清单",
    "hidden_info": "隐藏信息",
    "red_herrings": "干扰项",
    "emotional_state": "情绪状态",
    "disclosure_profile": "披露风格",
    "persona": "人物设定(自由文本)",
}

_WHY_ZH: tuple[tuple[str, str], ...] = (
    ("missing required field", "缺少必填字段"),
    ("must be a string", "必须为文本"),
    ("must not be empty", "不能为空"),
    ("must be a list", "必须为列表"),
    ("must be a mapping", "必须为对象"),
    ("must be a number", "必须为数字"),
    ("must have at least one item", "至少需要一项"),
    ("duplicate item_id", "清单编号(item_id)重复"),
    ("clinical-complexity label", "临床复杂度必须为 simple / moderate / complex"),
    ("must be one of", "取值不在允许范围内"),
)


def _label(field: str) -> str:
    return _FIELD_LABELS_ZH.get(field, field)


def _translate_schema_error(exc: CaseValidationError) -> FieldIssue:
    """Turn a ``source:field — why`` schema error into a zh-friendly issue."""
    message = str(exc)
    field, sep, why = message.partition(" — ")
    if not sep:
        return FieldIssue(field="<draft>", message=message)
    # strip the "<draft>:" source prefix only — nested paths like "demographics:age" must
    # survive intact so the zh field-label lookup matches
    field = field.removeprefix("<draft>:")
    zh = next((zh for prefix, zh in _WHY_ZH if why.startswith(prefix)), why)
    return FieldIssue(field=field, message=f"{_label(field)}:{zh}({why})")


# --------------------------------------------------------------------------- #
# Normalization (no clinical invention — blanks become TODO_COLLAB)
# --------------------------------------------------------------------------- #
def _s(value: Any) -> str:
    """Stripped string form of a form value (None -> '')."""
    return str(value).strip() if value is not None else ""


def _opt(value: Any) -> str:
    """Optional clinical scalar: blank -> TODO_COLLAB placeholder."""
    text = _s(value)
    return text if text else TODO_COLLAB


def _lines(value: Any) -> list[str]:
    """Clean a string list (drop blank entries, keep order)."""
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise CaseValidationError(f"<draft>:{value!r} — must be a list")
    return [t for t in (_s(item) for item in value) if t]


def _history_list(value: Any) -> list[str]:
    """History list (pmh/medications/...): empty -> [TODO_COLLAB] (awaiting authoring)."""
    cleaned = _lines(value)
    return cleaned if cleaned else [TODO_COLLAB]


def _rows(value: Any, keys: tuple[str, ...]) -> list[dict[str, str]]:
    """Keep only rows where at least one of ``keys`` is non-blank."""
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise CaseValidationError("<draft>:rows — must be a list")
    out: list[dict[str, str]] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        row = {k: _s(raw.get(k)) for k in keys}
        if any(row[k] for k in keys):
            out.append(row)
    return out


def _normalize_obgyn(raw: Any, specialty: str) -> Optional[dict[str, str]]:
    block = raw if isinstance(raw, dict) else {}
    fields = ("lmp", "menstrual_history", "obstetric_history", "contraception", "sexual_history")
    values = {k: _s(block.get(k)) for k in fields}
    if specialty != "obgyn" and not any(values.values()):
        return None  # non-OBGYN case with nothing entered: omit the block entirely
    return {k: (v if v else TODO_COLLAB) for k, v in values.items()}


def normalize_draft(raw: dict[str, Any]) -> dict[str, Any]:
    """Build the canonical case dict (stable key order, TODO_COLLAB filled).

    Raises:
        CaseValidationError: if the draft is not a mapping / lists are malformed.
    """
    if not isinstance(raw, dict):
        raise CaseValidationError("<draft>:<root> — case draft must be a mapping")

    def _sub(key: str) -> dict[str, Any]:
        value = raw.get(key)
        return value if isinstance(value, dict) else {}

    demographics = _sub("demographics")
    hpi = _sub("hpi")
    specialty = _s(raw.get("specialty"))

    hidden = _rows(raw.get("hidden_info"), ("info_id", "content", "trigger"))
    herrings = _rows(raw.get("red_herrings"), ("herring_id", "content", "note"))
    checklist_rows = _rows(raw.get("history_checklist"), ("item_id", "text", "weight"))
    checklist: list[dict[str, Any]] = []
    for row in checklist_rows:
        weight_text = row.get("weight", "")
        item: dict[str, Any] = {"item_id": row["item_id"], "text": row["text"]}
        if weight_text:
            try:
                item["weight"] = float(weight_text)
            except ValueError:
                item["weight"] = weight_text  # keep as-is -> schema rejects with a clear error
        else:
            item["weight"] = 1.0  # scoring metadata default, mirrors ChecklistItem
        checklist.append(item)

    normalized: dict[str, Any] = {
        "case_id": _s(raw.get("case_id")),
        "version": _s(raw.get("version")) or "1.0.0",
        "title": _s(raw.get("title")),
        "language": _s(raw.get("language")),
        "specialty": specialty,
        "difficulty": _s(raw.get("difficulty")) or "moderate",
        "demographics": {
            "age": _s(demographics.get("age")),
            "sex": _s(demographics.get("sex")),
            "occupation": _opt(demographics.get("occupation")),
            "marital_status": _opt(demographics.get("marital_status")),
        },
        "chief_complaint": _opt(raw.get("chief_complaint")),
        "hpi": {
            **{
                key: _opt(hpi.get(key))
                for key in (
                    "onset", "location", "duration", "character",
                    "aggravating", "relieving", "timing", "severity",
                )
            },
            "associated_symptoms": _lines(hpi.get("associated_symptoms")),
        },
        "pmh": _history_list(raw.get("pmh")),
        "medications": _history_list(raw.get("medications")),
        "allergies": _history_list(raw.get("allergies")),
        "family_history": _history_list(raw.get("family_history")),
        "social_history": _history_list(raw.get("social_history")),
        "pertinent_negatives": _lines(raw.get("pertinent_negatives")),
        "hidden_info": [
            {
                "info_id": row["info_id"],
                "content": row["content"] or TODO_COLLAB,
                "trigger": row["trigger"],
            }
            for row in hidden
        ],
        "red_herrings": [
            {"herring_id": row["herring_id"], "content": row["content"], "note": row["note"]}
            for row in herrings
        ],
        "emotional_state": _opt(raw.get("emotional_state")),
        "disclosure_profile": _opt(raw.get("disclosure_profile")),
        "persona": _opt(raw.get("persona")),
        "history_checklist": checklist,
    }
    obgyn = _normalize_obgyn(raw.get("obgyn"), specialty)
    if obgyn is not None:
        normalized["obgyn"] = obgyn
    return normalized


# --------------------------------------------------------------------------- #
# Portal-level hard requirements (cannot be stood in for by TODO_COLLAB)
# --------------------------------------------------------------------------- #
def _portal_required_errors(norm: dict[str, Any]) -> list[FieldIssue]:
    errors: list[FieldIssue] = []

    def need(field: str, value: str, why: str) -> None:
        if not value:
            errors.append(FieldIssue(field=field, message=f"{_label(field)}:{why}"))

    case_id = str(norm["case_id"])
    need("case_id", case_id, "必填(将作为文件名)")
    if case_id and not CASE_ID_RE.match(case_id):
        errors.append(FieldIssue(
            field="case_id",
            message="病例编号:只允许小写字母、数字、下划线,且以字母开头(如 obgyn_aub_zh_02)",
        ))
    need("title", str(norm["title"]), "必填")
    need("language", str(norm["language"]), "必填(zh 或 en)")
    need("specialty", str(norm["specialty"]), "必填(如 obgyn)")
    need("demographics.age", str(norm["demographics"]["age"]), "必填")
    need("demographics.sex", str(norm["demographics"]["sex"]), "必填")
    if not norm["history_checklist"]:
        errors.append(FieldIssue(
            field="history_checklist", message="评分清单:至少需要一条评分项",
        ))
    for i, row in enumerate(norm["hidden_info"]):
        if not row["info_id"]:
            errors.append(FieldIssue(
                field=f"hidden_info[{i}].info_id", message=f"隐藏信息第{i + 1}条:缺少编号(info_id)",
            ))
        if not row["trigger"]:
            errors.append(FieldIssue(
                field=f"hidden_info[{i}].trigger",
                message=f"隐藏信息第{i + 1}条:必须填写触发条件(学生问到什么才透露)",
            ))
    for i, row in enumerate(norm["red_herrings"]):
        if not row["herring_id"] or not row["content"]:
            errors.append(FieldIssue(
                field=f"red_herrings[{i}]", message=f"干扰项第{i + 1}条:编号和内容均不能为空",
            ))
    for i, row in enumerate(norm["history_checklist"]):
        if not row["item_id"] or not row["text"]:
            errors.append(FieldIssue(
                field=f"history_checklist[{i}]",
                message=f"评分清单第{i + 1}条:编号(item_id)和内容均不能为空",
            ))
    return errors


def validate_draft(raw: dict[str, Any]) -> DraftResult:
    """Normalize + validate a draft. Schema validation is the source of truth."""
    try:
        normalized = normalize_draft(raw)
    except CaseValidationError as exc:
        return DraftResult(
            ok=False, errors=(_translate_schema_error(exc),), warnings=(),
            normalized=None, case=None,
        )

    errors = _portal_required_errors(normalized)
    case: Optional[ClinicalCase] = None
    if not errors:
        try:
            case = clinical_case_from_dict(normalized, source="<draft>")
        except CaseValidationError as exc:
            errors.append(_translate_schema_error(exc))

    if errors or case is None:
        return DraftResult(
            ok=False, errors=tuple(errors), warnings=(), normalized=normalized, case=None,
        )

    warnings = tuple(
        FieldIssue(field=path, message=f"{path}:留空字段已标记为 {TODO_COLLAB},待临床老师补充")
        for path in case.placeholder_paths()
    )
    return DraftResult(ok=True, errors=(), warnings=warnings, normalized=normalized, case=case)
