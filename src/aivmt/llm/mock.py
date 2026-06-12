"""Deterministic mock LLM client for unit tests / offline dry runs (no model required)."""

from __future__ import annotations

from . import register_llm
from .base import BaseLLMClient

# Canned, deterministic responses keyed by sub-task (scoring).
_CANNED: dict[str, dict] = {
    "checklist": {
        "covered": ["q_onset", "q_character", "q_radiation", "q_associated"],
        "evidence": {"q_onset": "学生询问了起病时间"},
    },
    "segue": {
        "domains": {
            "set_the_stage": 1.0,
            "elicit_information": 0.8,
            "give_information": 0.5,
            "understand_perspective": 0.6,
            "end_encounter": 1.0,
        }
    },
    "reasoning": {"score": 0.75, "rationale": "鉴别诊断结构合理但解释略简。"},
    "feedback": {
        "summary": "整体问诊较系统,沟通到位,鉴别诊断可更充分。",
        "strengths": ["开场与信息采集规范", "对患者视角有回应"],
        "improvements": ["补充危险因素询问", "解释鉴别诊断的依据"],
    },
}


@register_llm("mock")
class MockLLMClient(BaseLLMClient):
    """Returns fixed JSON per task and a canned patient line; used for deterministic testing."""

    def __init__(self, model_id: str = "mock", **_: object) -> None:
        self.model_id = model_id
        self.n_calls = 0
        self.n_parse_failures = 0
        self.n_refusals = 0

    def complete_json(self, system: str, user: str, *, task: str) -> dict:
        self.n_calls += 1
        return dict(_CANNED.get(task, {}))

    def chat_text(self, system: str, messages: list[dict]) -> str:
        self.n_calls += 1
        return "我这里有点不舒服。"  # canned short patient reply for offline runs
