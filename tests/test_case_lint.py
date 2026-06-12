"""Tests for the case linter CLI (Stream B)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from aivmt.case_lint import lint_path, main

ROOT = Path(__file__).resolve().parents[1]
CONF_CASE = ROOT / "conf" / "case"

_VALID_YAML = textwrap.dedent(
    """\
    case_id: lint_demo
    version: "1.0.0"
    title: Demo
    language: en
    specialty: cardiology
    difficulty: moderate
    demographics: {age: "40", sex: male, occupation: teacher, marital_status: married}
    chief_complaint: Chest pain
    hpi:
      onset: 1 hour ago
      location: Retrosternal
      duration: 1 hour
      character: Crushing
      aggravating: Exertion
      relieving: Rest
      timing: Constant
      severity: Severe
      associated_symptoms: [Sweating]
    pmh: [None]
    medications: [None]
    allergies: [None]
    family_history: [None]
    social_history: [Non-smoker]
    hidden_info:
      - {info_id: hi_1, content: Radiates to left arm, trigger: Asked about radiation}
    emotional_state: Anxious
    disclosure_profile: Answers only when asked
    persona: |
      You are a 40-year-old man with chest pain.
    history_checklist:
      - {item_id: q_onset, text: Ask onset, weight: 1.0}
    """
)


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_real_cases_lint_pass_with_warnings() -> None:
    report = lint_path(CONF_CASE)
    assert report.n_files == 5
    assert report.errors == ()
    assert report.ok
    assert len(report.warnings) > 0  # TODO_COLLAB placeholders are expected


def test_fully_authored_case_has_no_warnings(tmp_path: Path) -> None:
    _write(tmp_path / "ok.yaml", _VALID_YAML)
    report = lint_path(tmp_path)
    assert report.ok
    assert report.warnings == ()


def test_todo_collab_is_warning_not_error(tmp_path: Path) -> None:
    yaml = _VALID_YAML.replace("location: Retrosternal", "location: TODO_COLLAB")
    _write(tmp_path / "todo.yaml", yaml)
    report = lint_path(tmp_path)
    assert report.ok  # exit 0
    assert any("hpi.location" in w for w in report.warnings)


def test_schema_violation_is_error(tmp_path: Path) -> None:
    yaml = _VALID_YAML.replace('case_id: lint_demo\n', "")  # drop a required field
    _write(tmp_path / "broken.yaml", yaml)
    report = lint_path(tmp_path)
    assert not report.ok
    assert any("case_id" in e for e in report.errors)


def test_bad_language_is_error(tmp_path: Path) -> None:
    yaml = _VALID_YAML.replace("language: en", "language: fr")
    _write(tmp_path / "lang.yaml", yaml)
    report = lint_path(tmp_path)
    assert not report.ok
    assert any("language" in e for e in report.errors)


def test_main_passes_on_real_cases() -> None:
    assert main([str(CONF_CASE)]) == 0


def test_main_fails_on_broken_case(tmp_path: Path) -> None:
    _write(tmp_path / "broken.yaml", _VALID_YAML.replace("version: \"1.0.0\"\n", ""))
    assert main([str(tmp_path)]) == 1


def test_missing_path_returns_error_code(tmp_path: Path) -> None:
    assert main([str(tmp_path / "does_not_exist")]) == 1
