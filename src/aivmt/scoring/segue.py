"""SEGUE communication scorer — anchored, item-level rubric, strict validation."""

from __future__ import annotations

from . import register_scorer
from .base import BaseScorer, Exemplar, build_exemplar_block, render_transcript, require
from ..llm.base import BaseLLMClient, LLMOutputError
from ..schemas import Case, Transcript

#: SEGUE framework domains.
SEGUE_DOMAINS: tuple[str, ...] = (
    "set_the_stage",
    "elicit_information",
    "give_information",
    "understand_perspective",
    "end_encounter",
)

_ANCHORS = {
    "en": {
        "set_the_stage": "greets, introduces self/role, sets agenda or obtains consent",
        "elicit_information": "open then focused questions; systematically gathers the history",
        "give_information": "explains findings/plan in lay terms; checks understanding",
        "understand_perspective": "explores patient ideas, concerns, expectations, feelings",
        "end_encounter": "summarizes, invites questions, states clear next steps",
    },
    "zh": {
        "set_the_stage": "问候、自我介绍/说明角色、说明议程或取得同意",
        "elicit_information": "先开放后聚焦提问;系统采集病史",
        "give_information": "用通俗语言解释发现/计划;确认患者理解",
        "understand_perspective": "探询患者的想法、担忧、期望与感受",
        "end_encounter": "总结、邀请提问、给出明确下一步",
    },
}

_SYS = {
    "en": (
        "You are a strict clinical-communication examiner using the SEGUE framework. Score each "
        "domain 0.0-1.0 (0=absent, 0.5=partial, 1.0=fully demonstrated) based ONLY on the "
        "transcript. Do not reward intentions that are not shown. Output a JSON object only."
    ),
    "zh": (
        "你是严格的临床沟通考官,使用 SEGUE 框架。仅依据转录为每个维度打 0.0-1.0 分"
        "(0=未做到,0.5=部分,1.0=充分体现),不要奖励未展示的意图。只输出JSON对象。"
    ),
}


# SYNTHETIC exemplars (NOT real patient data) for the few-shot ablation arm. Each pair is a short
# transcript excerpt mapped to the rubric JSON it should produce, illustrating the {0,0.5,1.0}
# anchors above (e.g. a clean greeting+agenda earns set_the_stage=1.0; an abrupt close earns
# end_encounter=0.0). They do not change the rubric, only show how to apply it.
_FEW_SHOT_EXEMPLARS: dict[str, tuple[Exemplar, ...]] = {
    "en": (
        (
            "Student: Hello, I'm a medical student; may I ask about today?\n"
            "Patient: I have a headache.\n"
            "Student: Thanks, that's all.",
            '{"domains": {"set_the_stage": 1.0, "elicit_information": 0.0, '
            '"give_information": 0.0, "understand_perspective": 0.0, "end_encounter": 0.0}, '
            '"rationale": {"set_the_stage": "greeted, introduced role, named agenda"}}',
        ),
        (
            "Student: What started the pain and where does it spread?\n"
            "Patient: Last night, to my jaw.\n"
            "Student: What worries you most about it?",
            '{"domains": {"set_the_stage": 0.0, "elicit_information": 1.0, '
            '"give_information": 0.0, "understand_perspective": 0.5, "end_encounter": 0.0}, '
            '"rationale": {"elicit_information": "focused onset/radiation history taken"}}',
        ),
    ),
    "zh": (
        (
            "学生:您好,我是医学生,今天能问您几个问题吗?\n"
            "患者:我头痛。\n"
            "学生:谢谢,就这样。",
            '{"domains": {"set_the_stage": 1.0, "elicit_information": 0.0, '
            '"give_information": 0.0, "understand_perspective": 0.0, "end_encounter": 0.0}, '
            '"rationale": {"set_the_stage": "问候、说明身份与议程"}}',
        ),
        (
            "学生:疼痛什么时候开始,会放射到哪里?\n"
            "患者:昨晚开始,放射到下巴。\n"
            "学生:您最担心的是什么?",
            '{"domains": {"set_the_stage": 0.0, "elicit_information": 1.0, '
            '"give_information": 0.0, "understand_perspective": 0.5, "end_encounter": 0.0}, '
            '"rationale": {"elicit_information": "聚焦起病与放射的病史采集"}}',
        ),
    ),
}


def _build_user(case: Case, transcript: Transcript, *, few_shot: bool = False) -> str:
    anchors = _ANCHORS[case.language]
    rubric = "\n".join(f"- {d}: {anchors[d]}" for d in SEGUE_DOMAINS)
    schema = (
        '{"domains": {'
        + ", ".join(f'"{d}": 0.0' for d in SEGUE_DOMAINS)
        + '}, "rationale": {"<domain>": "<=12 words"}}'
    )
    prefix = build_exemplar_block(_FEW_SHOT_EXEMPLARS[case.language]) if few_shot else ""
    return (
        f"{prefix}"
        f"SEGUE domains & anchors:\n{rubric}\n\n"
        f"TRANSCRIPT:\n{render_transcript(transcript)}\n\n"
        f"Return JSON exactly in this shape (all 5 domains required): {schema}"
    )


@register_scorer("segue")
class SegueScorer(BaseScorer):
    """Scores the five SEGUE communication domains with strict validation."""

    name = "segue"

    def score(self, case: Case, transcript: Transcript, llm: BaseLLMClient) -> dict:
        user = _build_user(case, transcript, few_shot=self.variant == "few_shot")
        out = llm.complete_json(_SYS[case.language], user, task="segue")
        require(isinstance(out.get("domains"), dict), "segue: missing 'domains' object")
        raw = out["domains"]
        segue: dict[str, float] = {}
        for d in SEGUE_DOMAINS:
            require(d in raw, f"segue: missing domain '{d}'")
            try:
                v = float(raw[d])
            except (TypeError, ValueError) as exc:
                raise LLMOutputError(f"segue: domain '{d}' not numeric: {raw[d]!r}") from exc
            require(0.0 <= v <= 1.0, f"segue: domain '{d}'={v} out of [0,1]")
            segue[d] = v
        return {"segue": segue}
