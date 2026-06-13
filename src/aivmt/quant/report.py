"""Serialize :class:`QuantCell` objects to JSON + a human-readable frontier markdown table."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Sequence

from .types import QuantCell


def _fmt(x: float) -> str:
    """Render a float, surfacing NaN explicitly (never blank or a fabricated number)."""
    return "nan" if isinstance(x, float) and math.isnan(x) else f"{x:.3f}"


def _tok(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1f}"


def _mem(cell: QuantCell) -> str:
    return cell.memory.size_display if cell.memory is not None else "n/a"


def _disk(cell: QuantCell) -> str:
    return cell.disk.size_display if cell.disk is not None else "n/a"


def render_markdown(cells: Sequence[QuantCell]) -> str:
    """Render the validity-cost frontier as a markdown table (one row per cell)."""
    lines = [
        "# Quantization frontier (auto-generated — do not edit by hand)",
        "",
        "Validity-cost surface over (model size x quant level): ICC-vs-gold against the designed "
        "synthetic gold, JSON-parse robustness, per-encounter latency, loaded RAM/VRAM, and on-disk "
        "size. `degenerate` flags a cell whose scorer produced no between-encounter variance (ICC is "
        "an explicit nan, never a silent number).",
        "",
        "| model_tag | label | n_tx | icc2_1 | icc2_k | parse | refusal | median_s | p90_s | "
        "tok/s | mem | disk | degenerate |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in cells:
        v, lat = c.validity, c.latency
        lines.append(
            f"| {c.model_tag} | {c.label} | {c.n_transcripts} | {_fmt(v.icc2_1)} | "
            f"{_fmt(v.icc2_k)} | {v.parse_success_rate:.3f} | {v.refusal_rate:.3f} | "
            f"{lat.median_s:.3f} | {lat.p90_s:.3f} | {_tok(lat.tokens_per_s)} | "
            f"{_mem(c)} | {_disk(c)} | {v.degenerate} |"
        )
    return "\n".join(lines) + "\n"


def write_quant_frontier_artifacts(
    cells: Sequence[QuantCell], out_dir: Path
) -> tuple[Path, Path]:
    """Write ``quant_frontier.json`` (full) + ``quant_frontier.md`` (summary). Returns both paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "quant_frontier.json"
    md_path = out_dir / "quant_frontier.md"
    payload = [c.to_dict() for c in cells]
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(cells), encoding="utf-8")
    return json_path, md_path


__all__ = ["render_markdown", "write_quant_frontier_artifacts"]
