"""Serialize a :class:`LocalVsCloudComparison` to JSON + a human-readable markdown table.

The markdown surfaces, per model, the overall ICC-vs-gold and the per-SEGUE-domain ICC (so the
domain-level cloud collapse — ECOSBot's communication-subdomain failure mode — is visible at a
glance), then the local-minus-cloud deltas against the pre-registered non-inferiority margin.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from .scoring import SEGUE_DOMAINS
from .types import LocalVsCloudComparison, ProviderCell


def _fmt(x: float) -> str:
    """Render a float, surfacing NaN explicitly (never blank or a fabricated number)."""
    return "nan" if isinstance(x, float) and math.isnan(x) else f"{x:.3f}"


def _cell_row(cell: ProviderCell) -> str:
    doms = " | ".join(_fmt(cell.domain_icc(d)) for d in SEGUE_DOMAINS)
    return (
        f"| {cell.role} | {cell.provider} | {cell.model_id} | {cell.n_transcripts} | "
        f"{_fmt(cell.overall_icc2_1)} | {doms} | {cell.parse_success_rate:.3f} | "
        f"{cell.refusal_rate:.3f} |"
    )


def render_markdown(comparison: LocalVsCloudComparison) -> str:
    """Render the local-vs-cloud comparison as markdown (validity table + NI delta table)."""
    dom_cols = " | ".join(SEGUE_DOMAINS)
    dom_sep = "|".join(["---"] * len(SEGUE_DOMAINS))
    lines = [
        "# Local-vs-cloud scoring head-to-head (auto-generated — do not edit by hand)",
        "",
        f"Provenance: **{comparison.provenance}** (off-device-safe synthetic/de-identified — NO real "
        "data was transmitted to any cloud endpoint). "
        f"Seed: {comparison.seed}. n={comparison.n_transcripts}. Variant: {comparison.variant}. "
        f"Pre-registered non-inferiority margin delta = {comparison.non_inferiority_margin:.2f}.",
        "",
        "## ICC(2,1) vs designed-quality gold (overall + per SEGUE domain)",
        "",
        f"| role | provider | model | n | overall | {dom_cols} | parse | refusal |",
        f"|---|---|---|---|---|{dom_sep}|---|---|",
        _cell_row(comparison.local),
    ]
    for cell in comparison.cloud:
        lines.append(_cell_row(cell))

    lines += [
        "",
        "## Local-minus-cloud ICC delta (positive => local agrees with gold MORE than cloud)",
        "",
        "Pre-registered non-inferiority claim: the local model is non-inferior to a cloud comparator "
        f"on the overall axis iff `delta_overall >= -{comparison.non_inferiority_margin:.2f}` (the "
        "local ICC is at most the margin below the cloud ICC). Per-domain deltas are reported because "
        "cloud models are known to collapse on communication subdomains (ECOSBot).",
        "",
        f"| cloud provider | delta_overall | non-inferior? | {dom_cols} |",
        f"|---|---|---|{dom_sep}|",
    ]
    margin = comparison.non_inferiority_margin
    for d in comparison.deltas:
        if math.isnan(d.delta_overall):
            ni = "nan (degenerate)"
        else:
            ni = "YES" if d.delta_overall >= -margin else "NO"
        dom_deltas = " | ".join(_fmt(d.delta_by_domain[dom]) for dom in SEGUE_DOMAINS)
        lines.append(f"| {d.cloud_provider} | {_fmt(d.delta_overall)} | {ni} | {dom_deltas} |")

    if comparison.skipped_providers:
        lines += [
            "",
            "## Requested-but-skipped providers (PARTIAL head-to-head)",
            "",
            "These providers were explicitly requested but had no API key set, so they were NOT "
            "scored. The comparison above is therefore partial — read the deltas accordingly.",
            "",
            f"- requested: {', '.join(comparison.requested_providers) or '(none)'}",
            f"- skipped (key unset): {', '.join(comparison.skipped_providers)}",
        ]

    if not comparison.cloud:
        lines += [
            "",
            "_No cloud provider had its API key set in this run — only the local cell was scored. "
            "Export DEEPSEEK_API_KEY / DASHSCOPE_API_KEY / OPENAI_API_KEY (see .env.example) and "
            "re-run for the head-to-head._",
        ]
    return "\n".join(lines) + "\n"


def write_local_vs_cloud_artifacts(
    comparison: LocalVsCloudComparison, out_dir: Path
) -> tuple[Path, Path]:
    """Write ``local_vs_cloud.json`` (full) + ``local_vs_cloud.md`` (summary). Returns both paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "local_vs_cloud.json"
    md_path = out_dir / "local_vs_cloud.md"
    json_path.write_text(
        json.dumps(comparison.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md_path.write_text(render_markdown(comparison), encoding="utf-8")
    return json_path, md_path


__all__ = ["render_markdown", "write_local_vs_cloud_artifacts"]
