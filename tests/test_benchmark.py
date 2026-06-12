"""Tests for the model-selection benchmark using a deterministic fake LLM."""

from __future__ import annotations

import math

from aivmt.benchmark import BenchmarkResult, run_model_benchmark, select_best
from aivmt.llm.base import BaseLLMClient
from aivmt.scoring.segue import SEGUE_DOMAINS
from aivmt.schemas import Case, ChecklistItem, Transcript, Turn


class _FakeLLM(BaseLLMClient):
    """Deterministic LLM whose scores grow with transcript length (+ a per-model bias)."""

    def __init__(self, model_id: str, bias: float = 0.0) -> None:
        self.model_id = model_id
        self.bias = bias

    def complete_json(self, system: str, user: str, *, task: str) -> dict:
        s = min(1.0, max(0.0, len(user) / 3000.0 + self.bias))
        if task == "checklist":
            return {"covered": []}
        if task == "segue":
            return {"domains": {d: s for d in SEGUE_DOMAINS}}
        if task == "reasoning":
            return {"score": s}
        return {"summary": "ok"}


def _case() -> Case:
    return Case(
        case_id="c1",
        title="t",
        language="zh",
        persona="p",
        history_checklist=(ChecklistItem("q1", "x"),),
    )


def _dataset():
    case = _case()
    examples = []
    golds = [0.1, 0.2, 0.35, 0.5, 0.65, 0.8]
    for i, gold in enumerate(golds):
        # transcripts of strictly increasing length -> increasing fake scores
        turns = tuple(
            Turn("student", "请问" + "症状描述" * (j + 1), 0.0, 1.0) for j in range(i + 1)
        )
        examples.append(
            (case, Transcript(f"enc_{i}", "c1", "zh", turns), gold)
        )
    return examples


def test_benchmark_returns_one_result_per_model() -> None:
    llms = [_FakeLLM("model_a"), _FakeLLM("model_b", bias=0.05)]
    results = run_model_benchmark(_dataset(), llms)

    assert len(results) == 2
    assert {r.model_id for r in results} == {"model_a", "model_b"}
    for r in results:
        assert isinstance(r, BenchmarkResult)
        assert r.n == 6
        assert math.isfinite(r.icc2_1)
        assert math.isfinite(r.icc2_k)


def test_benchmark_sorted_descending_and_select_best() -> None:
    llms = [_FakeLLM("model_a"), _FakeLLM("model_b", bias=0.05)]
    results = run_model_benchmark(_dataset(), llms)
    assert results[0].icc2_1 >= results[1].icc2_1
    assert select_best(results).icc2_1 == results[0].icc2_1
