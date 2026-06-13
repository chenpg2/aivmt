"""Tests for the formal ClinicalCase schema and YAML migration (Stream B)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from aivmt.case_schema import (
    TODO_COLLAB,
    CaseValidationError,
    ClinicalCase,
    clinical_case_from_dict,
    is_placeholder,
    load_clinical_case,
)
from aivmt.llm import LLMFactory
from aivmt.pipeline import ScoringPipeline
from aivmt.schemas import Case, ChecklistItem, Telemetry, Transcript, Turn

ROOT = Path(__file__).resolve().parents[1]
CONF_CASE = ROOT / "conf" / "case"
CASE_IDS = (
    "example_chestpain_en",
    "example_chestpain_zh",
    "obgyn_ectopic_zh_01",
    "obgyn_aub_zh_01",
    "obgyn_vaginitis_zh_01",
)


def _valid_dict() -> dict:
    return {
        "case_id": "demo_01",
        "version": "1.0.0",
        "title": "Demo",
        "language": "en",
        "specialty": "cardiology",
        "difficulty": "moderate",
        "demographics": {"age": "40", "sex": "male"},
        "chief_complaint": "Chest pain",
        "hpi": {"onset": "1 hour ago", "character": "Crushing"},
        "pmh": [TODO_COLLAB],
        "medications": ["None"],
        "allergies": ["None"],
        "family_history": [TODO_COLLAB],
        "social_history": ["Non-smoker"],
        "hidden_info": [
            {"info_id": "hi_radiation", "content": "Radiates to left arm", "trigger": "Asked about radiation"},
        ],
        "history_checklist": [
            {"item_id": "q_onset", "text": "Ask onset", "weight": 1.0},
            {"item_id": "q_char", "text": "Ask character", "weight": 2.0},
        ],
        "emotional_state": "Anxious",
        "disclosure_profile": "Answers only when asked",
        "persona": "You are a 40-year-old man with chest pain.",
    }


def test_valid_dict_builds_clinical_case() -> None:
    case = clinical_case_from_dict(_valid_dict(), source="demo")
    assert isinstance(case, ClinicalCase)
    assert case.case_id == "demo_01"
    assert case.language == "en"
    assert case.demographics.age == "40"
    assert case.hpi.onset == "1 hour ago"
    assert len(case.hidden_info) == 1
    assert case.hidden_info[0].content == "Radiates to left arm"
    # unspecified optional fields default to the placeholder sentinel
    assert is_placeholder(case.hpi.severity)
    assert case.obgyn is None


@pytest.mark.parametrize("missing", ["case_id", "version", "chief_complaint", "language", "persona"])
def test_missing_required_field_raises_with_field_path(missing: str) -> None:
    data = _valid_dict()
    del data[missing]
    with pytest.raises(CaseValidationError) as exc:
        clinical_case_from_dict(data, source="demo.yaml")
    msg = str(exc.value)
    assert "demo.yaml" in msg
    assert missing in msg


def test_bad_language_is_error() -> None:
    data = _valid_dict()
    data["language"] = "fr"
    with pytest.raises(CaseValidationError, match="language"):
        clinical_case_from_dict(data, source="demo.yaml")


def test_empty_checklist_is_error() -> None:
    data = _valid_dict()
    data["history_checklist"] = []
    with pytest.raises(CaseValidationError, match="history_checklist"):
        clinical_case_from_dict(data, source="demo.yaml")


def test_duplicate_checklist_item_id_is_error() -> None:
    data = _valid_dict()
    data["history_checklist"].append({"item_id": "q_onset", "text": "dup", "weight": 1.0})
    with pytest.raises(CaseValidationError, match="duplicate"):
        clinical_case_from_dict(data, source="demo.yaml")


def test_non_numeric_weight_is_error() -> None:
    data = _valid_dict()
    data["history_checklist"][0]["weight"] = "heavy"
    with pytest.raises(CaseValidationError, match="weight"):
        clinical_case_from_dict(data, source="demo.yaml")


def test_out_of_range_weight_is_error() -> None:
    """Regression (portal review): a negative or oversized weight must be rejected at the
    single validation source so it can never distort the scoring normalisation."""
    from aivmt.case_schema import MAX_CHECKLIST_WEIGHT

    for bad in (-5, -0.01, MAX_CHECKLIST_WEIGHT + 0.01):
        data = _valid_dict()
        data["history_checklist"][0]["weight"] = bad
        with pytest.raises(CaseValidationError, match="weight"):
            clinical_case_from_dict(data, source="demo.yaml")
    # boundary values stay valid
    for ok in (0.0, MAX_CHECKLIST_WEIGHT):
        data = _valid_dict()
        data["history_checklist"][0]["weight"] = ok
        clinical_case_from_dict(data, source="demo.yaml")  # must not raise


def test_placeholder_paths_lists_todo_collab_fields() -> None:
    case = clinical_case_from_dict(_valid_dict(), source="demo")
    paths = set(case.placeholder_paths())
    assert "pmh[0]" in paths
    assert "family_history[0]" in paths
    assert "hpi.severity" in paths
    # populated fields are not reported
    assert "chief_complaint" not in paths
    assert "medications[0]" not in paths


def test_to_case_is_scoring_compatible() -> None:
    case = clinical_case_from_dict(_valid_dict(), source="demo")
    legacy = case.to_case()
    assert isinstance(legacy, Case)
    assert legacy.case_id == "demo_01"
    assert legacy.difficulty == "moderate"  # clinical-complexity label round-trips
    assert all(isinstance(it, ChecklistItem) for it in legacy.history_checklist)
    # checklist weights preserved exactly for the scorer
    assert [it.weight for it in legacy.history_checklist] == [1.0, 2.0]

    transcript = Transcript(
        encounter_id="enc_demo",
        case_id=legacy.case_id,
        language=legacy.language,
        turns=(Turn("student", "When did it start?"), Turn("patient", "An hour ago.")),
        telemetry=Telemetry(),
    )
    result = ScoringPipeline(LLMFactory("mock")).run(legacy, transcript)
    assert 0.0 <= result.score.history_completion <= 1.0
    assert len(result.score.item_scores) == 2


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_real_cases_load_under_schema(case_id: str) -> None:
    case = load_clinical_case(CONF_CASE / f"{case_id}.yaml")
    assert case.case_id.strip()
    assert case.version.strip()
    assert case.history_checklist  # non-empty
    assert case.persona_text.strip()


def test_obgyn_cases_have_specialty_block() -> None:
    for case_id in ("obgyn_ectopic_zh_01", "obgyn_aub_zh_01", "obgyn_vaginitis_zh_01"):
        case = load_clinical_case(CONF_CASE / f"{case_id}.yaml")
        assert case.specialty == "obgyn"
        assert case.obgyn is not None


def test_migration_preserves_verbatim_persona() -> None:
    """The free-text persona is retained verbatim for the live SP / legacy loader."""
    case = load_clinical_case(CONF_CASE / "obgyn_ectopic_zh_01.yaml")
    assert "停经6周多" in case.persona_text
    assert "三年前" in case.persona_text


def test_immutability() -> None:
    case = clinical_case_from_dict(_valid_dict(), source="demo")
    with pytest.raises(Exception):  # frozen dataclass
        case.case_id = "other"  # type: ignore[misc]


def test_construction_does_not_mutate_input() -> None:
    data = _valid_dict()
    snapshot = copy.deepcopy(data)
    clinical_case_from_dict(data, source="demo")
    assert data == snapshot
