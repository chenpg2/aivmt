"""SQ1 validity suite: assemble the full encounters x raters analysis from system + faculty scores.

Pure, file-format-agnostic orchestrator. Callers supply:
  - ``system_by_id``: encounter_id -> {dimension: score} for the local model (overall + SEGUE
    domains + history_completion + reasoning).
  - ``faculty_rows``: long-format rating rows (one per encounter x rater) using the columns of
    ``aivmt.dataio.FACULTY_SHEET_FIELDS``.

It builds the persons x raters matrix WITHOUT collapsing raters, then reports system-vs-consensus
ICC (overall + every subscore), pairwise system-vs-each-rater ICC, the inter-faculty ceiling ICC,
quadratic weighted kappa on the ordinal-anchored dimensions, Bland-Altman, G-theory + D-study, and
pass/fail decision consistency. Missing rater cells are handled listwise with an explicit count and
a hard error above ``MISSING_DATA_HARD_THRESHOLD`` — never silently imputed.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Mapping, Sequence

import numpy as np

from .agreement import DEFAULT_CUT_SCORE, decision_consistency, quadratic_weighted_kappa
from .bland_altman import bland_altman
from .gtheory import g_theory
from .icc import bootstrap_icc_ci, icc_with_ci

logger = logging.getLogger(__name__)

__all__ = [
    "SEGUE_DOMAINS",
    "SUBSCORE_DIMENSIONS",
    "OVERALL_DIMENSION",
    "ORDINAL_DIMENSIONS",
    "ORDINAL_ANCHORS",
    "MISSING_DATA_HARD_THRESHOLD",
    "run_validity_suite",
    "headline_metrics",
]

#: SEGUE communication domains (canonical source: aivmt.scoring.segue.SEGUE_DOMAINS).
SEGUE_DOMAINS: tuple[str, ...] = (
    "set_the_stage",
    "elicit_information",
    "give_information",
    "understand_perspective",
    "end_encounter",
)
#: Continuous subscores shared by system and faculty.
SUBSCORE_DIMENSIONS: tuple[str, ...] = ("history_completion", "reasoning")
OVERALL_DIMENSION: str = "overall"
#: Every dimension analysed for system-vs-consensus ICC.
ALL_DIMENSIONS: tuple[str, ...] = (OVERALL_DIMENSION, *SEGUE_DOMAINS, *SUBSCORE_DIMENSIONS)
#: Dimensions that are anchored to discrete levels and so support quadratic weighted kappa.
ORDINAL_DIMENSIONS: tuple[str, ...] = (*SEGUE_DOMAINS, "reasoning")
#: Anchor levels for the ordinal SEGUE/reasoning rubric (config constant). QWK maps to {0,1,2}.
ORDINAL_ANCHORS: tuple[float, ...] = (0.0, 0.5, 1.0)
#: Above this fraction of missing rater cells the analysis aborts (prereg: sensitivity if >10%).
MISSING_DATA_HARD_THRESHOLD: float = 0.10


def _to_float(value: object, ctx: str) -> float:
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{ctx}: non-numeric value {value!r}") from exc
    if not np.isfinite(out):
        raise ValueError(f"{ctx}: non-finite value {value!r}")
    if not 0.0 <= out <= 1.0:
        raise ValueError(f"{ctx}: value {out} outside [0, 1]")
    return out


def _ordinalize(value: float) -> int:
    """Map a [0,1] score to the index of the nearest ordinal anchor."""
    diffs = [abs(value - a) for a in ORDINAL_ANCHORS]
    return int(np.argmin(diffs))


def _build_matrices(
    system_by_id: Mapping[str, Mapping[str, float]],
    faculty_rows: Sequence[Mapping[str, object]],
) -> dict:
    """Build complete-case persons x raters matrices per dimension (listwise, fail-loud)."""
    raters = sorted({str(r["rater_id"]) for r in faculty_rows if r.get("rater_id")})
    if len(raters) < 2:
        raise ValueError(f"need >=2 distinct faculty raters for the validity suite (got {len(raters)})")

    by_enc: dict[str, dict[str, Mapping[str, object]]] = defaultdict(dict)
    for row in faculty_rows:
        eid = str(row.get("encounter_id") or "")
        rid = str(row.get("rater_id") or "")
        if not eid:
            continue
        if not rid:
            raise ValueError(f"faculty row for encounter {eid!r} has no rater_id (malformed)")
        if rid in by_enc[eid]:
            raise ValueError(f"duplicate rating: encounter {eid!r} rater {rid!r}")
        by_enc[eid][rid] = row

    candidates = sorted(set(by_enc) & set(system_by_id))
    if not candidates:
        raise ValueError("no encounters have BOTH a system score and faculty ratings")

    total_cells = len(candidates) * len(raters)
    missing_cells = sum(len(raters) - len(by_enc[eid]) for eid in candidates)
    missing_fraction = missing_cells / total_cells if total_cells else 0.0
    if missing_fraction > MISSING_DATA_HARD_THRESHOLD:
        raise ValueError(
            f"missing rater cells {missing_fraction:.1%} exceed the "
            f"{MISSING_DATA_HARD_THRESHOLD:.0%} threshold; no silent imputation — "
            "collect the outstanding ratings or pre-register a sensitivity analysis"
        )

    complete = [eid for eid in candidates if len(by_enc[eid]) == len(raters)]
    dropped = len(candidates) - len(complete)
    logger.info(
        "validity suite: %d candidate encounters x %d raters; %d cells missing (%.1f%%); "
        "%d dropped listwise; %d complete-case encounters retained",
        len(candidates), len(raters), missing_cells, 100.0 * missing_fraction, dropped, len(complete),
    )
    if len(complete) < 2:
        raise ValueError(f"need >=2 complete-case encounters for ICC (got {len(complete)})")

    faculty_matrix: dict[str, np.ndarray] = {}
    system_vector: dict[str, np.ndarray] = {}
    for dim in ALL_DIMENSIONS:
        sys_vals = []
        fac_rows = []
        for eid in complete:
            sdim = system_by_id[eid]
            if dim not in sdim:
                raise ValueError(f"system encounter {eid!r} missing dimension {dim!r}")
            sys_vals.append(_to_float(sdim[dim], f"system[{eid}].{dim}"))
            fac_rows.append(
                [_to_float(by_enc[eid][rid].get(dim), f"faculty[{eid},{rid}].{dim}") for rid in raters]
            )
        system_vector[dim] = np.asarray(sys_vals, dtype=float)
        faculty_matrix[dim] = np.asarray(fac_rows, dtype=float)

    return {
        "raters": raters,
        "complete_encounters": complete,
        "missing_cells": int(missing_cells),
        "missing_fraction": float(missing_fraction),
        "dropped_listwise": int(dropped),
        "n_candidate_encounters": len(candidates),
        "faculty_matrix": faculty_matrix,
        "system_vector": system_vector,
    }


def run_validity_suite(
    system_by_id: Mapping[str, Mapping[str, float]],
    faculty_rows: Sequence[Mapping[str, object]],
    seed: int,
    cut_score: float = DEFAULT_CUT_SCORE,
) -> dict:
    """Run the full SQ1 validity suite and return a JSON-serializable result dict.

    Args:
        system_by_id: encounter_id -> {dimension: score}.
        faculty_rows: long-format faculty rating rows (FACULTY_SHEET_FIELDS columns).
        seed: bootstrap seed (MUST come from configs/seed.yaml, never hardcoded).
        cut_score: pass/fail cut for decision consistency.

    Returns:
        Nested dict with every analysis plus a ``missing_data`` audit block.
    """
    built = _build_matrices(system_by_id, faculty_rows)
    raters: list[str] = built["raters"]
    faculty_matrix: dict[str, np.ndarray] = built["faculty_matrix"]
    system_vector: dict[str, np.ndarray] = built["system_vector"]
    n = len(built["complete_encounters"])

    # 1. System vs faculty-consensus ICC for overall + every subscore (no rater collapsing for ICC).
    consensus: dict[str, np.ndarray] = {d: faculty_matrix[d].mean(axis=1) for d in faculty_matrix}
    system_vs_consensus: dict[str, dict] = {}
    for dim in faculty_matrix:
        paired = np.column_stack([system_vector[dim], consensus[dim]])
        system_vs_consensus[dim] = {
            "icc2_1": icc_with_ci(paired, "icc2_1").to_dict(),
            "icc2_k": icc_with_ci(paired, "icc2_k").to_dict(),
        }

    # 2. Pairwise system-vs-each-rater ICC on the overall score.
    overall_fac = faculty_matrix[OVERALL_DIMENSION]
    pairwise = {
        rid: icc_with_ci(
            np.column_stack([system_vector[OVERALL_DIMENSION], overall_fac[:, j]]), "icc2_1"
        ).to_dict()
        for j, rid in enumerate(raters)
    }

    # 3. Inter-faculty ceiling ICC on the overall score (raters as the k columns).
    inter_faculty = {
        "icc2_1": icc_with_ci(overall_fac, "icc2_1").to_dict(),
        "icc2_k": icc_with_ci(overall_fac, "icc2_k").to_dict(),
    }

    # 4. Quadratic weighted kappa on ordinal-anchored dimensions (system vs consensus).
    qwk: dict[str, float] = {}
    max_cat = len(ORDINAL_ANCHORS) - 1
    for dim in ORDINAL_DIMENSIONS:
        sys_ord = [_ordinalize(v) for v in system_vector[dim]]
        con_ord = [_ordinalize(v) for v in consensus[dim]]
        qwk[dim] = quadratic_weighted_kappa(sys_ord, con_ord, min_rating=0, max_rating=max_cat)

    # 5. Bland-Altman on the overall score (system vs consensus).
    ba = bland_altman(system_vector[OVERALL_DIMENSION], consensus[OVERALL_DIMENSION]).to_dict()

    # 6. G-theory + D-study on the faculty overall matrix (persons x raters).
    gt = g_theory(overall_fac).to_dict()

    # 7. Decision consistency at the cut-score (system vs consensus, overall).
    dc = decision_consistency(
        system_vector[OVERALL_DIMENSION], consensus[OVERALL_DIMENSION], cut_score
    ).to_dict()

    # 8. Bootstrap CI for the headline overall ICC(2,1) — independent cross-check of the F-based CI.
    boot = bootstrap_icc_ci(
        np.column_stack([system_vector[OVERALL_DIMENSION], consensus[OVERALL_DIMENSION]]),
        seed=seed,
        kind="icc2_1",
    ).to_dict()

    return {
        "n_encounters": int(n),
        "n_raters": len(raters),
        "raters": raters,
        "seed": int(seed),
        "missing_data": {
            "n_candidate_encounters": built["n_candidate_encounters"],
            "missing_cells": built["missing_cells"],
            "missing_fraction": built["missing_fraction"],
            "dropped_listwise": built["dropped_listwise"],
            "threshold": MISSING_DATA_HARD_THRESHOLD,
        },
        "system_vs_consensus_icc": system_vs_consensus,
        "pairwise_system_vs_rater_icc": pairwise,
        "inter_faculty_ceiling_icc": inter_faculty,
        "quadratic_weighted_kappa": qwk,
        "bland_altman_overall": ba,
        "g_theory_overall": gt,
        "decision_consistency_overall": dc,
        "bootstrap_overall_icc2_1": boot,
    }


def headline_metrics(result: Mapping[str, object]) -> dict:
    """Flatten the headline numbers (overall ICC, ceiling, decision kappa) for the evidence table."""
    svc = result["system_vs_consensus_icc"][OVERALL_DIMENSION]  # type: ignore[index]
    ceiling = result["inter_faculty_ceiling_icc"]  # type: ignore[index]
    dc = result["decision_consistency_overall"]  # type: ignore[index]
    return {
        "n_encounters": result["n_encounters"],
        "n_raters": result["n_raters"],
        "overall_icc2_1": round(svc["icc2_1"]["point"], 3),
        "overall_icc2_1_ci": [round(svc["icc2_1"]["ci_lower"], 3), round(svc["icc2_1"]["ci_upper"], 3)],
        "overall_icc2_k": round(svc["icc2_k"]["point"], 3),
        "inter_faculty_icc2_1": round(ceiling["icc2_1"]["point"], 3),  # type: ignore[index]
        "decision_kappa": round(dc["cohen_kappa"], 3),  # type: ignore[index]
        "missing_fraction": result["missing_data"]["missing_fraction"],  # type: ignore[index]
    }
