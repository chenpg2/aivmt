"""AI standardized-patient conversation engine.

The collection front-end (laptop now, device later) calls this to run one history-taking
encounter: the model plays the patient (answers only what is asked, never volunteers), then a
reasoning probe is posed, and the full turn-by-turn transcript is captured for scoring.
"""

from __future__ import annotations

from typing import Optional, cast

from .case_schema import ClinicalCase
from .llm.base import BaseLLMClient
from .persona import compile_persona, wrap_persona_text
from .schemas import Case, Speaker, Telemetry, Transcript, Turn

_REASONING_PROMPT = {
    "zh": "请说出你的鉴别诊断及理由,以及下一步建议的检查或处理。",
    "en": "Please state your differential diagnosis with reasoning, and the next steps you would take.",
}


class PatientAgent:
    """Stateful standardized-patient agent for one encounter.

    The SP system prompt is built by the persona compiler (:mod:`aivmt.persona`).
    Given the legacy flat ``Case`` it wraps the free-text persona; given a
    structured ``ClinicalCase`` (via :meth:`from_clinical_case`) it compiles the
    full structured prompt. ``difficulty`` is a compile-time behavioral knob.
    """

    def __init__(
        self,
        case: Case,
        llm: BaseLLMClient,
        *,
        difficulty: str = "standard",
        system: Optional[str] = None,
    ) -> None:
        self.case = case
        self.llm = llm
        self.difficulty = difficulty
        self._system = (
            system if system is not None
            else wrap_persona_text(case.persona, case.language, difficulty)
        )
        self._history: list[dict] = []  # chat messages for the patient model

    @classmethod
    def from_clinical_case(
        cls,
        clinical_case: ClinicalCase,
        llm: BaseLLMClient,
        *,
        difficulty: str = "standard",
        language: Optional[str] = None,
    ) -> "PatientAgent":
        """Build an agent from a structured case, compiling the full SP prompt."""
        system = compile_persona(clinical_case, difficulty, language)
        return cls(clinical_case.to_case(), llm, difficulty=difficulty, system=system)

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
