"""Property tests for the persona compiler (Stream B personalization engine)."""

from __future__ import annotations

from pathlib import Path

import pytest

from aivmt.case_schema import (
    TODO_COLLAB,
    ClinicalCase,
    Demographics,
    HPI,
    HiddenInfoItem,
    RedHerring,
    is_placeholder,
    load_clinical_case,
)
from aivmt.persona import (
    DIFFICULTY_LEVELS,
    DIFFICULTY_PROFILES,
    compile_persona,
    compile_persona_sections,
    forthcoming_directives,
    wrap_persona_text,
)
from aivmt.llm import LLMFactory
from aivmt.patient import PatientAgent
from aivmt.schemas import Case, ChecklistItem

ROOT = Path(__file__).resolve().parents[1]
CONF_CASE = ROOT / "conf" / "case"

HIDDEN_FACT = "The pain radiates to the left arm and he is sweating."


def _synthetic_case(language: str = "en") -> ClinicalCase:
    """A controlled case whose hidden fact is a distinctive, easily-searched string."""
    return ClinicalCase(
        case_id="syn_01",
        version="1.0.0",
        language=language,  # type: ignore[arg-type]
        specialty="cardiology",
        title="Synthetic",
        demographics=Demographics(age="58", sex="male"),
        chief_complaint="Sudden crushing chest pain",
        hpi=HPI(onset="2 hours ago", character="Crushing", duration="2 hours"),
        pmh=("Hypertension",),
        medications=(TODO_COLLAB,),
        allergies=("None",),
        family_history=(TODO_COLLAB,),
        social_history=("Smoker",),
        hidden_info=(
            HiddenInfoItem(info_id="hi_1", content=HIDDEN_FACT, trigger="Asked about radiation/associated symptoms"),
        ),
        history_checklist=(ChecklistItem("q_onset", "Ask onset", 1.0),),
        emotional_state="Mildly anxious",
        disclosure_profile="Answers only when asked",
        persona_text="You are a 58-year-old man with chest pain.",
        red_herrings=(RedHerring(herring_id="rh_1", content="Mild seasonal cough", note="benign"),),
    )


# --- Property: hidden_info isolation ---------------------------------------- #
@pytest.mark.parametrize("difficulty", DIFFICULTY_LEVELS)
@pytest.mark.parametrize("language", ["en", "zh"])
def test_hidden_info_only_in_disclosure_not_opening(difficulty: str, language: str) -> None:
    case = _synthetic_case(language)
    compiled = compile_persona_sections(case, difficulty, language)
    assert HIDDEN_FACT in compiled.section("disclosure")
    assert HIDDEN_FACT not in compiled.section("opening")
    # and never leaks into the full opening rendering at any difficulty
    assert HIDDEN_FACT not in compiled.section("opening")


def test_opening_contains_chief_complaint_and_emotion() -> None:
    case = _synthetic_case("en")
    opening = compile_persona_sections(case, "standard").section("opening")
    assert "Sudden crushing chest pain" in opening
    assert "Mildly anxious" in opening


# --- Property: higher difficulty strictly reduces volunteered-info ----------- #
@pytest.mark.parametrize("language", ["en", "zh"])
def test_volunteer_directives_strictly_decrease(language: str) -> None:
    counts = [len(forthcoming_directives(d, language)) for d in ("easy", "standard", "hard")]
    assert counts == [2, 1, 0]
    assert counts[0] > counts[1] > counts[2]


@pytest.mark.parametrize("language", ["en", "zh"])
def test_compiled_behavior_volunteer_lines_strictly_decrease(language: str) -> None:
    case = _synthetic_case(language)

    def n_vol(diff: str) -> int:
        behavior = compile_persona_sections(case, diff, language).section("behavior")
        return sum(line in behavior for line in forthcoming_directives("easy", language))

    assert n_vol("easy") > n_vol("standard") > n_vol("hard")
    assert n_vol("hard") == 0


def test_volunteer_level_profile_monotonic() -> None:
    levels = [DIFFICULTY_PROFILES[d].volunteer_level for d in ("easy", "standard", "hard")]
    assert levels[0] > levels[1] > levels[2]


# --- Property: determinism --------------------------------------------------- #
@pytest.mark.parametrize("difficulty", DIFFICULTY_LEVELS)
@pytest.mark.parametrize("language", ["en", "zh"])
def test_deterministic_output(difficulty: str, language: str) -> None:
    case = _synthetic_case(language)
    first = compile_persona(case, difficulty, language)
    for _ in range(5):
        assert compile_persona(case, difficulty, language) == first


# --- Difficulty modulation knobs -------------------------------------------- #
def test_red_herrings_only_active_on_hard() -> None:
    case = _synthetic_case("en")
    assert "Mild seasonal cough" not in compile_persona_sections(case, "easy").section("distractors")
    assert "Mild seasonal cough" not in compile_persona_sections(case, "standard").section("distractors")
    assert "Mild seasonal cough" in compile_persona_sections(case, "hard").section("distractors")


def test_hard_requires_rapport_text_present() -> None:
    behavior = compile_persona_sections(_synthetic_case("en"), "hard").section("behavior")
    assert "trust" in behavior.lower()


def test_placeholder_fields_never_rendered() -> None:
    # medications/family_history are TODO_COLLAB in the synthetic case
    full = compile_persona(_synthetic_case("en"), "standard", "en")
    assert TODO_COLLAB not in full


