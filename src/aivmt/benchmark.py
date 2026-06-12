"""Pre-registered model selection (pre-reg §8).

Run the scoring pipeline over a gold-labeled set of encounters with each candidate
open-weight model, then rank models by agreement (ICC) of the system's overall score
with the gold (faculty) score. The selection criterion (highest ICC) is fixed in advance;
report ALL candidates' ICCs — no post-hoc swapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

import numpy as np

from .llm.base import BaseLLMClient
from .metrics import icc
from .pipeline import ScoringPipeline
from .schemas import Case, Transcript
from .utils import get_logger

logger = get_logger(__name__)

#: One gold-labeled example: (case, transcript, gold_overall_score in [0, 1]).
GoldExample = Tuple[Case, Transcript, float]


@dataclass(frozen=True)
class BenchmarkResult:
    """Agreement of one model's automated scores with the gold (faculty) scores."""

    model_id: str
    n: int
    icc2_1: float
    icc2_k: float


def _icc_key(result: BenchmarkResult) -> float:
    """Rank key: treat nan as worst so degenerate models sort last."""
    return np.nan_to_num(result.icc2_1, nan=-1.0)


def run_model_benchmark(
    dataset: Sequence[GoldExample],
    llms: Sequence[BaseLLMClient],
) -> list[BenchmarkResult]:
    """Score the dataset with each model and rank by ICC(2,1) vs gold (descending)."""
    if not dataset:
        raise ValueError("dataset is empty")
    golds = [gold for _, _, gold in dataset]

    results: list[BenchmarkResult] = []
    for llm in llms:
        pipeline = ScoringPipeline(llm)
        system_scores = [
            pipeline.run(case, transcript).score.overall for case, transcript, _ in dataset
        ]
        matrix = np.column_stack([system_scores, golds])
        result = BenchmarkResult(
            model_id=llm.model_id,
            n=len(dataset),
            icc2_1=icc(matrix, "icc2_1"),
            icc2_k=icc(matrix, "icc2_k"),
        )
        logger.info("model=%s n=%d ICC(2,1)=%.3f", result.model_id, result.n, result.icc2_1)
        results.append(result)

    return sorted(results, key=_icc_key, reverse=True)


def select_best(results: Sequence[BenchmarkResult]) -> BenchmarkResult:
    """Return the model with the highest ICC(2,1) (pre-registered criterion)."""
    if not results:
        raise ValueError("no benchmark results")
    return max(results, key=_icc_key)
