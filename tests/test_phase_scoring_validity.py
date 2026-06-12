"""Full SQ1 validity-suite tests: the complete matrix, missing-data policy, fail-loud, and the
end-to-end PhaseScoringValidity.run() artifact path on synthetic fixtures."""

from __future__ import annotations

import csv
import json
import logging

import numpy as np
import pytest

from aivmt.dataio import FACULTY_SHEET_FIELDS
from aivmt.metrics import headline_metrics, run_validity_suite
from aivmt.metrics.validity import (
    ALL_DIMENSIONS,
    MISSING_DATA_HARD_THRESHOLD,
    ORDINAL_DIMENSIONS,
)
from harness.registry import PhaseScoringValidity, load_seed
from harness.sanity.scoring_validity import (
    check_validity_suite_negative_control,
    make_validity_fixture,
)

SEED = load_seed()


# --- Full suite content ------------------------------------------------------------------------
def test_full_suite_reports_every_analysis() -> None:
    system_by_id, faculty_rows = make_validity_fixture(n=30, k=3, seed=SEED)
    res = run_validity_suite(system_by_id, faculty_rows, seed=SEED)

    assert res["n_encounters"] == 30
    assert res["n_raters"] == 3

    # 1. system-vs-consensus ICC for overall AND every subscore, each with CI.
    svc = res["system_vs_consensus_icc"]
    assert set(svc) == set(ALL_DIMENSIONS)
    for dim in ALL_DIMENSIONS:
        for kind in ("icc2_1", "icc2_k"):
            est = svc[dim][kind]
            assert {"point", "ci_lower", "ci_upper"} <= set(est)
            assert est["ci_lower"] <= est["point"] + 1e-9
    # Strong agreement on the headline overall score.
    assert svc["overall"]["icc2_1"]["point"] > 0.6

    # 2. pairwise system-vs-each-rater ICC.
    assert set(res["pairwise_system_vs_rater_icc"]) == set(res["raters"])

    # 3. inter-faculty ceiling ICC with CI.
    assert {"icc2_1", "icc2_k"} <= set(res["inter_faculty_ceiling_icc"])

    # 4. QWK on the ordinal-anchored dimensions.
    qwk = res["quadratic_weighted_kappa"]
    assert set(qwk) == set(ORDINAL_DIMENSIONS)
    assert np.mean(list(qwk.values())) > 0.5

    # 5. Bland-Altman.
    ba = res["bland_altman_overall"]
    assert {"bias", "loa_lower", "loa_upper", "prop_bias_slope", "prop_bias_p"} <= set(ba)

    # 6. G-theory + D-study (k = 1..5).
    gt = res["g_theory_overall"]
    assert [p["n_raters"] for p in gt["d_study"]] == [1, 2, 3, 4, 5]

    # 7. decision consistency at the configured cut.
    dc = res["decision_consistency_overall"]
    assert dc["cut_score"] == 0.6
    assert 0.0 <= dc["raw_agreement"] <= 1.0

    # 8. bootstrap cross-check for the overall ICC.
    boot = res["bootstrap_overall_icc2_1"]
    assert boot["method"].startswith("bootstrap")


def test_headline_metrics_are_flat_and_rounded() -> None:
    system_by_id, faculty_rows = make_validity_fixture(seed=SEED)
    res = run_validity_suite(system_by_id, faculty_rows, seed=SEED)
    flat = headline_metrics(res)
    assert flat["n_encounters"] == res["n_encounters"]
    assert isinstance(flat["overall_icc2_1_ci"], list) and len(flat["overall_icc2_1_ci"]) == 2


# --- Missing-data policy: listwise + logged count + hard error --------------------------------
def test_missing_cells_are_dropped_listwise_with_logged_count(caplog) -> None:
    system_by_id, faculty_rows = make_validity_fixture(n=30, k=3, seed=SEED)
    # Drop rater R3 for exactly 2 encounters -> 2 missing cells (2.2% < 10%).
    dropped_targets = {"syn_enc_000", "syn_enc_001"}
    thinned = [r for r in faculty_rows if not (r["encounter_id"] in dropped_targets and r["rater_id"] == "R3")]
    with caplog.at_level(logging.INFO, logger="aivmt.metrics.validity"):
        res = run_validity_suite(system_by_id, thinned, seed=SEED)
    assert res["missing_data"]["missing_cells"] == 2
    assert res["missing_data"]["dropped_listwise"] == 2
    assert res["n_encounters"] == 28
    assert "dropped listwise" in caplog.text


