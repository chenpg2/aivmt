"""Few-shot ablation arm: zero_shot must be byte-identical to the original prompts; few_shot must
prepend the SYNTHETIC exemplars, differ from zero_shot, and keep parsing strict (mock LLM only)."""

from __future__ import annotations

import pytest

from aivmt.llm.base import LLMOutputError
from aivmt.llm.mock import MockLLMClient
from aivmt.schemas import Case, ChecklistItem, Transcript, Turn
from aivmt.scoring import ScorerFactory, build_exemplar_block
from aivmt.scoring.checklist import _FEW_SHOT_EXEMPLARS as CHECKLIST_EX
from aivmt.scoring.checklist import _build_user as checklist_user
from aivmt.scoring.reasoning import _FEW_SHOT_EXEMPLARS as REASON_EX
from aivmt.scoring.reasoning import _build_user as reasoning_user
from aivmt.scoring.segue import _FEW_SHOT_EXEMPLARS as SEGUE_EX
from aivmt.scoring.segue import _build_user as segue_user


def _case(language: str = "en") -> Case:
    return Case(
        case_id="c1",
        title="Chest pain",
        language=language,  # type: ignore[arg-type]
        persona="...",
        history_checklist=(
            ChecklistItem("q_onset", "asks onset", 1.0),
            ChecklistItem("q_radiation", "asks radiation", 1.0),
        ),
    )


def _transcript(language: str = "en") -> Transcript:
    return Transcript(
        encounter_id="e1",
        case_id="c1",
        language=language,  # type: ignore[arg-type]
        turns=(
            Turn("student", "Hello, what brings you in?"),
            Turn("patient", "Chest pain since this morning."),
        ),
    )


# --- zero_shot is the byte-for-byte original ---------------------------------------------------
@pytest.mark.parametrize("language", ["en", "zh"])
def test_segue_zero_shot_byte_identical_to_original(language: str) -> None:
    """The original SEGUE user prompt (no exemplar prefix) is preserved exactly."""
    case, tr = _case(language), _transcript(language)
    from aivmt.scoring.base import render_transcript
    from aivmt.scoring.segue import SEGUE_DOMAINS, _ANCHORS

    anchors = _ANCHORS[language]
    rubric = "\n".join(f"- {d}: {anchors[d]}" for d in SEGUE_DOMAINS)
    schema = (
        '{"domains": {'
        + ", ".join(f'"{d}": 0.0' for d in SEGUE_DOMAINS)
        + '}, "rationale": {"<domain>": "<=12 words"}}'
    )
    expected = (
        f"SEGUE domains & anchors:\n{rubric}\n\n"
        f"TRANSCRIPT:\n{render_transcript(tr)}\n\n"
        f"Return JSON exactly in this shape (all 5 domains required): {schema}"
    )
    assert segue_user(case, tr, few_shot=False) == expected
    assert segue_user(case, tr) == expected  # default arg is zero_shot


@pytest.mark.parametrize("language", ["en", "zh"])
def test_reasoning_zero_shot_byte_identical_to_original(language: str) -> None:
    case, tr = _case(language), _transcript(language)
    from aivmt.scoring.base import render_transcript

    schema = '{"score": 0.0, "rationale": "<=20 words"}'
    expected = f"TRANSCRIPT:\n{render_transcript(tr)}\n\nReturn JSON exactly: {schema}"
    assert reasoning_user(case, tr, few_shot=False) == expected
    assert reasoning_user(case, tr) == expected


@pytest.mark.parametrize("language", ["en", "zh"])
def test_checklist_zero_shot_byte_identical_to_original(language: str) -> None:
    case, tr = _case(language), _transcript(language)
    from aivmt.scoring.base import render_transcript

    items = "\n".join(f"- {it.item_id}: {it.text}" for it in case.history_checklist)
    schema = '{"covered": ["item_id", ...], "evidence": {"item_id": "quote"}}'
    expected = (
        f"CHECKLIST:\n{items}\n\nTRANSCRIPT:\n{render_transcript(tr)}\n\n"
        f"Return JSON exactly (covered = item_ids the student covered): {schema}"
    )
    assert checklist_user(case, tr, few_shot=False) == expected
    assert checklist_user(case, tr) == expected


# --- few_shot prepends exemplars and differs ---------------------------------------------------
@pytest.mark.parametrize(
    "builder, exemplars, language",
    [
        (segue_user, SEGUE_EX, "en"),
        (segue_user, SEGUE_EX, "zh"),
        (reasoning_user, REASON_EX, "en"),
        (reasoning_user, REASON_EX, "zh"),
        (checklist_user, CHECKLIST_EX, "en"),
        (checklist_user, CHECKLIST_EX, "zh"),
    ],
)
def test_few_shot_contains_exemplars_and_differs(builder, exemplars, language: str) -> None:
    case, tr = _case(language), _transcript(language)
    zero = builder(case, tr, few_shot=False)
    few = builder(case, tr, few_shot=True)

    assert few != zero, "few_shot prompt must differ from zero_shot"
    assert few.endswith(zero), "few_shot must be the zero_shot prompt with an exemplar prefix"
    assert "SYNTHETIC" in few, "exemplar block must be explicitly labeled SYNTHETIC"
    # every exemplar excerpt AND its expected JSON appears verbatim in the few-shot prompt.
    for excerpt, expected_json in exemplars[language]:
        assert excerpt in few
        assert expected_json in few


def test_few_shot_is_deterministic() -> None:
    """Same inputs -> byte-identical few-shot prompt (reproducibility)."""
    case, tr = _case("en"), _transcript("en")
    assert segue_user(case, tr, few_shot=True) == segue_user(case, tr, few_shot=True)


def test_build_exemplar_block_empty_is_noop() -> None:
    assert build_exemplar_block(()) == ""


# --- scorer-level behavior on the mock LLM -----------------------------------------------------
@pytest.mark.parametrize("name", ["segue", "reasoning", "checklist"])
def test_variant_default_is_zero_shot(name: str) -> None:
    assert ScorerFactory(name).variant == "zero_shot"
    assert ScorerFactory(name, variant="few_shot").variant == "few_shot"


def test_unknown_variant_fails_loud() -> None:
    with pytest.raises(ValueError, match="unknown scorer variant"):
        ScorerFactory("segue", variant="three_shot")  # type: ignore[arg-type]


@pytest.mark.parametrize("name", ["segue", "reasoning", "checklist"])
@pytest.mark.parametrize("variant", ["zero_shot", "few_shot"])
def test_both_variants_produce_valid_scores_on_mock(name: str, variant: str) -> None:
    """Strict parsing/validation is unchanged: the mock's canned JSON scores cleanly either way."""
    case, tr = _case("en"), _transcript("en")
    scorer = ScorerFactory(name, variant=variant)  # type: ignore[arg-type]
    out = scorer.score(case, tr, MockLLMClient())
    assert out  # non-empty partial result dict


@pytest.mark.parametrize("name", ["segue", "reasoning"])
def test_strict_parsing_still_fails_loud(name: str) -> None:
    """A malformed model output still raises LLMOutputError under both variants (no zero-fallback)."""

    class BadLLM(MockLLMClient):
        def complete_json(self, system: str, user: str, *, task: str) -> dict:
            self.n_calls += 1
            return {}  # missing required keys

    case, tr = _case("en"), _transcript("en")
    with pytest.raises(LLMOutputError):
        ScorerFactory(name, variant="few_shot").score(case, tr, BadLLM())
