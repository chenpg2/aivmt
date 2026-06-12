"""Serialize a validity-suite result to artifacts: per-analysis JSON + one markdown summary table.

Kept separate from the analysis so the suite stays pure (testable without touching the filesystem).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Union

from .validity import ALL_DIMENSIONS, ORDINAL_DIMENSIONS

PathLike = Union[str, Path]

__all__ = ["write_validity_artifacts", "render_markdown_summary"]

#: Analysis blocks written as standalone JSON files (key -> filename stem).
_JSON_BLOCKS: dict[str, str] = {
    "system_vs_consensus_icc": "system_vs_consensus_icc",
    "pairwise_system_vs_rater_icc": "pairwise_system_vs_rater_icc",
    "inter_faculty_ceiling_icc": "inter_faculty_ceiling_icc",
    "quadratic_weighted_kappa": "quadratic_weighted_kappa",
    "bland_altman_overall": "bland_altman_overall",
    "g_theory_overall": "g_theory_overall",
    "decision_consistency_overall": "decision_consistency_overall",
    "bootstrap_overall_icc2_1": "bootstrap_overall_icc2_1",
    "missing_data": "missing_data",
}


def _fmt(x: float) -> str:
    return f"{x:.3f}" if isinstance(x, (int, float)) and x == x else "nan"


def render_markdown_summary(result: Mapping[str, Any]) -> str:
    """Render the human-readable markdown summary table for the SQ1 validity suite."""
    svc = result["system_vs_consensus_icc"]  # type: ignore[index]
    lines: list[str] = [
        "# SQ1 validity suite — summary",
        "",
        f"- encounters (complete-case): **{result['n_encounters']}**; "
        f"faculty raters: **{result['n_raters']}**; seed: {result['seed']}",
        f"- missing rater cells: {result['missing_data']['missing_fraction']:.1%} "  # type: ignore[index]
        f"({result['missing_data']['missing_cells']} cells); "  # type: ignore[index]
        f"dropped listwise: {result['missing_data']['dropped_listwise']}",  # type: ignore[index]
        "",
        "## System vs faculty-consensus ICC (absolute agreement, 95% CI)",
        "",
        "| dimension | ICC(2,1) | 95% CI | ICC(2,k) | 95% CI |",
        "|---|---|---|---|---|",
    ]
    for dim in ALL_DIMENSIONS:
        s1 = svc[dim]["icc2_1"]  # type: ignore[index]
        sk = svc[dim]["icc2_k"]  # type: ignore[index]
        lines.append(
            f"| {dim} | {_fmt(s1['point'])} | [{_fmt(s1['ci_lower'])}, {_fmt(s1['ci_upper'])}] | "
            f"{_fmt(sk['point'])} | [{_fmt(sk['ci_lower'])}, {_fmt(sk['ci_upper'])}] |"
        )

    ceiling = result["inter_faculty_ceiling_icc"]  # type: ignore[index]
    c1 = ceiling["icc2_1"]  # type: ignore[index]
    ck = ceiling["icc2_k"]  # type: ignore[index]
    lines += [
        "",
        "## Inter-faculty ceiling ICC (overall)",
        "",
        f"- ICC(2,1) = {_fmt(c1['point'])} [{_fmt(c1['ci_lower'])}, {_fmt(c1['ci_upper'])}]",
        f"- ICC(2,k) = {_fmt(ck['point'])} [{_fmt(ck['ci_lower'])}, {_fmt(ck['ci_upper'])}]",
        "",
        "## Pairwise system-vs-each-rater ICC(2,1) (overall)",
        "",
        "| rater | ICC(2,1) | 95% CI |",
        "|---|---|---|",
    ]
    for rid, est in result["pairwise_system_vs_rater_icc"].items():  # type: ignore[index]
        lines.append(f"| {rid} | {_fmt(est['point'])} | [{_fmt(est['ci_lower'])}, {_fmt(est['ci_upper'])}] |")

    qwk = result["quadratic_weighted_kappa"]  # type: ignore[index]
    lines += [
        "",
        "## Quadratic weighted kappa (ordinal-anchored dimensions, system vs consensus)",
        "",
        "| dimension | QWK |",
        "|---|---|",
    ]
    for dim in ORDINAL_DIMENSIONS:
        lines.append(f"| {dim} | {_fmt(qwk[dim])} |")  # type: ignore[index]

    ba = result["bland_altman_overall"]  # type: ignore[index]
    lines += [
        "",
        "## Bland-Altman (overall: system vs consensus)",
        "",
        f"- bias = {_fmt(ba['bias'])}; SD(diff) = {_fmt(ba['sd_diff'])}",
        f"- 95% limits of agreement = [{_fmt(ba['loa_lower'])}, {_fmt(ba['loa_upper'])}]",
        f"- proportional-bias slope = {_fmt(ba['prop_bias_slope'])} (p = {_fmt(ba['prop_bias_p'])})",
    ]

    gt = result["g_theory_overall"]  # type: ignore[index]
    comp = gt["components"]  # type: ignore[index]
    lines += [
        "",
        "## G-theory (faculty overall, persons x raters) + D-study",
        "",
        f"- variance components: person = {_fmt(comp['var_person'])}, "
        f"rater = {_fmt(comp['var_rater'])}, residual = {_fmt(comp['var_residual'])}",
        f"- observed design (k={gt['n_raters']}): G = {_fmt(gt['g_coefficient'])}, "  # type: ignore[index]
        f"Phi = {_fmt(gt['phi'])}",
        "",
        "| n raters | G (relative) | Phi (absolute) |",
        "|---|---|---|",
    ]
    for pt in gt["d_study"]:  # type: ignore[index]
        lines.append(f"| {pt['n_raters']} | {_fmt(pt['g_coefficient'])} | {_fmt(pt['phi'])} |")

    dc = result["decision_consistency_overall"]  # type: ignore[index]
    lines += [
        "",
        "## Decision consistency (pass/fail at the cut-score)",
        "",
        f"- cut-score = {dc['cut_score']}; raw agreement = {_fmt(dc['raw_agreement'])}; "  # type: ignore[index]
        f"Cohen's kappa = {_fmt(dc['cohen_kappa'])}",  # type: ignore[index]
        f"- both pass = {dc['n_both_pass']}; both fail = {dc['n_both_fail']}; "  # type: ignore[index]
        f"disagree = {dc['n_disagree']}",  # type: ignore[index]
        "",
    ]
    return "\n".join(lines)


def write_validity_artifacts(result: Mapping[str, object], out_dir: PathLike) -> list[Path]:
    """Write per-analysis JSON files + ``summary.md`` to ``out_dir``; return the written paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    full = out / "validity_suite.json"
    full.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    written.append(full)

    for key, stem in _JSON_BLOCKS.items():
        if key in result:
            path = out / f"{stem}.json"
            path.write_text(json.dumps(result[key], indent=2, ensure_ascii=False), encoding="utf-8")
            written.append(path)

    summary = out / "summary.md"
    summary.write_text(render_markdown_summary(result), encoding="utf-8")
    written.append(summary)
    return written