def test_missing_above_threshold_raises_no_silent_imputation() -> None:
    system_by_id, faculty_rows = make_validity_fixture(n=30, k=3, seed=SEED)
    # Drop R3 for 10 of 30 encounters -> 10 missing cells / 90 = 11.1% > 10%.
    targets = {f"syn_enc_{i:03d}" for i in range(10)}
    thinned = [r for r in faculty_rows if not (r["encounter_id"] in targets and r["rater_id"] == "R3")]
    with pytest.raises(ValueError, match="exceed"):
        run_validity_suite(system_by_id, thinned, seed=SEED)


def test_malformed_value_fails_loud() -> None:
    system_by_id, faculty_rows = make_validity_fixture(n=10, k=2, seed=SEED)
    faculty_rows[0]["overall"] = "not-a-number"
    with pytest.raises(ValueError, match="non-numeric"):
        run_validity_suite(system_by_id, faculty_rows, seed=SEED)


def test_out_of_range_value_fails_loud() -> None:
    system_by_id, faculty_rows = make_validity_fixture(n=10, k=2, seed=SEED)
    faculty_rows[0]["overall"] = 1.7
    with pytest.raises(ValueError, match="outside"):
        run_validity_suite(system_by_id, faculty_rows, seed=SEED)


def test_single_rater_fails_loud() -> None:
    system_by_id, faculty_rows = make_validity_fixture(n=10, k=1, seed=SEED)
    with pytest.raises(ValueError, match=">=2 distinct faculty raters"):
        run_validity_suite(system_by_id, faculty_rows, seed=SEED)


def test_threshold_constant_is_ten_percent() -> None:
    assert MISSING_DATA_HARD_THRESHOLD == 0.10


# --- Negative control --------------------------------------------------------------------------
def test_shuffled_pairing_collapses_overall_icc() -> None:
    m = check_validity_suite_negative_control(seed=SEED)
    assert m["true_icc"] >= 0.6
    assert m["shuffled_icc"] <= 0.3


# --- End-to-end run() artifact path on real-format files --------------------------------------
def _write_encounter(enc_dir, eid, row) -> None:
    score = {
        "overall": row["overall"],
        "history_completion": row["history_completion"],
        "reasoning": row["reasoning"],
        "segue": {d: row[d] for d in (
            "set_the_stage", "elicit_information", "give_information",
            "understand_perspective", "end_encounter",
        )},
    }
    (enc_dir / f"{eid}.json").write_text(
        json.dumps({"encounter_id": eid, "score": score}, ensure_ascii=False), encoding="utf-8"
    )


def test_phase_run_writes_artifacts_end_to_end(tmp_path) -> None:
    system_by_id, faculty_rows = make_validity_fixture(n=20, k=3, seed=SEED)
    enc_dir = tmp_path / "encounters"
    enc_dir.mkdir()
    for eid, row in system_by_id.items():
        _write_encounter(enc_dir, eid, row)

    fac_csv = tmp_path / "faculty_ratings.csv"
    with fac_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FACULTY_SHEET_FIELDS)
        writer.writeheader()
        for r in faculty_rows:
            writer.writerow({k: r.get(k, "") for k in FACULTY_SHEET_FIELDS})

    out_json = tmp_path / "results" / "validity_suite.json"
    phase = PhaseScoringValidity()
    phase.inputs = [enc_dir, fac_csv]
    phase.outputs = [out_json]

    result = phase.run()
    assert result["n_encounters"] == 20

    # Artifacts written: full JSON, per-analysis JSONs, and the markdown summary.
    out_dir = out_json.parent
    assert (out_dir / "validity_suite.json").exists()
    assert (out_dir / "summary.md").exists()
    assert (out_dir / "g_theory_overall.json").exists()
    assert (out_dir / "decision_consistency_overall.json").exists()
    summary = (out_dir / "summary.md").read_text(encoding="utf-8")
    assert "System vs faculty-consensus ICC" in summary

    # benchmark() now reports REAL_DATA headline numbers.
    flat = phase.benchmark()
    assert flat["status"] == "REAL_DATA"
    assert "overall_icc2_1" in flat
