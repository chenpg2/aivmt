"""Out-loud clinical-reasoning scorer — anchored rubric, strict validation."""

from __future__ import annotations

from . import register_scorer
from .base import BaseScorer, Exemplar, build_exemplar_block, render_transcript, require
from ..llm.base import BaseLLMClient, LLMOutputError
from ..schemas import Case, Transcript

_SYS = {
    "en": (
        "You are a strict examiner of clinical reasoning. Score the student's spoken differential "
        "and justification 0.0-1.0 (0.0=none; 0.5=a diagnosis named without justification; "
        "1.0=a structured differential with justification AND appropriate next steps), based ONLY "
        "on the transcript. Output a JSON object only."
    ),
    "zh": (
        "你是严格的临床推理考官。仅依据转录,为学生口头给出的鉴别诊断与理由打 0.0-1.0 分"
        "(0.0=没有;0.5=只说出诊断但无依据;1.0=有结构的鉴别诊断+依据+恰当的下一步)。只输出JSON对象。"
    ),
}


# SYNTHETIC exemplars (NOT real patient data) for the few-shot ablation arm. They illustrate the
# 0.0 / 0.5 / 1.0 anchors of the reasoning rubric (named diagnosis without justification = 0.5;
# structured differential + justification + next steps = 1.0). They do not change the rubric.
_FEW_SHOT_EXEMPLARS: dict[str, tuple[Exemplar, ...]] = {
    "en": (
        (
            "Student: I think it's a heart attack.\nPatient: Okay.",
            '{"score": 0.5, "rationale": "diagnosis named, no justification or next steps"}',
        ),
        (
            "Student: Given crushing pain radiating to the arm with sweating, I'm most concerned "
            "about acute coronary syndrome over reflux; I'll get an ECG and troponin now.",
            '{"score": 1.0, "rationale": "ranked differential with justification and next steps"}',
        ),
    ),
    "zh": (
        (
            "学生:我觉得是心梗。\n患者:好的。",
            '{"score": 0.5, "rationale": "只说出诊断,无依据与下一步"}',
        ),
        (
            "学生:压榨性胸痛放射到手臂伴出汗,我最担心急性冠脉综合征而非反流;"
            "现在做心电图和肌钙蛋白。",
            '{"score": 1.0, "rationale": "有依据的分级鉴别诊断并给出下一步"}',
        ),
    ),
}


def _build_user(case: Case, transcript: Transcript, *, few_shot: bool = False) -> str:
    schema = '{"score": 0.0, "rationale": "<=20 words"}'
    prefix = build_exemplar_block(_FEW_SHOT_EXEMPLARS[case.language]) if few_shot else ""
    return f"{prefix}TRANSCRIPT:\n{render_transcript(transcript)}\n\nReturn JSON exactly: {schema}"


@register_scorer("reasoning")
class ReasoningScorer(BaseScorer):
    """Scores the out-loud reasoning probe with strict validation."""

    name = "reasoning"

    def score(self, case: Case, transcript: Transcript, llm: BaseLLMClient) -> dict:
        user = _build_user(case, transcript, few_shot=self.variant == "few_shot")
        out = llm.complete_json(_SYS[case.language], user, task="reasoning")
        require("score" in out, "reasoning: missing 'score'")
        try:
            v = float(out["score"])
        except (TypeError, ValueError) as exc:
            raise LLMOutputError(f"reasoning: 'score' not numeric: {out.get('score')!r}") from exc
        require(0.0 <= v <= 1.0, f"reasoning: score={v} out of [0,1]")
        return {"reasoning": v}
