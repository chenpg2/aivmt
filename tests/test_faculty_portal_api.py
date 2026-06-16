"""API tests for the blinded faculty-scoring portal (TestClient, no live server)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from aivmt.dataio import FACULTY_SHEET_FIELDS
from aivmt.faculty_portal import create_app
from aivmt.faculty_portal.storage import SCORE_FIELDS

#: A distinctive system score that MUST NOT leak into any blinded payload.
SECRET_SYSTEM_OVERALL = 0.987654321


def _transcript(encounter_id: str, case_id: str = "obgyn_aub_zh_01") -> dict[str, Any]:
    """A de-identified synthetic transcript (provenance label kept, no scores)."""
    return {
        "encounter_id": encounter_id,
        "case_id": case_id,
        "language": "zh",
        "provenance": "synthetic",
        "turns": [
            {"speaker": "student", "text": "您好,我是医学生,今天来问诊。", "t_start": 0.0, "t_end": 0.0},
            {"speaker": "patient", "text": "医生你好。", "t_start": 0.0, "t_end": 0.0},
            {"speaker": "student", "text": "末次月经是什么时候?", "t_start": 0.0, "t_end": 0.0},
            {"speaker": "patient", "text": "大概六周前。", "t_start": 0.0, "t_end": 0.0},
        ],
        "telemetry": {"duration_s": 120.0, "n_student_questions": 2, "n_voluntary_repeats": 0},
        # A planted score field to prove the blinded payload never echoes it back.
        "system_overall": SECRET_SYSTEM_OVERALL,
    }


@pytest.fixture()
def env(tmp_path: Path) -> tuple[Path, Path]:
    """A transcript dir with 3 transcripts and an (absent) ratings CSV path."""
    tdir = tmp_path / "eval_transcripts"
    tdir.mkdir()
    for eid in ("E001", "E002", "E003"):
        (tdir / f"{eid}.json").write_text(
            json.dumps(_transcript(eid), ensure_ascii=False), encoding="utf-8"
        )
    csv_path = tmp_path / "faculty_ratings.csv"
    return tdir, csv_path


@pytest.fixture()
def client(env: tuple[Path, Path]) -> TestClient:
    tdir, csv_path = env
    return TestClient(create_app(tdir, csv_path, seed=42))


def _valid_submission(encounter_id: str, rater_id: str, overall: float = 0.6) -> dict[str, Any]:
    body = {"encounter_id": encounter_id, "rater_id": rater_id, "notes": "测试备注"}
    for field in SCORE_FIELDS:
        body[field] = 0.5
    body["overall"] = overall
    return body


# --------------------------------------------------------------------------- #
def test_session_reports_full_set_initially(client: TestClient) -> None:
    resp = client.get("/api/session/fac01")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["scored"] == 0
    assert body["remaining"] == 3
    assert body["next_encounter_id"] in {"E001", "E002", "E003"}


def test_next_payload_is_blinded(client: TestClient) -> None:
    """The served transcript must never carry a system/gold score or condition."""
    resp = client.get("/api/next/fac01")
    assert resp.status_code == 200
    body = resp.json()
    payload = body["transcript"]
    assert payload is not None
    # Only de-identified transcript keys are present.
    assert set(payload.keys()) == {"encounter_id", "case_id", "language", "turns"}
    # No planted system score reaches the transcript payload.
    payload_blob = json.dumps(payload, ensure_ascii=False)
    assert "system_overall" not in payload_blob
    assert str(SECRET_SYSTEM_OVERALL) not in payload_blob
    assert "telemetry" not in payload  # behavioral signals withheld from the rater too
    for turn in payload["turns"]:
        assert set(turn.keys()) == {"speaker", "text"}


def test_round_trip_writes_valid_faculty_row(client: TestClient, env: tuple[Path, Path]) -> None:
    _, csv_path = env
    nxt = client.get("/api/next/fac01").json()
    eid = nxt["transcript"]["encounter_id"]
    resp = client.post("/api/score", json={"submission": _valid_submission(eid, "fac01")})
    assert resp.status_code == 200
    assert resp.json()["progress"]["scored"] == 1

    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == FACULTY_SHEET_FIELDS  # exact schema + order
        rows = list(reader)
    assert len(rows) == 1
    row = rows[0]
    assert row["encounter_id"] == eid
    assert row["rater_id"] == "fac01"
    assert abs(float(row["overall"]) - 0.6) < 1e-9
    for field in SCORE_FIELDS:
        assert 0.0 <= float(row[field]) <= 1.0


def test_out_of_range_returns_422_and_writes_nothing(client: TestClient, env: tuple[Path, Path]) -> None:
    _, csv_path = env
    eid = client.get("/api/next/fac01").json()["transcript"]["encounter_id"]
    bad = _valid_submission(eid, "fac01")
    bad["reasoning"] = 1.5  # out of [0, 1]
    resp = client.post("/api/score", json={"submission": bad})
    assert resp.status_code == 422
    fields = {e["field"] for e in resp.json()["detail"]["errors"]}
    assert "reasoning" in fields
    assert not csv_path.exists()  # fail loud: nothing written


def test_non_numeric_returns_422(client: TestClient) -> None:
    eid = client.get("/api/next/fac01").json()["transcript"]["encounter_id"]
    bad = _valid_submission(eid, "fac01")
    bad["overall"] = "好"
    resp = client.post("/api/score", json={"submission": bad})
    assert resp.status_code == 422


def test_missing_field_returns_422(client: TestClient) -> None:
    eid = client.get("/api/next/fac01").json()["transcript"]["encounter_id"]
    bad = _valid_submission(eid, "fac01")
    del bad["history_completion"]
    resp = client.post("/api/score", json={"submission": bad})
    assert resp.status_code == 422
    fields = {e["field"] for e in resp.json()["detail"]["errors"]}
    assert "history_completion" in fields


def test_duplicate_rating_refused(client: TestClient) -> None:
    eid = client.get("/api/next/fac01").json()["transcript"]["encounter_id"]
    sub = _valid_submission(eid, "fac01")
    assert client.post("/api/score", json={"submission": sub}).status_code == 200
    dup = client.post("/api/score", json={"submission": sub})
    assert dup.status_code == 409


def test_explicit_rescore_overwrites(client: TestClient, env: tuple[Path, Path]) -> None:
    _, csv_path = env
    eid = client.get("/api/next/fac01").json()["transcript"]["encounter_id"]
    client.post("/api/score", json={"submission": _valid_submission(eid, "fac01", overall=0.2)})
    resp = client.post(
        "/api/score",
        json={"submission": _valid_submission(eid, "fac01", overall=0.9), "overwrite": True},
    )
    assert resp.status_code == 200
    with csv_path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1  # re-score replaces, never duplicates
    assert abs(float(rows[0]["overall"]) - 0.9) < 1e-9


def test_resume_skips_already_scored(client: TestClient) -> None:
    first = client.get("/api/next/fac01").json()["transcript"]["encounter_id"]
    client.post("/api/score", json={"submission": _valid_submission(first, "fac01")})
    nxt = client.get("/api/next/fac01").json()
    assert nxt["progress"]["scored"] == 1
    assert nxt["transcript"]["encounter_id"] != first  # the served one is unscored


def test_full_pass_reaches_done(client: TestClient) -> None:
    for _ in range(3):
        eid = client.get("/api/next/fac01").json()["transcript"]["encounter_id"]
        assert client.post("/api/score", json={"submission": _valid_submission(eid, "fac01")}).status_code == 200
    done = client.get("/api/next/fac01").json()
    assert done["done"] is True
    assert done["transcript"] is None
    assert done["progress"]["remaining"] == 0


def test_two_raters_score_independently(client: TestClient, env: tuple[Path, Path]) -> None:
    _, csv_path = env
    e1 = client.get("/api/next/fac01").json()["transcript"]["encounter_id"]
    client.post("/api/score", json={"submission": _valid_submission(e1, "fac01")})
    # fac02 still sees all 3 unscored.
    s2 = client.get("/api/session/fac02").json()
    assert s2["scored"] == 0 and s2["remaining"] == 3
    e2 = client.get("/api/next/fac02").json()["transcript"]["encounter_id"]
    client.post("/api/score", json={"submission": _valid_submission(e2, "fac02")})

    with csv_path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    raters = {r["rater_id"] for r in rows}
    assert raters == {"fac01", "fac02"}


def test_serving_order_is_fixed_canonical_for_all_raters(client: TestClient) -> None:
    first = client.get("/api/session/facA").json()["next_encounter_id"]
    assert client.get("/api/session/facA").json()["next_encounter_id"] == first  # deterministic
    # Every rater starts at the SAME canonical-first encounter — the serving order matches the
    # offline scoring packet so operator data entry is a straight sequential pass (no per-rater shuffle).
    for i in range(6):
        assert client.get(f"/api/session/fac{i}").json()["next_encounter_id"] == first


def test_score_for_unknown_encounter_404(client: TestClient) -> None:
    resp = client.post("/api/score", json={"submission": _valid_submission("NOPE", "fac01")})
    assert resp.status_code == 404


def test_empty_rater_id_422(client: TestClient) -> None:
    assert client.get("/api/session/%20").status_code == 422
