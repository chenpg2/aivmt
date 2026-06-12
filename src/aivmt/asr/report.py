"""Serialize ASR ICC-degradation curves to JSON + a human-readable markdown summary."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Sequence

from .curve import AsrDegradationCurve


def _fmt(x: float) -> str:
    """Render a float, surfacing NaN explicitly (never blank or a fabricated number)."""
    return "nan" if isinstance(x, float) and math.isnan(x) else f"{x:.3f}"


def render_markdown(curves: Sequence[AsrDegradationCurve]) -> str:
    """Render an ICC-degradation markdown table (one row per (model, variant, level))."""
    lines = [
        "# ASR-robustness ICC-degradation curve (auto-generated — do not edit by hand)",
        "",
        "Metric: Character Error Rate (CER) — the standard zh ASR severity metric. `target_wer` is "
        "the requested level; `achieved_cer` is what the deterministic corruption actually reached.",
        "",
        "| model | variant | target_wer | achieved_cer | icc_vs_gold | n_tx | degenerate |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in curves:
        for p in c.points:
            lines.append(
                f"| {c.model_id} | {c.variant} | {p.target_wer:.2f} | {_fmt(p.achieved_cer)} | "
                f"{_fmt(p.icc_vs_gold)} | {p.n_transcripts} | {p.degenerate} |"
            )
    return "\n".join(lines) + "\n"


def write_curve_artifacts(
    curves: Sequence[AsrDegradationCurve], out_dir: Path
) -> tuple[Path, Path]:
    """Write ``asr_robustness.json`` (full) + ``asr_robustness.md`` (summary). Returns both paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "asr_robustness.json"
    md_path = out_dir / "asr_robustness.md"
    payload = [c.to_dict() for c in curves]
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(curves), encoding="utf-8")
    return json_path, md_path


__all__ = ["render_markdown", "write_curve_artifacts"]
