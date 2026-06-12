"""Mock-LLM unit test for the scoring pipeline (no model required)."""

from __future__ import annotations

from aivmt.llm import LLMFactory
from aivmt.pipeline import ScoringPipeline
from aivmt.scoring.segue import SEGUE_DOMAINS
from aivmt.schemas import Case, ChecklistItem, Telemetry, Transcript, Turn


def _case() -> Case:
    checklist = (
        ChecklistItem("q_onset", "询问起病时间与诱因"),
        ChecklistItem("q_character", "询问疼痛性质"),
        ChecklistItem("q_radiation", "询问放射部位"),
        ChecklistItem("q_associated", "询问伴随症状"),
        ChecklistItem("q_pmh", "询问既往史/危险因素"),
    )
    return Case(
        case_id="chestpain_zh_01",
        title="急性胸痛",
        language="zh",
        persona="58岁男性,突发胸骨后压榨样疼痛;仅在被问到时回答。",
        history_checklist=checklist,
        difficulty="moderate",
    )


def _transcript() -> Transcript:
    turns = (
        Turn("student", "您好,我是医学生,今天哪里不舒服?", 0.0, 3.0),
        Turn("patient", "我胸口疼。", 3.0, 5.0),
        Turn("student", "什么时候开始的?疼痛是什么性质?会放射吗?", 5.0, 9.0),
        Turn("patient", "两小时前,压着一样的疼,放射到左臂。", 9.0, 13.0),
        Turn("student", "我的鉴别诊断主要考虑急性冠脉综合征……", 13.0, 18.0),
    )
    return Transcript(
        encounter_id="enc_0001",
        case_id="chestpain_zh_01",
        language="zh",
        turns=turns,
        telemetry=Telemetry(duration_s=18.0, n_student_questions=4, n_voluntary_repeats=0),
    )


def test_pipeline_runs_with_mock() -> None:
    pipeline = ScoringPipeline(LLMFactory("mock"))
    result = pipeline.run(_case(), _transcript())

    assert result.model_id == "mock"
    assert result.encounter_id == "enc_0001"

    score = result.score
    assert 0.0 <= score.history_completion <= 1.0
    # mock covers 4 of 5 equally-weighted items
    assert abs(score.history_completion - 0.8) < 1e-9
    assert set(score.segue) == set(SEGUE_DOMAINS)
    assert 0.0 <= score.reasoning <= 1.0
    assert 0.0 <= score.overall <= 1.0
    assert len(score.item_scores) == 5

    assert result.feedback.summary
    assert result.feedback.improvements


def test_overall_is_weighted_combination() -> None:
    pipeline = ScoringPipeline(LLMFactory("mock"))
    score = pipeline.run(_case(), _transcript()).score
    segue_mean = sum(score.segue.values()) / len(score.segue)
    expected = 0.4 * score.history_completion + 0.4 * segue_mean + 0.2 * score.reasoning
    assert abs(score.overall - expected) < 1e-9
