"""Scorer-robustness analysis for SQ1.

Quantifies how stable the local-model automated scores are under two perturbations that must NOT
change a valid clinical judgement:
  - prompt-paraphrase sensitivity (semantics-preserving rewordings of the system prompt), and
  - stochasticity / test-retest reliability (repeated scorings across seeds at temp in {0, 0.3}).

Every number flows through the metrics package (read-only) and a registered harness phase, so the
robustness figures in the manuscript are reproducible from ``configs/seed.yaml``.
"""

from __future__ import annotations

from .core import (
    GoldedTranscript,
    paraphrase_sensitivity,
    score_overall,
    retest_reliability,
)
from .fixtures import build_golded_dataset, transcripts_only
from .paraphrase import (
    PARAPHRASE_TEMPLATES,
    ParaphraseTemplate,
    ParaphrasingClient,
    SystemTransform,
)
from .report import render_markdown, write_robustness_artifacts
from .types import ParaphraseSensitivity, RobustnessReport, TestRetest

__all__ = [
    # core
    "score_overall",
    "paraphrase_sensitivity",
    "retest_reliability",
    "GoldedTranscript",
    "build_golded_dataset",
    "transcripts_only",
    # paraphrase
    "PARAPHRASE_TEMPLATES",
    "ParaphraseTemplate",
    "ParaphrasingClient",
    "SystemTransform",
    # types
    "ParaphraseSensitivity",
    "TestRetest",
    "RobustnessReport",
    # report
    "render_markdown",
    "write_robustness_artifacts",
]
