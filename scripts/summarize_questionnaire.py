"""Summarize the student post-session questionnaire (secondary endpoints), QC-gated.

Reads ``data/student_questionnaire_real.csv`` (one row per student) and computes the
usability/educational secondary endpoints: SUS (0-100), perceived learning value,
Q16/Q17 option proportions, Q18 willingness distribution, and demographics.

A QC gate runs FIRST and ABORTS (writing nothing) if the data fails integrity checks,
so a data-entry error can never be silently summarized as a real result.

QC hard checks (abort): exact columns; >= 1 row; SUS/PLV/Q18 are integers in 1-5;
unique stu_code; Q16/Q17 codes in 1-7; and an identical-column check (two DIFFERENT
score columns must not have byte-identical responses across all students, which is the
signature of a templating / copy-paste entry error). Soft checks (warn, non-blocking):
uniform grade or date, demographic missingness.

Q18 coding: by default 非常愿意=5 (the template codebook). If the data was entered left-to-right
(非常愿意=1), pass ``--q18-coding position`` and the script reverses it (6 - x) to the codebook
direction before summarizing, recording the choice in the artifact. The raw CSV is never modified.

Usage:
  uv run python scripts/summarize_questionnaire.py
  uv run python scripts/summarize_questionnaire.py --in data/student_questionnaire_real.csv --q18-coding position
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
from pathlib import Path

logger = logging.getLogger("aivmt.questionnaire")
ROOT = Path(__file__).resolve().parents[1]

SUS_ITEMS = [f"sus_q{i}" for i in range(1, 11)]
SUS_POSITIVE = {f"sus_q{i}" for i in (1, 3, 5, 7, 9)}  # odd items are positively worded
PLV_ITEMS = [f"plv_q{i}" for i in range(11, 16)]
LIKERT_1_5 = SUS_ITEMS + PLV_ITEMS + ["q18_continue"]
EXPECTED_COLS = [
    "stu_code", "group", "date", "grade", "sex", "prior_sp", "prior_sp_count", "prior_ai_use",
    *SUS_ITEMS, *PLV_ITEMS,
    "q16_valuable_codes", "q16_other", "q17_improve_codes", "q17_other", "q18_continue", "q19_open",
]
Q16_OPTIONS = {1: "可反复练习", 2: "即时反馈", 3: "不怕面对真人尴尬", 4: "随时可用",
               5: "评分客观一致", 6: "帮助梳理思路", 7: "其他"}
Q17_OPTIONS = {1: "语音识别准确度", 2: "AI病人真实感", 3: "反馈细致度", 4: "设备操作",
               5: "病例难度/覆盖面", 6: "交流流畅度/等待", 7: "其他"}


def _to_int(value: str):
    value = (value or "").strip()
    if value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _req_int(value: str) -> int:
    """Like ``_to_int`` but asserts a value is present (use only after QC has passed)."""
    iv = _to_int(value)
    assert iv is not None, "expected a validated 1-5 integer (QC should have caught this)"
    return iv


def _parse_codes(cell: str) -> list[int]:
    cell = (cell or "").strip()
    if not cell:
        return []
    out: list[int] = []
    for tok in cell.replace(";", ",").split(","):
        tok = tok.strip()
        if tok:
            try:
                out.append(int(tok))
            except ValueError:
                pass
    return out


def qc_hard_failures(rows: list[dict], cols: list[str]) -> list[str]:
    """Return a list of hard QC failures; empty means the data may be summarized."""
    fails: list[str] = []
    missing = [c for c in EXPECTED_COLS if c not in cols]
    if missing:
        return [f"missing columns: {missing}"]
    if not rows:
        return ["no data rows"]

    for q in LIKERT_1_5:
        bad = []
        for r in rows:
            iv = _to_int(r[q])
            if iv is None or not 1 <= iv <= 5:
                bad.append(r["stu_code"])
        if bad:
            fails.append(f"{q}: {len(bad)} value(s) blank or outside 1-5 (e.g. {bad[:5]})")

    codes = [r["stu_code"].strip() for r in rows]
    dupes = sorted({c for c in codes if codes.count(c) > 1})
    if dupes:
        fails.append(f"duplicate stu_code: {dupes}")

    for col in ("q16_valuable_codes", "q17_improve_codes"):
        out_of_range = {tok for r in rows for tok in _parse_codes(r[col]) if not 1 <= tok <= 7}
        if out_of_range:
            fails.append(f"{col}: option code(s) outside 1-7: {sorted(out_of_range)}")

    # identical-column artifact: two different score items with the same response vector
    score_cols = SUS_ITEMS + PLV_ITEMS
    vecs = {c: tuple(r[c].strip() for r in rows) for c in score_cols}
    ident = []
    for i, a in enumerate(score_cols):
        for b in score_cols[i + 1:]:
            if vecs[a] == vecs[b] and len(set(vecs[a])) > 1:
                ident.append(f"{a}=={b}")
    if ident:
        fails.append(f"different items share an identical response vector (entry/template error?): {ident[:8]}")

    return fails


def qc_warnings(rows: list[dict]) -> list[str]:
    warns: list[str] = []
    for col in ("grade", "date"):
        vals = {r[col].strip() for r in rows if r[col].strip()}
        if len(vals) == 1:
            warns.append(f"all rows share one {col} ({next(iter(vals))}) — confirm this is expected")
    for col in ("grade", "sex", "prior_sp", "prior_ai_use"):
        blank = sum(1 for r in rows if not r[col].strip())
        if blank:
            warns.append(f"{col}: {blank} blank cell(s)")
    return warns


def _mean_sd_ci(xs: list[float]) -> dict:
    n = len(xs)
    mean = sum(xs) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / (n - 1)) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n else 0.0
    half = 1.96 * se  # normal approximation; at n~50 the t correction is negligible
    return {"mean": round(mean, 2), "sd": round(sd, 2), "n": n,
            "ci95": [round(mean - half, 2), round(mean + half, 2)]}


def _sus_score(row: dict) -> float:
    total = 0
    for q in SUS_ITEMS:
        v = _req_int(row[q])
        total += (v - 1) if q in SUS_POSITIVE else (5 - v)
    return total * 2.5  # standard SUS, 0-100


def summarize(rows: list[dict], q18_coding: str = "codebook") -> dict:
    n = len(rows)
    sus = [_sus_score(r) for r in rows]
    plv = [sum(_req_int(r[q]) for q in PLV_ITEMS) / len(PLV_ITEMS) for r in rows]

    def proportions(col: str, options: dict) -> dict:
        counts = {k: 0 for k in options}
        for r in rows:
            for c in set(_parse_codes(r[col])):
                if c in counts:
                    counts[c] += 1
        return {f"{k} {options[k]}": round(counts[k] / n, 3) for k in options}

    # q18: reverse to the codebook direction (非常愿意=5) if entered position-order (非常愿意=1)
    q18 = []
    for r in rows:
        raw = _req_int(r["q18_continue"])
        q18.append(6 - raw if q18_coding == "position" else raw)
    dist = {str(k): q18.count(k) for k in range(1, 6)}

    def freq(col: str) -> dict:
        return {k: sum(1 for r in rows if r[col].strip() == k)
                for k in sorted({r[col].strip() for r in rows})}

    mean_sus = sum(sus) / n
    mean_plv = sum(plv) / n
    return {
        "n_students": n,
        "sus": {**_mean_sd_ci(sus), "threshold": 68, "meets_threshold": mean_sus >= 68},
        "perceived_learning_value": {**_mean_sd_ci(plv), "midpoint": 3, "above_midpoint": mean_plv > 3},
        "q16_valuable_proportions": proportions("q16_valuable_codes", Q16_OPTIONS),
        "q17_improve_proportions": proportions("q17_improve_codes", Q17_OPTIONS),
        "q18_continue": {"coding": q18_coding, "distribution_1to5": dist, "mean": round(sum(q18) / n, 2),
                         "willing_4plus_rate": round(sum(1 for v in q18 if v >= 4) / n, 3)},
        "demographics": {"grade": freq("grade"), "sex": freq("sex"),
                         "prior_sp": freq("prior_sp"), "prior_ai_use": freq("prior_ai_use")},
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Summarize the student questionnaire (QC-gated).")
    ap.add_argument("--in", dest="inp", default=str(ROOT / "data" / "student_questionnaire_real.csv"))
    ap.add_argument("--out", default=str(ROOT / "results" / "phase_questionnaire" / "questionnaire_summary.json"))
    ap.add_argument("--q18-coding", choices=("codebook", "position"), default="codebook",
                    help="how q18_continue was entered: 'codebook' = 非常愿意 as 5 (default); "
                         "'position' = 非常愿意 as 1 (left-to-right), reversed to 6-x before summary")
    args = ap.parse_args()

    path = Path(args.inp)
    if not path.exists():
        logger.error("input not found: %s", path)
        return 1
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        cols = list(reader.fieldnames or [])
        rows = [r for r in reader if (r.get("stu_code") or "").strip()]

    for w in qc_warnings(rows):
        logger.warning("QC warning: %s", w)

    fails = qc_hard_failures(rows, cols)
    if fails:
        logger.error("QC FAILED — refusing to summarize (no result written):")
        for f in fails:
            logger.error("  - %s", f)
        logger.error("Re-enter from the paper forms using the validated xlsx template, then re-run.")
        return 2

    result = summarize(rows, q18_coding=args.q18_coding)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("QC passed. Questionnaire summary (n=%d):", result["n_students"])
    logger.info("  SUS = %s", result["sus"])
    logger.info("  perceived_learning = %s", result["perceived_learning_value"])
    logger.info("  Q18 willing(>=4) = %s", result["q18_continue"]["willing_4plus_rate"])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
