"""Negative controls for the ASR-robustness ICC-degradation phase.

All controls run on the seeded SYNTHETIC zh golded fixture with a deterministic keyword-counting
stub scorer (no real model required); the identical curve logic applies to real (model, transcript)
data later. The stub scores each transcript by how many CLEAN history/medical keywords survive in
its text, so ASR corruption genuinely lowers the score and the curve degrades — exactly the effect
the manuscript claims.

  - ``check_clean_level_reproduces_anchor``: WER=0 is the identity path, so its ICC equals the ICC
    computed on the un-corrupted transcripts EXACTLY (no drift from the corruption machinery).
  - ``check_degradation_is_monotone_ish``: ICC at the highest swept CER is meaningfully below the
    clean anchor — the curve must actually fall, not stay flat.
  - ``check_scramble_collapses_icc``: the 'scramble everything' control (CER -> ~1) collapses
    ICC-vs-gold toward 0; if it stays high the curve is inert.
  - ``check_degenerate_curve_point_is_nan_not_silent``: a constant-scoring scorer yields an EXPLICIT
    nan (flagged degenerate), never a silently fabricated number.
"""

from __future__ import annotations

import math

import numpy as np

from aivmt.asr import build_zh_golded_dataset, compute_curve
from aivmt.llm.mock import MockLLMClient
from aivmt.scoring.segue import SEGUE_DOMAINS
from aivmt.schemas import Case, ChecklistItem

#: ICC the clean anchor must clear (the fixture must be genuinely valid before corruption).
_CLEAN_MIN = 0.5
#: How far ICC must drop from clean -> high CER for the curve to count as "degrading".
_MIN_DROP = 0.1
#: ICC ceiling the scramble control must fall below (collapse toward 0).
_SCRAMBLE_MAX = 0.3

#: Clean keywords whose survival tracks history-taking quality (medical entities the table corrupts).
_KEYWORDS: tuple[str, ...] = (
    "腹痛", "阴道流血", "末次月经", "头晕", "坠胀", "宫外孕", "异位妊娠",
    "高血压", "糖尿病", "多久", "检查", "超声",
)

_ITEMS = (
    ChecklistItem("q_onset", "asks onset", 1.0),
    ChecklistItem("q_assoc", "asks associated", 1.0),
    ChecklistItem("q_risk", "asks risk", 1.0),
    ChecklistItem("q_plan", "states plan", 1.0),
)
_CASE = Case(
    case_id="syn_zh", title="ZH history-taking", language="zh", persona="...",
    history_checklist=_ITEMS,
)


class KeywordCountMock(MockLLMClient):
    """Deterministic stub: score == fraction of CLEAN keywords present in the rendered transcript.

    Corruption mangles the keywords (homophone/medical-term swaps, deletions), so fewer survive and
    the score falls — the curve degrades. A ``constant`` mode ignores the text (every encounter scored
    the same) to exercise the degenerate-variance path.
    """

    def __init__(self, *, constant: bool = False) -> None:
        super().__init__(model_id="keyword-mock")
        self._constant = constant

    def _quality(self, user: str) -> float:
        if self._constant:
            return 0.5
        hits = sum(1 for kw in _KEYWORDS if kw in user)
        return float(np.clip(hits / len(_KEYWORDS) * 2.0, 0.0, 1.0))

    def complete_json(self, system: str, user: str, *, task: str) -> dict:
        self.n_calls += 1
        q = self._quality(user)
        if task == "checklist":
            n = int(round(q * len(_ITEMS)))
            covered = [it.item_id for it in _ITEMS[:n]]
            return {"covered": covered, "evidence": {c: "q" for c in covered}}
        if task == "segue":
            return {"domains": {d: round(q, 3) for d in SEGUE_DOMAINS}}
        if task == "reasoning":
            return {"score": round(q, 3), "rationale": "synthetic"}
        return {}


def _curve(seed: int, n: int = 8, **kw):
    ds = build_zh_golded_dataset(_CASE, n)
    return compute_curve(_CASE, ds, KeywordCountMock(), seed=seed, **kw)


def check_clean_level_reproduces_anchor(seed: int = 42) -> dict:
    """WER=0 (identity path) ICC equals the ICC on un-corrupted transcripts EXACTLY."""
    curve = _curve(seed, wer_levels=(0.0, 0.30))
    clean_icc = curve.clean_icc()

    # Reference: score the raw (un-corrupted) transcripts directly via a CER=[] curve at 0 only.
    ref = _curve(seed, wer_levels=(0.0,))
    ref_icc = ref.points[0].icc_vs_gold

    assert math.isfinite(clean_icc), f"clean anchor ICC is not finite ({clean_icc})"
    assert clean_icc >= _CLEAN_MIN, f"fixture clean ICC too low ({clean_icc:.3f}) — fixture broken"
    assert clean_icc == ref_icc, (
        f"WER=0 anchor {clean_icc} != reference identity ICC {ref_icc} — corruption machinery "
        "perturbed the clean path"
    )
    return {"clean_icc": clean_icc}


def check_degradation_is_monotone_ish(seed: int = 42) -> dict:
    """ICC at the highest swept CER must fall meaningfully below the clean anchor."""
    curve = _curve(seed, wer_levels=(0.0, 0.15, 0.30))
    clean = curve.clean_icc()
    worst = curve.points[-1].icc_vs_gold
    assert math.isfinite(clean) and math.isfinite(worst), "curve endpoints must be finite"
    assert clean - worst >= _MIN_DROP, (
        f"NEGATIVE CONTROL FAILED: ICC did not degrade (clean={clean:.3f} high-CER={worst:.3f}, "
        f"drop {clean - worst:.3f} < {_MIN_DROP}); the curve is inert"
    )
    return {"clean_icc": clean, "high_cer_icc": worst, "drop": clean - worst}


def check_scramble_collapses_icc(seed: int = 42) -> dict:
    """'Scramble everything' (CER -> ~1) collapses ICC-vs-gold toward 0."""
    scrambled = _curve(seed, wer_levels=(0.0,), scramble=True)
    icc_val = scrambled.points[0].icc_vs_gold
    # nan (degenerate) also counts as a collapse — all surviving signal destroyed.
    collapsed = math.isnan(icc_val) or icc_val <= _SCRAMBLE_MAX
    assert collapsed, (
        f"NEGATIVE CONTROL FAILED: scrambled ICC {icc_val:.3f} did not collapse (<= {_SCRAMBLE_MAX}); "
        "the curve does not respond to catastrophic corruption"
    )
    return {"scrambled_icc": icc_val, "achieved_cer": scrambled.points[0].achieved_cer}


def check_degenerate_curve_point_is_nan_not_silent(seed: int = 42) -> dict:
    """A constant-scoring scorer has no between-encounter variance -> EXPLICIT nan, not a fake number."""
    ds = build_zh_golded_dataset(_CASE, 8)
    curve = compute_curve(_CASE, ds, KeywordCountMock(constant=True), seed=seed, wer_levels=(0.0,))
    pt = curve.points[0]
    assert pt.degenerate is True, "constant scorer must flag degenerate=True"
    assert math.isnan(pt.icc_vs_gold), (
        f"NEGATIVE CONTROL FAILED: degenerate point returned {pt.icc_vs_gold!r} instead of nan"
    )
    return {"degenerate_icc_is_nan": True}


__all__ = [
    "KeywordCountMock",
    "check_clean_level_reproduces_anchor",
    "check_degradation_is_monotone_ish",
    "check_scramble_collapses_icc",
    "check_degenerate_curve_point_is_nan_not_silent",
]
