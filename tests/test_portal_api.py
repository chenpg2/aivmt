"""API tests for the case-entry portal (FastAPI TestClient, no live server)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from aivmt.case_lint import lint_path
from aivmt.case_schema import TODO_COLLAB, load_clinical_case
from aivmt.persona import DIFFICULTY_LEVELS
from aivmt.portal import create_app

#: Distinctive hidden fact used to assert the persona-isolation invariant.
HIDDEN_FACT = "昨天开始有少量暗红色阴道流血。"


def make_draft(case_id: str = "portal_demo_zh") -> dict[str, Any]:
    """A valid form-shaped draft with deliberate blanks (-> TODO_COLLAB)."""
    return {
        "case_id": case_id,
        "version": "1.0.0",
        "title": "测试病例:下腹痛",
        "language": "zh",
        "specialty": "obgyn",
        "difficulty": "moderate",
        "demographics": {"age": "28", "sex": "female", "occupation": "", "marital_status": "已婚"},
        "chief_complaint": "下腹隐痛一天",
        "hpi": {
            "onset": "今天", "location": "下腹", "duration": "", "character": "隐痛",
            "aggravating": "", "relieving": "", "timing": "", "severity": "",
            "associated_symptoms": ["站起来时头晕"],
        },
        "pmh": [],  # blank history list -> [TODO_COLLAB], never silently "no history"
        "medications": [],
        "allergies": ["无"],
        "family_history": [],
        "social_history": [],
        "pertinent_negatives": ["没有发热"],
        "obgyn": {
            "lmp": "末次月经大约6周前", "menstrual_history": "", "obstetric_history": "",
            "contraception": "", "sexual_history": "",
        },
        "hidden_info": [
            {"info_id": "hi_bleeding", "content": HIDDEN_FACT, "trigger": "询问阴道流血的量、颜色"},
        ],
        "red_herrings": [
            {"herring_id": "rh_cough", "content": "最近偶尔有点咳嗽", "note": "良性"},
        ],
        "emotional_state": "口语化、简短,略带紧张。",
        "disclosure_profile": "只回答被直接问到的内容,绝不主动透露。",
        "persona": "",  # blank optional clinical free text -> TODO_COLLAB
        "history_checklist": [
            {"item_id": "hx_lmp", "text": "询问末次月经/停经时间", "weight": "1.0"},
            {"item_id": "hx_bleeding", "text": "询问阴道流血情况", "weight": ""},
        ],
    }


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path))


# --------------------------------------------------------------------------- #
# Static page + list
# --------------------------------------------------------------------------- #
def test_index_served(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "病历录入" in resp.text


def test_list_empty(client: TestClient) -> None:
    resp = client.get("/api/cases")
    assert resp.status_code == 200
    assert resp.json() == []


# --------------------------------------------------------------------------- #
# Save -> list -> load round-trip
# --------------------------------------------------------------------------- #
def test_save_list_load_roundtrip(client: TestClient, tmp_path: Path) -> None:
    resp = client.post("/api/cases", json={"case": make_draft(), "overwrite": False})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["path"] == "portal_demo_zh.yaml"
    assert len(body["warnings"]) > 0  # blanks were marked TODO_COLLAB

    saved = tmp_path / "portal_demo_zh.yaml"
    assert saved.is_file()

    # the saved file round-trips through the REAL linter with 0 errors
    report = lint_path(tmp_path)
    assert report.n_files == 1
    assert report.errors == ()
    assert len(report.warnings) > 0

    listed = client.get("/api/cases").json()
    assert len(listed) == 1
    assert listed[0]["case_id"] == "portal_demo_zh"
    assert listed[0]["n_errors"] == 0
    assert listed[0]["n_warnings"] > 0
    assert listed[0]["title"] == "测试病例:下腹痛"

    loaded = client.get("/api/cases/portal_demo_zh")
    assert loaded.status_code == 200
    case = loaded.json()["case"]
    assert case["chief_complaint"] == "下腹隐痛一天"
    assert case["persona"] == TODO_COLLAB           # blank -> placeholder, not invented
    assert case["pmh"] == [TODO_COLLAB]             # blank history list -> placeholder
    assert case["allergies"] == ["无"]              # explicit "none" preserved verbatim
    assert case["demographics"]["occupation"] == TODO_COLLAB
    assert case["hidden_info"][0]["content"] == HIDDEN_FACT
    assert case["history_checklist"][1]["weight"] == 1.0  # blank weight -> default

    # and the saved YAML is loadable as a typed ClinicalCase
    clinical = load_clinical_case(saved)
    assert clinical.case_id == "portal_demo_zh"
    assert clinical.obgyn is not None
    assert clinical.obgyn.lmp == "末次月经大约6周前"


def test_load_missing_404(client: TestClient) -> None:
    assert client.get("/api/cases/no_such_case").status_code == 404


# --------------------------------------------------------------------------- #
# Validation: server is the source of truth; invalid drafts never written
# --------------------------------------------------------------------------- #
def test_invalid_language_422_and_not_written(client: TestClient, tmp_path: Path) -> None:
    draft = make_draft("bad_lang_case")
    draft["language"] = "fr"
    resp = client.post("/api/cases", json={"case": draft, "overwrite": False})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["errors"], detail
    assert any(e["field"] == "language" for e in detail["errors"])
    assert list(tmp_path.glob("*.yaml")) == []  # nothing written


def test_bad_weight_422_and_not_written(client: TestClient, tmp_path: Path) -> None:
    draft = make_draft("bad_weight_case")
    draft["history_checklist"][0]["weight"] = "很重要"
    resp = client.post("/api/cases", json={"case": draft, "overwrite": False})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert any("weight" in e["field"] for e in detail["errors"])
    assert list(tmp_path.glob("*.yaml")) == []


def test_portal_required_fields_zh_messages(client: TestClient, tmp_path: Path) -> None:
    draft = make_draft("")
    draft["case_id"] = ""
    draft["hidden_info"][0]["trigger"] = ""  # trigger is the pedagogical gate: required
    resp = client.post("/api/cases", json={"case": draft, "overwrite": False})
    assert resp.status_code == 422
    errors = resp.json()["detail"]["errors"]
    fields = {e["field"] for e in errors}
    assert "case_id" in fields
    assert "hidden_info[0].trigger" in fields
    assert any("必填" in e["message"] for e in errors)        # zh-friendly messages
    assert any("触发条件" in e["message"] for e in errors)
    assert list(tmp_path.glob("*.yaml")) == []


def test_validate_endpoint_reports_without_writing(client: TestClient, tmp_path: Path) -> None:
    resp = client.post("/api/validate", json=make_draft())
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["errors"] == []
    assert len(body["warnings"]) > 0
    assert body["normalized"]["persona"] == TODO_COLLAB
    assert any("TODO_COLLAB" in w["message"] for w in body["warnings"])
    assert list(tmp_path.glob("*.yaml")) == []  # validate never writes


# --------------------------------------------------------------------------- #
# Overwrite protection
# --------------------------------------------------------------------------- #
def test_overwrite_protection(client: TestClient) -> None:
    draft = make_draft("ow_case")
    assert client.post("/api/cases", json={"case": draft, "overwrite": False}).status_code == 200
    second = client.post("/api/cases", json={"case": draft, "overwrite": False})
    assert second.status_code == 409
    assert "已存在" in second.json()["detail"]
    third = client.post("/api/cases", json={"case": draft, "overwrite": True})
    assert third.status_code == 200


# --------------------------------------------------------------------------- #
# Persona preview: deterministic, all difficulties, hidden_info isolation
# --------------------------------------------------------------------------- #
def test_preview_deterministic_all_difficulties(client: TestClient) -> None:
    draft = make_draft()
    first = client.post("/api/preview", json=draft)
    second = client.post("/api/preview", json=copy.deepcopy(draft))
    assert first.status_code == 200
    assert first.json() == second.json()  # deterministic compile, no LLM
    previews = first.json()["previews"]
    assert set(previews) == set(DIFFICULTY_LEVELS)
    assert first.json()["language"] == "zh"
    for difficulty in DIFFICULTY_LEVELS:
        assert previews[difficulty]["prompt"].strip()


def test_preview_hidden_info_isolation(client: TestClient) -> None:
    previews = client.post("/api/preview", json=make_draft()).json()["previews"]
    for difficulty in DIFFICULTY_LEVELS:
        sections = previews[difficulty]["sections"]
        assert HIDDEN_FACT in sections["disclosure"]
        assert HIDDEN_FACT not in sections["opening"]      # never leaks into opening
        assert HIDDEN_FACT not in sections["background"]   # nor general background


def test_preview_invalid_draft_422(client: TestClient) -> None:
    draft = make_draft()
    draft["history_checklist"] = []
    resp = client.post("/api/preview", json=draft)
    assert resp.status_code == 422
    assert any(e["field"] == "history_checklist" for e in resp.json()["detail"]["errors"])
