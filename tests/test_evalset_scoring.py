"""Tests for the eval-set system-scoring path (-> data/encounters/ for PhaseScoringValidity).

Verifies the MOCK (offline, deterministic) scoring path:
* writes one valid encounter JSON per transcript in the dataio format;
* every encounter satisfies the SQ1 input contract (overall + history_completion +
  reasoning + five SEGUE domains, all in [0, 1]);
* PhaseScoringValidity.run() loads the mock-scored encounters end-to-end when
  paired with a synthetic faculty CSV (round-trip on a tmp dir);
* a blank blinded faculty-rating sheet is exported with the right schema and ids.

The REAL local-model batch is NOT run here (GPU busy by directive).
"""

from __future__ import annotations

import csv

import pytest

from aivmt.dataio import FACULTY_SHEET_FIELDS, load_encounter
from aivmt.evalset import (
    export_blank_faculty_sheet,
    generate_for_case,
    load_obgyn_cases,
    score_eval_set,
)
from aivmt.evalset.scoring import REAL_SCORE_COMMAND
from aivmt.llm import LLMFactory
from aivmt.metrics.validity import SEGUE_DOMAINS
from harness.contracts.scoring_validity import check_scoring_validity_inputs
from harness.registry import PhaseScoringValidity, load_seed

SEED = load_seed()
PER_CASE = 6


def _scored(tmp_path):
    cases = load_obgyn_cases()
    transcripts = []
    for case in cases:
        transcripts.extend(
            g.transcript for g in generate_for_case(case, seed=SEED, n_transcripts=PER_CASE)
        )
    enc_dir = tmp_path / "encounters"
    scored = score_eval_set(transcripts, cases, LLMFactory("mock"), enc_dir)
    return cases, transcripts, enc_dir, scored


def test_mock_scoring_writes_one_encounter_per_transcript(tmp_path) -> None:
    cases, transcripts, enc_dir, scored = _scored(tmp_path)
    assert len(scored) == len(transcripts) == PER_CASE * len(cases)
    files = sorted(enc_dir.glob("*.json"))
    assert len(files) == len(transcripts)
    # ids round-trip and match transcripts.
    assert {s.encounter_id for s in scored} == {tx.encounter_id for tx in transcripts}


def test_mock_encounters_have_full_score_shape(tmp_path) -> None:
    _, _, enc_dir, _ = _scored(tmp_path)
    for f in sorted(enc_dir.glob("*.json")):
        data = load_encounter(f)
        score = data["score"]
        assert 0.0 <= score["overall"] <= 1.0
        for dim in ("history_completion", "reasoning"):
            assert 0.0 <= score[dim] <= 1.0
        assert set(SEGUE_DOMAINS) <= set(score["segue"])
        for dom in SEGUE_DOMAINS:
            assert 0.0 <= score["segue"][dom] <= 1.0


def test_unknown_case_id_fails_loud(tmp_path) -> None:
    cases = load_obgyn_cases()
    g = generate_for_case(cases[0], seed=SEED, n_transcripts=2)[0]
    # Hand-build a transcript pointing at a case not in the set.
    from aivmt.schemas import Transcript

    orphan = Transcript(
        encounter_id="eval_orphan_00",
        case_id="not_a_real_case",
        language="zh",
        turns=g.transcript.turns,
    )
    with pytest.raises(KeyError, match="unknown case_id"):
        score_eval_set([orphan], cases, LLMFactory("mock"), tmp_path / "enc")


def _write_faculty_csv(path, encounter_ids) -> None:
    """Two synthetic raters per encounter (apparatus): satisfies the >=2-rater contract."""
    rows = []
    dims = ("set_the_stage", "elicit_information", "give_information",
            "understand_perspective", "end_encounter",
            "history_completion", "reasoning", "overall")
    for i, eid in enumerate(sorted(encounter_ids)):
        for rid, base in (("R1", 0.5), ("R2", 0.55)):
            val = min(1.0, base + (i % 5) * 0.05)
            row = {"encounter_id": eid, "rater_id": rid, "notes": ""}
            for d in dims:
                row[d] = round(val, 3)
            rows.append(row)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FACULTY_SHEET_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in FACULTY_SHEET_FIELDS})


def test_phase_scoring_validity_loads_mock_encounters_end_to_end(tmp_path) -> None:
    """The mock-scored encounters + a synthetic faculty CSV satisfy the contract and
    drive PhaseScoringValidity.run() to a real validity-suite result."""
    _, transcripts, enc_dir, scored = _scored(tmp_path)
    fac_csv = tmp_path / "faculty_ratings.csv"
    _write_faculty_csv(fac_csv, [s.encounter_id for s in scored])

    # The SQ1 input contract accepts these inputs (no silent fallback).
    check_scoring_validity_inputs(enc_dir, fac_csv)

    out_json = tmp_path / "results" / "validity_suite.json"
    phase = PhaseScoringValidity()
    phase.inputs = [enc_dir, fac_csv]
    phase.outputs = [out_json]

    result = phase.run()
    assert result["n_encounters"] == len(transcripts)
    assert result["n_raters"] == 2
    assert (out_json.parent / "validity_suite.json").exists()
    assert (out_json.parent / "summary.md").exists()


def test_export_blank_faculty_sheet_schema_and_ids(tmp_path) -> None:
    _, _, _, scored = _scored(tmp_path)
    path = export_blank_faculty_sheet(scored, tmp_path / "sheet.csv")
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [*rows[0].keys()] == FACULTY_SHEET_FIELDS
    assert {r["encounter_id"] for r in rows} == {s.encounter_id for s in scored}
    # Blinded: every score cell is blank.
    assert all(r["overall"] == "" for r in rows)


def test_real_score_command_is_documented() -> None:
    assert "score_eval_set.py" in REAL_SCORE_COMMAND
    assert "--model" in REAL_SCORE_COMMAND