def test_unknown_difficulty_fails_loud() -> None:
    with pytest.raises(ValueError, match="difficulty"):
        compile_persona(_synthetic_case("en"), "impossible")


def test_unknown_language_fails_loud() -> None:
    case = _synthetic_case("en")
    with pytest.raises(ValueError, match="language"):
        compile_persona(case, "standard", "fr")


# --- wrap_persona_text (legacy / live-session path) -------------------------- #
def test_wrap_persona_text_includes_persona_and_rules() -> None:
    out = wrap_persona_text("我胸口疼。", "zh", "standard")
    assert "我胸口疼。" in out
    assert "标准化病人" in out  # role framing present


def test_wrap_persona_text_deterministic() -> None:
    first = wrap_persona_text("chest pain persona", "en", "standard")
    assert wrap_persona_text("chest pain persona", "en", "standard") == first


def test_wrap_persona_text_difficulty_reduces_volunteer_lines() -> None:
    def n_vol(diff: str) -> int:
        out = wrap_persona_text("persona", "en", diff)
        return sum(line in out for line in forthcoming_directives("easy", "en"))

    assert n_vol("easy") > n_vol("standard") > n_vol("hard")


# --- Integration: real migrated cases compile cleanly ------------------------ #
REAL_CASE_IDS = (
    "example_chestpain_en",
    "example_chestpain_zh",
    "obgyn_ectopic_zh_01",
    "obgyn_aub_zh_01",
    "obgyn_vaginitis_zh_01",
)

#: Every compiled section a gated fact must NOT leak into. The disclosure section is the
#: ONLY place hidden_info may appear; in particular the always-disclosed background section
#: must not surface a fact the student is supposed to earn via its trigger question.
_NON_DISCLOSURE_SECTIONS = ("opening", "background", "persona", "distractors")


@pytest.mark.parametrize("case_id", REAL_CASE_IDS)
@pytest.mark.parametrize("difficulty", DIFFICULTY_LEVELS)
def test_real_cases_compile_and_isolate_hidden_info(case_id: str, difficulty: str) -> None:
    case = load_clinical_case(CONF_CASE / f"{case_id}.yaml")
    compiled = compile_persona_sections(case, difficulty)
    disclosure = compiled.section("disclosure")
    for item in case.hidden_info:
        if is_placeholder(item.content):  # placeholder facts are skipped by the compiler
            continue
        assert item.content in disclosure
        for section in _NON_DISCLOSURE_SECTIONS:
            assert item.content not in compiled.section(section), (
                f"hidden fact for {case_id} ({difficulty}) leaked into '{section}': {item.content}"
            )


# --- Fidelity: pertinent negatives survive the structured (persona_text-free) path --- #
_PERTINENT_NEGATIVES = {
    "obgyn_ectopic_zh_01": ("没有发热", "白带正常"),
    "obgyn_aub_zh_01": ("体重没有明显变化", "没有明显腹痛", "白带正常"),
    "obgyn_vaginitis_zh_01": ("没有发热", "没有腹痛", "小便正常"),
}


@pytest.mark.parametrize("case_id", sorted(_PERTINENT_NEGATIVES))
@pytest.mark.parametrize("difficulty", DIFFICULTY_LEVELS)
def test_pertinent_negatives_rendered_in_background(case_id: str, difficulty: str) -> None:
    """Negatives must be in the structured-compiled prompt, not only in persona_text.

    Guards the fidelity regression where '白带正常'/'无发热' lived only in the free-text
    persona and vanished from the structured ``from_clinical_case`` compile path.
    """
    case = load_clinical_case(CONF_CASE / f"{case_id}.yaml")
    compiled = compile_persona_sections(case, difficulty)
    background = compiled.section("background")
    full = compiled.render()
    for negative in _PERTINENT_NEGATIVES[case_id]:
        assert negative in case.pertinent_negatives
        assert negative in background
        assert negative in full


# --- PatientAgent uses the compiler (patient.py refactor) -------------------- #
def _legacy_case() -> Case:
    return Case(
        case_id="chestpain_zh_01",
        title="急性胸痛",
        language="zh",
        persona="58岁男性,突发胸骨后压榨样疼痛;仅在被问到时回答。",
        history_checklist=(ChecklistItem("q_onset", "询问起病时间"),),
        difficulty="moderate",
    )


def test_patient_agent_builds_system_via_compiler() -> None:
    agent = PatientAgent(_legacy_case(), LLMFactory("mock"))
    # the free-text persona is wrapped, role framing is present, behavior block applied
    assert "58岁男性" in agent._system
    assert "标准化病人" in agent._system
    assert agent.difficulty == "standard"


def test_patient_agent_mock_reply_roundtrip() -> None:
    agent = PatientAgent(_legacy_case(), LLMFactory("mock"))
    reply = agent.reply("您好,哪里不舒服?")
    assert isinstance(reply, str) and reply
    assert agent.reasoning_prompt  # bilingual reasoning probe still works


def test_patient_agent_from_clinical_case_compiles_structured_prompt() -> None:
    case = load_clinical_case(CONF_CASE / "example_chestpain_en.yaml")
    agent = PatientAgent.from_clinical_case(case, LLMFactory("mock"), difficulty="hard")
    assert agent.difficulty == "hard"
    # structured opening present; hidden fact stays out of the opening line
    assert "Sudden crushing retrosternal chest pain" in agent._system
    assert agent.reply("When did it start?")
