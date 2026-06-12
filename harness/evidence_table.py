"""Regenerate the evidence table from each phase's benchmark() — the single source of paper numbers.

Deterministic (seeded): re-running produces no diff. Run: `python -m harness.evidence_table`
"""

from __future__ import annotations

from harness.registry import PHASE_REGISTRY, PROJECT_ROOT


def build_table() -> str:
    lines = [
        "# Evidence table (auto-generated from phase.benchmark() — do not edit by hand)",
        "",
        "| phase | metrics |",
        "|---|---|",
    ]
    for name, cls in PHASE_REGISTRY.items():
        metrics = cls().benchmark()
        rendered = "; ".join(f"{k}={v}" for k, v in metrics.items()) or "(none)"
        lines.append(f"| {name} | {rendered} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    table = build_table()
    out = PROJECT_ROOT / "results" / "evidence_table.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(table, encoding="utf-8")
    print(table)


if __name__ == "__main__":
    main()
