"""Serialize :class:`RobustnessReport` objects to JSON + a human-readable markdown summary."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Sequence

from .types import RobustnessReport


def _fmt(x: float) -> str:
    """Render a float for markdown, surfacing NaN explicitly (never as a blank or a fake number)."""
    return "nan" if isinstance(x, float) and math.isnan(x) else f"{x:.3f}"


def render_markdown(reports: Sequence[RobustnessReport]) -> str:
    """Render a markdown robustness summary (one paraphrase row + one row per retest cell each)."""
    lines = [
        "# Scorer robustness (auto-generated — do not edit by hand)",
        "",
        "## Paraphrase sensitivity (ICC-vs-gold across system-prompt rewordings)",
        "",
        "| model | variant | n_para | n_tx | icc_mean | icc_sd | icc_range |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in reports:
        p = r.paraphrase
        lines.append(
            f"| {r.model_id} | {r.variant} | {p.n_paraphrases} | {p.n_transcripts} | "
            f"{_fmt(p.icc_mean)} | {_fmt(p.icc_sd)} | {_fmt(p.icc_range)} |"
        )
    lines += [
        "",
        "## Test-retest reliability (stochasticity across repeated scorings)",
        "",
        "| model | variant | temp | K | n_tx | retest_icc | mean_cv | degenerate |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in reports:
        for t in r.test_retest:
            lines.append(
                f"| {r.model_id} | {r.variant} | {t.temperature} | {t.n_repeats} | "
                f"{t.n_transcripts} | {_fmt(t.retest_icc)} | {_fmt(t.mean_cv)} | {t.degenerate} |"
            )
    return "\n".join(lines) + "\n"


def write_robustness_artifacts(
    reports: Sequence[RobustnessReport], out_dir: Path
) -> tuple[Path, Path]:
    """Write ``robustness.json`` (full, machine-readable) + ``robustness.md`` (summary) to ``out_dir``.

    Returns the (json_path, md_path) pair. Parent directories are created if absent.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "robustness.json"
    md_path = out_dir / "robustness.md"
    payload = [r.to_dict() for r in reports]
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(reports), encoding="utf-8")
    return json_path, md_path
