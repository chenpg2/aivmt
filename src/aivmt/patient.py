"""AI standardized-patient conversation engine.

The collection front-end (laptop now, device later) calls this to run one history-taking
encounter: the model plays the patient (answers only what is asked, never volunteers), then a
reasoning probe is posed, and the full turn-by-turn transcript is captured for scoring.
"""

from __future__ import annotations

from typing import cast

from .llm.base import BaseLLMClient
from .schemas import Case, Speaker, Telemetry, Transcript, Turn

_PATIENT_SYS = {
    "zh": (
        "你在扮演一位标准化病人,用于训练医学生问诊。严格遵守:\n"
        "1) 只回答学生明确问到的内容,绝不主动透露其他信息;\n"
        "2) 用第一人称、口语化、简短(1-3句)地回答,符合人物设定;\n"
        "3) 不要使用医学术语;听不懂时可以反问;\n"
        "4) 不要给诊断、不要评价学生、不要跳出角色。\n"
        "你的人物设定如下:\n{persona}"
    ),
    "en": (
        "You are role-playing a standardized patient to train medical students. Strictly:\n"
        "1) Answer ONLY what the student explicitly asks; never volunteer other information;\n"
        "2) Reply in the first person, colloquial and short (1-3 sentences), in character;\n"
        "3) Avoid medical jargon; you may ask for clarification;\n"
        "4) Do not give a diagnosis, do not evaluate the student, do not break character.\n"
        "Your persona:\n{persona}"
    ),
}

_REASONING_PROMPT = {
    "zh": "请说出你的鉴别诊断及理由,以及下一步建议的检查或处理。",
    "en": "Please state your differential diagnosis with reasoning, and the next steps you would take.",
}


class PatientAgent:
    """Stateful standardized-patient agent for one encounter."""

    def __init__(self, case: Case, llm: BaseLLMClient) -> None:
        self.case = case
        self.llm = llm
        self._system = _PATIENT_SYS[case.language].format(persona=case.persona)
        self._history: list[dict] = []  # chat messages for the patient model

    def reply(self, student_utterance: str) -> str:
        """Return the patient's spoken reply to one student utterance."""
        self._history.append({"role": "user", "content": student_utterance})
        text = self.llm.chat_text(self._system, self._history)
        self._history.append({"role": "assistant", "content": text})
        return text

    @property
    def reasoning_prompt(self) -> str:
        return _REASONING_PROMPT[self.case.language]


def build_transcript(
    encounter_id: str,
    case: Case,
    turns: list[tuple[str, str]],
    telemetry: Telemetry,
) -> Transcript:
    """Assemble a Transcript from (speaker, text) pairs."""
    return Transcript(
        encounter_id=encounter_id,
        case_id=case.case_id,
        language=case.language,
        turns=tuple(Turn(cast(Speaker, spk), txt, 0.0, 0.0) for spk, txt in turns),
        telemetry=telemetry,
    )
