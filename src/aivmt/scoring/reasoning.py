"""Out-loud clinical-reasoning scorer — anchored rubric, strict validation."""

from __future__ import annotations

from . import register_scorer
from .base import BaseScorer, render_transcript, require
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


def _build_user(transcript: Transcript) -> str:
    schema = '{"score": 0.0, "rationale": "<=20 words"}'
    return f"TRANSCRIPT:\n{render_transcript(transcript)}\n\nReturn JSON exactly: {schema}"


@register_scorer("reasoning")
class ReasoningScorer(BaseScorer):
    """Scores the out-loud reasoning probe with strict validation."""

    name = "reasoning"

    def score(self, case: Case, transcript: Transcript, llm: BaseLLMClient) -> dict:
        out = llm.complete_json(_SYS[case.language], _build_user(transcript), task="reasoning")
        require("score" in out, "reasoning: missing 'score'")
        try:
            v = float(out["score"])
        except (TypeError, ValueError) as exc:
            raise LLMOutputError(f"reasoning: 'score' not numeric: {out.get('score')!r}") from exc
        require(0.0 <= v <= 1.0, f"reasoning: score={v} out of [0,1]")
        return {"reasoning": v}
