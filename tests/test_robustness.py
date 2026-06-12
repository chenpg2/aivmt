"""Robustness module tests (deterministic, mock-LLM only).

Cover: paraphrase wrapping is transparent + semantics-preserving, paraphrase-sensitivity spread is
computed, test-retest detects determinism (degenerate -> explicit nan) AND genuine stochasticity,
the report writer round-trips, and the negative controls fire.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from aivmt.llm.mock import MockLLMClient
from aivmt.robustness import (
    PARAPHRASE_TEMPLATES,
    ParaphrasingClient,
    RobustnessReport,
    build_golded_dataset,
    paraphrase_sensitivity,
    score_overall,
    retest_reliability,
    transcripts_only,
    write_robustness_artifacts,
)
from aivmt.robustness.report import render_markdown
from aivmt.schemas import Case, ChecklistItem

# ---------------------------------------------------------------------------------------------
# A controllable mock: returns checklist coverage proportional to a per-transcript "quality" knob
# encoded in the opening student turn, with optional seeded jitter so test-retest can be exercised.
# ---------------------------------------------------------------------------------------------
_ITEMS = (
    ChecklistItem("q_onset", "asks onset", 1.0),
    ChecklistItem("q_radiation", "asks radiation", 1.0),
    ChecklistItem("q_associated", "asks associated symptoms", 1.0),
    ChecklistItem("q_risk", "asks risk factors", 1.0),
)
_CASE = Case(
    case_id="c1", title="Chest pain", language="en", persona="...", history_checklist=_ITEMS
)


class QualityMock(MockLLMClient):
    """Deterministic-by-default mock whose coverage tracks a per-transcript quality, with optional
    seeded jitter (jitter>0 -> stochastic repeats for test-retest)."""

    def __init__(self, *, seed: int = 0, jitter: float = 0.0) -> None:
        super().__init__(model_id="quality-mock")
        self._rng = np.random.default_rng(seed)
        self._jitter = jitter

    def complete_json(self, system: str, user: str, *, task: str) -> dict:
        self.n_calls += 1
        # Extract the encounter quality from the rendered transcript embedded in `user`.
        q = self._quality_from_user(user)
        if self._jitter:
            q = float(np.clip(q + self._rng.normal(0.0, self._jitter), 0.0, 1.0))
        if task == "checklist":
            n_cover = int(round(q * len(_ITEMS)))
            covered = [it.item_id for it in _ITEMS[:n_cover]]
            return {"covered": covered, "evidence": {c: "quote" for c in covered}}
        if task == "segue":
            from aivmt.scoring.segue import SEGUE_DOMAINS

            return {"domains": {d: round(q, 3) for d in SEGUE_DOMAINS}}
        if task == "reasoning":
            return {"score": round(q, 3), "rationale": "synthetic"}
        return {}

    @staticmethod
    def _quality_from_user(user: str) -> float:
        # The opening turn carries "(case N)"; map N deterministically to a quality in [0.05, 0.95].
        import re

        m = re.search(r"\(case (\d+)\)", user)
        idx = int(m.group(1)) if m else 0
        return 0.05 + 0.9 * ((idx * 37 % 11) / 10.0)


def _dataset(n: int = 8):
    return build_golded_dataset(_CASE, n)


# --- paraphrase wrapping ---------------------------------------------------------------------
def test_paraphrasing_client_transforms_system_only() -> None:
    captured: dict = {}

    class CaptureMock(MockLLMClient):
        def complete_json(self, system: str, user: str, *, task: str) -> dict:
            captured["system"] = system
            captured["user"] = user
            return super().complete_json(system, user, task=task)

    inner = CaptureMock()
    transform = PARAPHRASE_TEMPLATES[1].transform  # a non-identity rewrap
    client = ParaphrasingClient(inner, transform)
    client.complete_json("BASE SYS", "USER", task="reasoning")
    assert captured["system"] == transform("BASE SYS")
    assert captured["system"] != "BASE SYS"
    assert captured["user"] == "USER"  # user prompt untouched


def test_paraphrasing_client_delegates_counters() -> None:
    inner = MockLLMClient()
    client = ParaphrasingClient(inner, PARAPHRASE_TEMPLATES[0].transform)
    client.complete_json("s", "u", task="reasoning")
    assert client.n_calls == inner.n_calls == 1


def test_identity_paraphrase_is_noop() -> None:
    assert PARAPHRASE_TEMPLATES[0].name == "p0_identity"
    assert PARAPHRASE_TEMPLATES[0].transform("anything") == "anything"


def test_at_least_five_non_identity_paraphrases() -> None:
    non_identity = [t for t in PARAPHRASE_TEMPLATES if t.name != "p0_identity"]
    assert len(non_identity) >= 5


# --- paraphrase sensitivity ------------------------------------------------------------------
def test_paraphrase_sensitivity_reports_full_spread() -> None:
    ds = _dataset(8)
    res = paraphrase_sensitivity(_CASE, ds, QualityMock(), variant="zero_shot")
    assert res.n_paraphrases == len(PARAPHRASE_TEMPLATES)
    assert res.n_transcripts == 8
    assert set(res.per_paraphrase_icc) == {t.name for t in PARAPHRASE_TEMPLATES}
    assert res.icc_min <= res.icc_mean <= res.icc_max
    assert res.icc_range == pytest.approx(res.icc_max - res.icc_min)
    # The mock ignores wording, so every paraphrase yields the SAME ICC -> zero spread.
    assert res.icc_sd == pytest.approx(0.0, abs=1e-9)


def test_paraphrase_sensitivity_is_deterministic() -> None:
    ds = _dataset(8)
    a = paraphrase_sensitivity(_CASE, ds, QualityMock(), variant="zero_shot")
    b = paraphrase_sensitivity(_CASE, ds, QualityMock(), variant="zero_shot")
    assert a.per_paraphrase_icc == b.per_paraphrase_icc


def test_paraphrase_sensitivity_requires_two_transcripts() -> None:
    with pytest.raises(ValueError, match=">=2 transcripts"):
        paraphrase_sensitivity(_CASE, _dataset(8)[:1], QualityMock())


# --- test-retest -----------------------------------------------------------------------------
def test_test_retest_deterministic_is_perfectly_reliable() -> None:
    """At temp 0 a deterministic mock gives identical repeats but varying encounters -> ICC ~1.0
    (a deterministic scorer IS perfectly reliable; this is a real number, not a degenerate nan)."""
    transcripts = transcripts_only(_dataset(8))

    def factory(seed, temperature):
        return QualityMock(seed=seed, jitter=0.0)  # deterministic regardless of seed

    res = retest_reliability(_CASE, transcripts, factory, temperature=0.0, seeds=[42, 43, 44])
    assert res.degenerate is False
    assert res.retest_icc == pytest.approx(1.0, abs=1e-6)
    assert res.n_repeats == 3
    assert res.mean_cv == pytest.approx(0.0, abs=1e-9)


def test_test_retest_all_identical_scores_is_degenerate_nan() -> None:
    """If every encounter scores identically there is no between-encounter variance -> explicit nan."""

    class ConstantMock(MockLLMClient):
        """Returns the SAME score for every transcript -> zero between-encounter variance."""

        def __init__(self) -> None:
            super().__init__(model_id="const-mock")

        def complete_json(self, system: str, user: str, *, task: str) -> dict:
            self.n_calls += 1
            if task == "checklist":
                return {"covered": ["q_onset"], "evidence": {"q_onset": "q"}}
            if task == "segue":
                from aivmt.scoring.segue import SEGUE_DOMAINS

                return {"domains": {d: 0.5 for d in SEGUE_DOMAINS}}
            if task == "reasoning":
                return {"score": 0.5, "rationale": "x"}
            return {}

    transcripts = transcripts_only(_dataset(8))
    res = retest_reliability(
        _CASE, transcripts, lambda s, t: ConstantMock(), temperature=0.0, seeds=[1, 2]
    )
    assert res.degenerate is True
    assert math.isnan(res.retest_icc)


def test_test_retest_detects_genuine_reliability() -> None:
    """With small seeded jitter the repeats differ but still track quality -> high, finite ICC."""
    transcripts = transcripts_only(_dataset(20))

    def factory(seed, temperature):
        return QualityMock(seed=seed, jitter=0.03)

    res = retest_reliability(_CASE, transcripts, factory, temperature=0.3, seeds=[1, 2, 3])
    assert res.degenerate is False
    assert math.isfinite(res.retest_icc)
    assert res.retest_icc > 0.5  # genuine reliability survives small jitter
    assert math.isfinite(res.mean_cv)


def test_test_retest_requires_two_seeds() -> None:
    transcripts = transcripts_only(_dataset(8))
    with pytest.raises(ValueError, match=">=2 seeds"):
        retest_reliability(
            _CASE, transcripts, lambda s, t: QualityMock(), temperature=0.0, seeds=[42]
        )


# --- score_overall + variant ------------------------------------------------------------------
def test_score_overall_in_unit_interval_both_variants() -> None:
    tr = _dataset(4)[0][0]
    for variant in ("zero_shot", "few_shot"):
        v = score_overall(_CASE, tr, QualityMock(), variant=variant)  # type: ignore[arg-type]
        assert 0.0 <= v <= 1.0


# --- report writer ----------------------------------------------------------------------------
def test_write_robustness_artifacts_roundtrip(tmp_path) -> None:
    ds = _dataset(8)
    para = paraphrase_sensitivity(_CASE, ds, QualityMock(), variant="zero_shot")
    transcripts = transcripts_only(ds)
    retest = retest_reliability(
        _CASE, transcripts, lambda s, t: QualityMock(seed=s, jitter=0.0),
        temperature=0.0, seeds=[1, 2],
    )
    report = RobustnessReport(
        model_id="quality-mock", variant="zero_shot", seed=42,
        paraphrase=para, test_retest=(retest,),
    )
    json_path, md_path = write_robustness_artifacts([report], tmp_path)
    assert json_path.exists() and md_path.exists()

    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded[0]["model_id"] == "quality-mock"
    assert loaded[0]["paraphrase"]["n_paraphrases"] == len(PARAPHRASE_TEMPLATES)
    # Deterministic temp-0 mock is perfectly reliable -> a real ICC, not nan.
    assert loaded[0]["test_retest"][0]["retest_icc"] == pytest.approx(1.0, abs=1e-6)

    # The written artifact passes the harness contract.
    from harness.contracts.robustness import check_robustness_inputs

    check_robustness_inputs(json_path)


def test_markdown_surfaces_nan_explicitly(tmp_path) -> None:
    """A degenerate (nan) retest_icc must render as the literal token 'nan', never blank."""
    from aivmt.robustness.types import ParaphraseSensitivity, TestRetest

    para = ParaphraseSensitivity(
        variant="zero_shot", n_paraphrases=len(PARAPHRASE_TEMPLATES), n_transcripts=4,
        per_paraphrase_icc={t.name: float("nan") for t in PARAPHRASE_TEMPLATES},
        icc_mean=float("nan"), icc_sd=float("nan"), icc_min=float("nan"),
        icc_max=float("nan"), icc_range=float("nan"),
    )
    retest = TestRetest(
        variant="zero_shot", temperature=0.0, n_repeats=2, n_seeds=2, n_transcripts=4,
        retest_icc=float("nan"), mean_cv=float("nan"), degenerate=True,
    )
    md = render_markdown([RobustnessReport("m", "zero_shot", 42, para, (retest,))])
    assert "nan" in md


def test_render_markdown_has_both_sections() -> None:
    ds = _dataset(8)
    para = paraphrase_sensitivity(_CASE, ds, QualityMock())
    report = RobustnessReport("m", "zero_shot", 42, para, ())
    md = render_markdown([report])
    assert "Paraphrase sensitivity" in md
    assert "Test-retest reliability" in md
