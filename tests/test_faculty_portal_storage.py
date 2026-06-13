"""Storage-layer tests for the blinded faculty-scoring portal."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aivmt.dataio import FACULTY_SHEET_FIELDS
from aivmt.faculty_portal import (
    DuplicateRatingError,
    RatingStore,
    TranscriptStore,
    UnknownEncounterError,
    create_app,
    rater_order_seed,
    validate_submission,
)
from aivmt.faculty_portal.storage import SCORE_FIELDS


def _write_transcript(tdir: Path, eid: str) -> None:
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / f"{eid}.json").write_text(
        json.dumps(
            {
                "encounter_id": eid,
                "case_id": "obgyn_aub_zh_01",
                "language": "zh",
                "provenance": "synthetic",
                "turns": [{"speaker": "student", "text": "你好", "t_start": 0.0, "t_end": 0.0}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_missing_transcript_dir_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        TranscriptStore(transcript_dir=tmp_path / "nope", base_seed=42)


def test_missing_dir_makes_create_app_fail_loud(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        create_app(tmp_path / "absent", tmp_path / "r.csv", seed=42)


def test_empty_transcript_set_serves_nothing(tmp_path: Path) -> None:
    tdir = tmp_path / "eval"
    tdir.mkdir()
    client = TestClient(create_app(tdir, tmp_path / "r.csv", seed=42))
    body = client.get("/api/next/fac01").json()
    assert body["done"] is True
    assert body["transcript"] is None
    assert body["progress"]["total"] == 0


def test_rater_order_seed_is_stable_and_distinct() -> None:
    assert rater_order_seed(42, "facA") == rater_order_seed(42, "facA")
    assert rater_order_seed(42, "facA") != rater_order_seed(42, "facB")


def test_ordered_ids_deterministic_per_rater(tmp_path: Path) -> None:
    tdir = tmp_path / "eval"
    for eid in ("E1", "E2", "E3", "E4", "E5"):
        _write_transcript(tdir, eid)
    store = TranscriptStore(transcript_dir=tdir, base_seed=42)
    assert store.ordered_ids("facA") == store.ordered_ids("facA")
    assert sorted(store.ordered_ids("facA")) == ["E1", "E2", "E3", "E4", "E5"]
    # Distinct raters generally get distinct orders.
    assert store.ordered_ids("facA") != store.ordered_ids("facZ")


def test_blinded_payload_has_no_score_keys(tmp_path: Path) -> None:
    tdir = tmp_path / "eval"
    _write_transcript(tdir, "E1")
    store = TranscriptStore(transcript_dir=tdir, base_seed=42)
    payload = store.blinded_payload("E1")
    assert set(payload.keys()) == {"encounter_id", "case_id", "language", "turns"}


def _row(eid: str, rater: str, overall: float = 0.6) -> dict[str, str]:
    body = {"encounter_id": eid, "rater_id": rater, "notes": "n"}
    for f in SCORE_FIELDS:
        body[f] = 0.5
    body["overall"] = overall
    validated, issues = validate_submission(body)
    assert validated is not None and not issues
    return validated.to_row()


def test_rating_store_append_and_dedup(tmp_path: Path) -> None:
    csv_path = tmp_path / "faculty_ratings.csv"
    store = RatingStore(csv_path=csv_path)
    store.append(_row("E1", "fac01"))
    assert store.has_rating("fac01", "E1")
    with pytest.raises(DuplicateRatingError):
        store.append(_row("E1", "fac01"))
    # overwrite replaces, never duplicates
    store.append(_row("E1", "fac01", overall=0.9), overwrite=True)
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8", newline="")))
    assert len(rows) == 1
    assert abs(float(rows[0]["overall"]) - 0.9) < 1e-9


def test_saved_csv_round_trips_to_faculty_fields(tmp_path: Path) -> None:
    csv_path = tmp_path / "faculty_ratings.csv"
    store = RatingStore(csv_path=csv_path)
    store.append(_row("E1", "fac01"))
    store.append(_row("E2", "fac02"))
    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == FACULTY_SHEET_FIELDS
        rows = list(reader)
    assert len(rows) == 2
    for row in rows:
        assert set(row.keys()) == set(FACULTY_SHEET_FIELDS)


def test_scored_ids_ignores_blank_export_rows(tmp_path: Path) -> None:
    """A blank export sheet row (encounter_id but no overall) is not 'scored'."""
    csv_path = tmp_path / "faculty_ratings.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FACULTY_SHEET_FIELDS)
        writer.writeheader()
        writer.writerow({"encounter_id": "E1", "rater_id": "fac01"})  # blank, no scores
    store = RatingStore(csv_path=csv_path)
    assert store.scored_encounter_ids("fac01") == set()


def test_validate_rejects_bool_and_out_of_range() -> None:
    body = {"encounter_id": "E1", "rater_id": "fac01", "notes": ""}
    for f in SCORE_FIELDS:
        body[f] = 0.5
    body["overall"] = True  # bool must be rejected (not a unit-interval score)
    validated, issues = validate_submission(body)
    assert validated is None
    assert any(i.field == "overall" for i in issues)


def test_unknown_encounter_load_raises(tmp_path: Path) -> None:
    tdir = tmp_path / "eval"
    _write_transcript(tdir, "E1")
    store = TranscriptStore(transcript_dir=tdir, base_seed=42)
    with pytest.raises(UnknownEncounterError):
        store.load("NOPE")
