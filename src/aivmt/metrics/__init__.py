"""Agreement & reliability metrics for the SQ1 validity analysis.

Public surface:
  - ICC: ``icc`` (point), ``icc_with_ci`` (McGraw & Wong F-based CI), ``bootstrap_icc_ci``.
  - Ordinal/nominal agreement: ``quadratic_weighted_kappa``, ``cohen_kappa``, ``percent_agreement``.
  - Decision consistency at a cut-score: ``decision_consistency``.
  - Bland-Altman: ``bland_altman``.
  - Generalizability theory + D-study: ``g_theory``.
  - Full SQ1 suite + artifacts: ``run_validity_suite``, ``headline_metrics``, ``write_validity_artifacts``.
"""

from __future__ import annotations

from .agreement import (
    DEFAULT_CUT_SCORE,
    DecisionConsistency,
    cohen_kappa,
    decision_consistency,
    percent_agreement,
    quadratic_weighted_kappa,
)
from .bland_altman import BlandAltman, bland_altman
from .gtheory import DStudyPoint, GTheoryResult, VarianceComponents, g_theory
from .icc import (
    DEFAULT_BOOTSTRAP_RESAMPLES,
    DEFAULT_CI_ALPHA,
    IccEstimate,
    IccKind,
    bootstrap_icc_ci,
    icc,
    icc_with_ci,
)
from .report import render_markdown_summary, write_validity_artifacts
from .validity import (
    ALL_DIMENSIONS,
    MISSING_DATA_HARD_THRESHOLD,
    ORDINAL_ANCHORS,
    ORDINAL_DIMENSIONS,
    OVERALL_DIMENSION,
    SEGUE_DOMAINS,
    SUBSCORE_DIMENSIONS,
    headline_metrics,
    run_validity_suite,
)

__all__ = [
    # ICC
    "icc",
    "icc_with_ci",
    "bootstrap_icc_ci",
    "IccEstimate",
    "IccKind",
    "DEFAULT_CI_ALPHA",
    "DEFAULT_BOOTSTRAP_RESAMPLES",
    # agreement
    "quadratic_weighted_kappa",
    "cohen_kappa",
    "percent_agreement",
    "decision_consistency",
    "DecisionConsistency",
    "DEFAULT_CUT_SCORE",
    # bland-altman
    "bland_altman",
    "BlandAltman",
    # g-theory
    "g_theory",
    "GTheoryResult",
    "VarianceComponents",
    "DStudyPoint",
    # validity suite
    "run_validity_suite",
    "headline_metrics",
    "render_markdown_summary",
    "write_validity_artifacts",
    "SEGUE_DOMAINS",
    "SUBSCORE_DIMENSIONS",
    "OVERALL_DIMENSION",
    "ALL_DIMENSIONS",
    "ORDINAL_DIMENSIONS",
    "ORDINAL_ANCHORS",
    "MISSING_DATA_HARD_THRESHOLD",
]
