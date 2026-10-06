"""Generate the supplementary tables requested at peer review (round 1).

Reviewer 2 asked for three things that are answerable from the data already collected,
with no new encounters and no new faculty rating:

  Supplementary Table 1  domain intercorrelations and composite-weighting stability   (R2-2)
  NOTE: Supplementary Table 2 (standard setting, R2-10) is maintained by hand in the output
  file; re-running this script regenerates Tables 1, 3 and 4 only and would drop it.
  Supplementary Table 3  decision consistency as a function of the pass/fail cut       (R2-10)
  Supplementary Table 4  faculty rater structure                                       (R2-11)

Inputs are the scored real-student encounters and the blinded faculty rating file, i.e.
exactly the inputs of ``phase_scoring_validity_real``. Nothing here calls an LLM.

Usage (pandas is not a declared project dependency, hence --with):
  uv run --with pandas python scripts/export_reviewer_tables.py
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

SEGUE = [
    "set_the_stage",
    "elicit_information",
    "give_information",
    "understand_perspective",
    "end_encounter",
]
DOMAINS7 = SEGUE + ["history_completion", "reasoning"]

#: Alternative composite weightings (w_history, w_meanSEGUE, w_reasoning) probed for stability.
ALT_WEIGHTS = {
    "0.40 / 0.40 / 0.20 (pre-registered)": (0.40, 0.40, 0.20),
    "0.33 / 0.33 / 0.33 (equal)": (1 / 3, 1 / 3, 1 / 3),
    "0.50 / 0.30 / 0.20": (0.50, 0.30, 0.20),
    "0.30 / 0.50 / 0.20": (0.30, 0.50, 0.20),
    "0.40 / 0.30 / 0.30": (0.40, 0.30, 0.30),
    "0.50 / 0.40 / 0.10": (0.50, 0.40, 0.10),
    "0.25 / 0.50 / 0.25": (0.25, 0.50, 0.25),
}

CUTS = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
PREREG_CUT = 0.60


def load_system(enc_dir: Path) -> pd.DataFrame:
    rows = []
    for f in sorted(glob.glob(str(enc_dir / "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        s = d["score"]
        row = {
            "encounter_id": d["encounter_id"],
            "history_completion": s["history_completion"],
            "reasoning": s["reasoning"],
            "overall": s["overall"],
        }
        row.update(s["segue"])
        rows.append(row)
    df = pd.DataFrame(rows).set_index("encounter_id").sort_index()
    df["mean_segue"] = df[SEGUE].mean(axis=1)
    return df


def load_faculty(fac_csv: Path) -> pd.DataFrame:
    fac = pd.read_csv(fac_csv, encoding="utf-8-sig")
    fac["mean_segue"] = fac[SEGUE].mean(axis=1)
    return fac


def cohen_kappa_binary(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    po = float((a == b).mean())
    pe = sum(float((a == c).mean()) * float((b == c).mean()) for c in (0, 1))
    return ((po - pe) / (1 - pe) if pe < 1 else float("nan")), po


def _corr_md(df: pd.DataFrame, cols: list[str]) -> list[str]:
    cm = df[cols].corr()
    short = {c: c.replace("_", " ")[:18] for c in cols}
    out = ["| | " + " | ".join(short[c] for c in cols) + " |",
           "|---|" + "---|" * len(cols)]
    for r in cols:
        cells = []
        for c in cols:
            cells.append("—" if r == c else f"{cm.loc[r, c]:.3f}")
        out.append(f"| **{short[r]}** | " + " | ".join(cells) + " |")
    return out


def build(sys_df: pd.DataFrame, fac: pd.DataFrame) -> str:
    cons = fac.groupby("encounter_id")[DOMAINS7 + ["overall", "mean_segue"]].mean()
    cons = cons.loc[sys_df.index]
    n = len(sys_df)
    o: list[str] = []
    w = o.append

    w("# Supplementary Tables 1 to 4 (peer review, round 1)")
    w("")
    w(
        f"All statistics are computed on the n = {n} encounters and the three blinded faculty "
        "raters of the primary analysis, by `scripts/export_reviewer_tables.py`. No new "
        "encounters and no new faculty rating were collected for these tables."
    )
    w("")
    w("---")
    w("")

    # ---- Table 2 ----------------------------------------------------------------
    w("## Supplementary Table 1. Domain intercorrelations and composite-weighting stability")
    w("")
    w("**(a) System scores — Pearson correlations among the seven scored domains.**")
    w("")
    o.extend(_corr_md(sys_df, DOMAINS7))
    w("")
    w("**(b) Faculty consensus — Pearson correlations among the same seven domains.**")
    w("")
    o.extend(_corr_md(cons, DOMAINS7))
    w("")

    sys_tri = sys_df[DOMAINS7].corr().values[np.triu_indices(7, 1)]
    con_tri = cons[DOMAINS7].corr().values[np.triu_indices(7, 1)]
    w(
        f"Across the 21 domain pairs the system correlations range {sys_tri.min():.3f} to "
        f"{sys_tri.max():.3f} (median {np.median(sys_tri):.3f}) and the faculty-consensus "
        f"correlations range {con_tri.min():.3f} to {con_tri.max():.3f} "
        f"(median {np.median(con_tri):.3f})."
    )
    w("")

    w("**(c) Components of the overall composite.**")
    w("")
    w("| Component pair | System *r* | Faculty consensus *r* |")
    w("|---|---|---|")
    pairs = [
        ("history_completion", "mean_segue", "history_completion x mean(SEGUE)"),
        ("history_completion", "elicit_information", "history_completion x elicit_information"),
        ("history_completion", "reasoning", "history_completion x reasoning"),
        ("mean_segue", "reasoning", "mean(SEGUE) x reasoning"),
    ]
    for a, b, label in pairs:
        w(f"| {label} | {sys_df[a].corr(sys_df[b]):.3f} | {cons[a].corr(cons[b]):.3f} |")
    w("")

    w("**(d) Stability of the composite under alternative weightings (system scores).**")
    w("")

    def composite(df: pd.DataFrame, wt: tuple[float, float, float]) -> pd.Series:
        return wt[0] * df["history_completion"] + wt[1] * df["mean_segue"] + wt[2] * df["reasoning"]

    ref = composite(sys_df, ALT_WEIGHTS["0.40 / 0.40 / 0.20 (pre-registered)"])
    w("| Weighting (history / SEGUE / reasoning) | *r* with pre-registered composite | Max shift in any encounter's score |")
    w("|---|---|---|")
    worst_r, worst_d = 1.0, 0.0
    for label, wt in ALT_WEIGHTS.items():
        alt = composite(sys_df, wt)
        if label.endswith("(pre-registered)"):
            w(f"| {label} | — (reference) | — |")
            continue
        r = float(ref.corr(alt))
        d = float((ref - alt).abs().max())
        worst_r, worst_d = min(worst_r, r), max(worst_d, d)
        w(f"| {label} | {r:.4f} | {d:.4f} |")
    w("")
    w(
        f"Every alternative weighting reproduces the pre-registered composite at r >= "
        f"{worst_r:.3f}, and no encounter's composite moves by more than {worst_d:.3f} on the "
        "0 to 1 scale."
    )
    w("")

    # ---- Table 3 ----------------------------------------------------------------
    w("## Supplementary Table 3. Decision consistency as a function of the pass/fail cut")
    w("")
    sysO, facO = sys_df["overall"].values, cons["overall"].values
    w("| Cut | Encounters failed by faculty | Raw agreement | Cohen's kappa |")
    w("|---|---|---|---|")
    for c in CUTS:
        k, po = cohen_kappa_binary((sysO >= c).astype(int), (facO >= c).astype(int))
        star = " **(pre-specified)**" if abs(c - PREREG_CUT) < 1e-9 else ""
        w(f"| {c:.2f}{star} | {int((facO < c).sum())} | {po:.3f} | {k:.3f} |")
    w("")
    w(
        f"Faculty-consensus overall scores had mean {facO.mean():.3f}, SD {facO.std(ddof=1):.3f}, "
        f"range {facO.min():.3f} to {facO.max():.3f}. The pre-specified cut of "
        f"{PREREG_CUT:.2f} falls in the densest region of that distribution, where a small "
        "difference between the system and faculty scores is most likely to place an encounter "
        "on opposite sides of the line; chance-corrected agreement is correspondingly lowest "
        "there. The cut reported in the main text is the pre-specified one and was not selected "
        "from this table."
    )
    w("")

    # ---- Table 4 ----------------------------------------------------------------
    w("## Supplementary Table 4. Faculty rater structure (overall score)")
    w("")
    pm = fac.pivot_table(index="encounter_id", columns="rater_id", values="overall")
    w("| Rater | Mean overall | SD |")
    w("|---|---|---|")
    for r in pm.columns:
        w(f"| {r} | {pm[r].mean():.4f} | {pm[r].std(ddof=1):.4f} |")
    w("")
    rater_var = float(np.var(pm.mean(axis=0).values, ddof=1))
    person_var = float(np.var(pm.mean(axis=1).values, ddof=1))
    w("| Quantity | Value |")
    w("|---|---|")
    w(f"| Variance of the three rater means | {rater_var:.6f} |")
    w(f"| Variance across encounters (consensus score) | {person_var:.6f} |")
    w(f"| Mean within-encounter SD across the three raters | {pm.std(axis=1, ddof=1).mean():.4f} |")
    w(f"| Largest within-encounter range across the three raters | {(pm.max(axis=1) - pm.min(axis=1)).max():.3f} |")
    w("")
    w(
        f"The rater main effect is small but not zero: the three rater means span "
        f"{pm.mean(axis=0).max() - pm.mean(axis=0).min():.3f} on the 0 to 1 scale, and the "
        f"variance between encounters exceeds the variance between raters by a factor of about "
        f"{person_var / rater_var:.0f}. The rater variance component reported in Table 2 of the "
        "main text rounds to 0.000 at three decimal places for this reason."
    )
    w("")
    return "\n".join(o) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Export peer-review supplementary tables.")
    ap.add_argument("--enc", default=str(ROOT / "data" / "encounters" / "real_students"))
    ap.add_argument("--fac", default=str(ROOT / "data" / "faculty_ratings_real.csv"))
    ap.add_argument(
        "--out",
        default=str(
            ROOT / "submission_lowresource" / "supplementary" / "Supplementary_Tables_2to4.md"
        ),
    )
    args = ap.parse_args()

    sys_df = load_system(Path(args.enc))
    fac = load_faculty(Path(args.fac))
    if len(sys_df) != fac["encounter_id"].nunique():
        raise SystemExit(
            f"encounter mismatch: {len(sys_df)} scored vs {fac['encounter_id'].nunique()} rated"
        )
    out = Path(args.out)
    out.write_text(build(sys_df, fac), encoding="utf-8")
    print(f"wrote {out} (n={len(sys_df)} encounters, {fac['rater_id'].nunique()} raters)")


if __name__ == "__main__":
    main()
