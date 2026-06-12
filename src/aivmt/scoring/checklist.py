"""History-taking checklist scorer (weighted completion + per-item evidence), strict validation."""

from __future__ import annotations

from . import register_scorer
from .base import BaseScorer, render_transcript, require
from ..llm.base import BaseLLMClient
from ..schemas import Case, ItemScore, Transcript

_SYS = {
    "en": (
        "You are a strict medical examiner. Decide which history-taking checklist items the "
        "student actually covered, based ONLY on the transcript. Output a JSON object only."
    ),
    "zh": (
        "你是严格的医学考官。仅依据转录,判断学生实际覆盖了问诊清单中的哪些条目。只输出JSON对象。"
    ),
}


def _build_user(case: Case, transcript: Transcript) -> str:
    items = "\n".join(f"- {it.item_id}: {it.text}" for it in case.history_checklist)
    schema = '{"covered": ["item_id", ...], "evidence": {"item_id": "quote"}}'
    return (
        f"CHECKLIST:\n{items}\n\nTRANSCRIPT:\n{render_transcript(transcript)}\n\n"
        f"Return JSON exactly (covered = item_ids the student covered): {schema}"
    )


@register_scorer("checklist")
class ChecklistScorer(BaseScorer):
    """Scores weighted history-taking checklist completion."""

    name = "checklist"

    def score(self, case: Case, transcript: Transcript, llm: BaseLLMClient) -> dict:
        out = llm.complete_json(_SYS[case.language], _build_user(case, transcript), task="checklist")
        require(isinstance(out.get("covered"), list), "checklist: missing 'covered' list")
        covered = {str(x) for x in out["covered"]}
        evidence = out.get("evidence") or {}
        require(isinstance(evidence, dict), "checklist: 'evidence' must be an object")

        item_scores = tuple(
            ItemScore(it.item_id, it.item_id in covered, evidence.get(it.item_id))
            for it in case.history_checklist
        )
        total_w = sum(it.weight for it in case.history_checklist) or 1.0
        got_w = sum(it.weight for it in case.history_checklist if it.item_id in covered)
        return {"history_completion": got_w / total_w, "item_scores": item_scores}
