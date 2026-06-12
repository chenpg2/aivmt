"""Tests for encounter capture/export (WS-F)."""

from __future__ import annotations

import csv

from aivmt.dataio import (
    FACULTY_SHEET_FIELDS,
    build_pairs,
    export_faculty_rating_sheet,
    load_encounter,
    save_encounter,
    transcript_from_dict,
)
from aivmt.llm import LLMFactory
from aivmt.pipeline import ScoringPipeline
from aivmt.schemas import Case, ChecklistItem, Telemetry, Transcript, Turn


def _case() -> Case:
    return Case(
        case_id="c1",
        title="急性胸痛",
        language="zh",
        persona="p",
        history_checklist=(ChecklistItem("q_onset", "询问起病时间"),),
    )


def _transcript() -> Transcript:
    turns = (
        Turn("student", "哪里不舒服?", 0.0, 2.0),
        Turn("patient", "胸口疼。", 2.0, 4.0),
    )
    return Transcript("enc_1", "c1", "zh", turns, Telemetry(4.0, 1, 0))


def test_save_and_load_round_trip(tmp_path) -> None:
    result = ScoringPipeline(LLMFactory("mock")).run(_case(), _transcript())
    path = save_encounter(result, _transcript(), tmp_path / "enc_1.json")
    assert path.exists()

    data = load_encounter(path)
    assert data["encounter_id"] == "enc_1"
    assert data["model_id"] == "mock"
    assert data["language"] == "zh"
    assert 0.0 <= data["score"]["overall"] <= 1.0
    assert len(data["transcript"]["turns"]) == 2

    # transcript rebuilds faithfully
    tx = transcript_from_dict(data["transcript"])
    assert tx.encounter_id == "enc_1"
    assert tx.turns[1].text == "胸口疼。"
    assert tx.telemetry.n_student_questions == 1


def test_export_faculty_sheet(tmp_path) -> None:
    path = export_faculty_rating_sheet(["enc_1", "enc_2", "enc_3"], tmp_path / "sheet.csv")
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [*rows[0].keys()] == FACULTY_SHEET_FIELDS
    assert [r["encounter_id"] for r in rows] == ["enc_1", "enc_2", "enc_3"]
    # scores are blank (blinded)
    assert rows[0]["overall"] == ""


def test_build_pairs_shape() -> None:
    pairs = build_pairs([0.1, 0.2, 0.3], [0.2, 0.1, 0.4])
    assert pairs.shape == (3, 2)
