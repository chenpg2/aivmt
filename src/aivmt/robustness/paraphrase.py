"""Prompt-paraphrase sensitivity for scorers.

A robust scorer should give the SAME score regardless of harmless rewordings of its system-prompt
wrapper (politeness, ordering of meta-instructions, phrasing of "output JSON only"). We author a
small set of SYNTHETIC paraphrase templates that rewrap the scorer's *existing* system prompt
WITHOUT touching the rubric, anchors, or schema, then measure how much ICC-vs-gold moves across
them. Large movement = brittle prompt; tight movement = the rubric, not the wording, drives scores.

The paraphrase is applied transparently at the LLM-client boundary (``ParaphrasingClient``), so
every scorer's own parsing/validation runs unchanged — we never duplicate or weaken it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..llm.base import BaseLLMClient

#: A system-prompt transform: takes the scorer's base system prompt, returns a reworded wrapper.
SystemTransform = Callable[[str], str]


@dataclass(frozen=True)
class ParaphraseTemplate:
    """A named, semantics-preserving rewrap of a scorer's system prompt (SYNTHETIC wording)."""

    name: str
    transform: SystemTransform


# SYNTHETIC paraphrase templates (wording only — NO rubric/anchor/schema changes). ``p0_identity``
# is the registered baseline so the spread always includes the un-paraphrased prompt. The rewraps
# only add meta-instructions (be careful, output valid JSON, no prose) that the prompts already
# imply; they must never add or remove scoring criteria.
_PREFIX = {
    "p1_careful": "Read carefully and reason step by step internally before answering. ",
    "p2_concise": "Be precise and concise. ",
    "p3_neutral": "Remain objective and avoid leniency or harshness. ",
    "p4_format": "Follow the requested output format strictly. ",
    "p5_evidence": "Base every judgement only on explicit evidence in the transcript. ",
}
_SUFFIX = {
    "p1_careful": " Return only a single valid JSON object.",
    "p2_concise": " Output JSON only, no commentary.",
    "p3_neutral": " Respond with one JSON object and nothing else.",
    "p4_format": " Emit exactly one JSON object; do not wrap it in code fences.",
    "p5_evidence": " Give your answer as a JSON object only.",
}


def _make_transform(prefix: str, suffix: str) -> SystemTransform:
    def _t(base: str) -> str:
        return f"{prefix}{base}{suffix}"

    return _t


#: Registered paraphrase templates (>=5 non-identity + identity baseline). Order is fixed for
#: reproducibility. The base system prompt already says "Output a JSON object only", so the
#: identity transform is a genuine member of the family, not a special case.
PARAPHRASE_TEMPLATES: tuple[ParaphraseTemplate, ...] = (
    ParaphraseTemplate("p0_identity", lambda base: base),
    *(
        ParaphraseTemplate(name, _make_transform(_PREFIX[name], _SUFFIX[name]))
        for name in ("p1_careful", "p2_concise", "p3_neutral", "p4_format", "p5_evidence")
    ),
)


class ParaphrasingClient(BaseLLMClient):
    """Wraps any LLM client and applies a system-prompt ``transform`` to every ``complete_json``.

    Transparent decorator: the wrapped scorer sees an ordinary client, its validation runs intact,
    and observability counters reflect the underlying client (we delegate, never reset them).
    """

    def __init__(self, inner: BaseLLMClient, transform: SystemTransform) -> None:
        self._inner = inner
        self._transform = transform
        self.model_id = inner.model_id

    # Counters live on the inner client; expose them so callers read real call/parse stats.
    @property
    def n_calls(self) -> int:  # type: ignore[override]
        return self._inner.n_calls

    @property
    def n_parse_failures(self) -> int:  # type: ignore[override]
        return self._inner.n_parse_failures

    @property
    def n_refusals(self) -> int:  # type: ignore[override]
        return self._inner.n_refusals

    def complete_json(self, system: str, user: str, *, task: str) -> dict:
        return self._inner.complete_json(self._transform(system), user, task=task)

    def chat_text(self, system: str, messages: list[dict]) -> str:
        return self._inner.chat_text(self._transform(system), messages)
