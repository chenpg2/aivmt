"""Storage-level tests: atomic write, overwrite refusal, fail-loud paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import aivmt.portal.storage as storage_mod
from aivmt.portal import CaseExistsError, CaseStore, PortalStorageError, create_app, default_case_dir
from aivmt.portal.draft import validate_draft
from tests.test_portal_api import make_draft


def _normalized(case_id: str = "atomic_case") -> dict[str, Any]:
    result = validate_draft(make_draft(case_id))
    assert result.ok and result.normalized is not None
    return result.normalized


# --------------------------------------------------------------------------- #
# Fail-loud construction + case_id hygiene
# --------------------------------------------------------------------------- #
def test_missing_case_dir_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        CaseStore(case_dir=tmp_path / "nope")
    with pytest.raises(FileNotFoundError):
        create_app(tmp_path / "nope")


def test_default_case_dir_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIVMT_CASE_DIR", str(tmp_path))
    assert default_case_dir() == tmp_path
    monkeypatch.delenv("AIVMT_CASE_DIR")
    assert default_case_dir() == Path("conf/case")


def test_path_traversal_case_id_rejected(tmp_path: Path) -> None:
    store = CaseStore(case_dir=tmp_path)
    data = _normalized()
    data["case_id"] = "../evil"
    with pytest.raises(PortalStorageError):
        store.save(data, overwrite=False)
    assert list(tmp_path.iterdir()) == []


def test_list_uses_file_stem_so_every_row_is_loadable(tmp_path: Path) -> None:
    """Legacy files may carry an internal case_id != file stem (e.g. the
    example_chestpain_* cases). The list must report the file stem — the
    routing identity of GET /api/cases/{case_id} — or those rows 404."""
    store = CaseStore(case_dir=tmp_path)
    saved = store.save(_normalized("portal_authored"), overwrite=False)
    legacy = tmp_path / "legacy_stem.yaml"
    legacy.write_text(
        saved.read_text(encoding="utf-8").replace(
            "case_id: portal_authored", "case_id: internal_id_differs"
        ),
        encoding="utf-8",
    )
    summaries = {s.case_id: s for s in store.list_cases()}
    assert set(summaries) == {"portal_authored", "legacy_stem"}
    for case_id, summary in summaries.items():
        assert summary.file_name == f"{case_id}.yaml"
        assert store.load(case_id)  # every listed row resolves


# --------------------------------------------------------------------------- #
# Overwrite refusal
# --------------------------------------------------------------------------- #
def test_store_overwrite_refusal(tmp_path: Path) -> None:
    store = CaseStore(case_dir=tmp_path)
    data = _normalized()
    target = store.save(data, overwrite=False)
    assert target.name == "atomic_case.yaml"
    with pytest.raises(CaseExistsError):
        store.save(data, overwrite=False)
    assert store.save(data, overwrite=True) == target


# --------------------------------------------------------------------------- #
# Atomicity: simulated failures leave NO partial / temp files behind
# --------------------------------------------------------------------------- #
def test_serialization_failure_touches_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = CaseStore(case_dir=tmp_path)

    def boom(data: dict[str, Any]) -> str:
        raise PortalStorageError("模拟序列化失败")

    monkeypatch.setattr(storage_mod, "dump_yaml", boom)
    with pytest.raises(PortalStorageError):
        store.save(_normalized(), overwrite=False)
    assert list(tmp_path.iterdir()) == []  # not even a temp file


def test_replace_failure_cleans_temp_and_leaves_no_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = CaseStore(case_dir=tmp_path)

    def broken_replace(src: Any, dst: Any) -> None:
        raise OSError("模拟磁盘故障")

    monkeypatch.setattr(storage_mod.os, "replace", broken_replace)
    with pytest.raises(PortalStorageError):
        store.save(_normalized(), overwrite=False)
    assert list(tmp_path.iterdir()) == []  # temp file cleaned up, no partial case


def test_replace_failure_keeps_previous_version_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = CaseStore(case_dir=tmp_path)
    target = store.save(_normalized(), overwrite=False)
    before = target.read_text(encoding="utf-8")

    def broken_replace(src: Any, dst: Any) -> None:
        raise OSError("模拟磁盘故障")

    monkeypatch.setattr(storage_mod.os, "replace", broken_replace)
    with pytest.raises(PortalStorageError):
        store.save(_normalized(), overwrite=True)
    assert target.read_text(encoding="utf-8") == before  # old version untouched
    assert sorted(p.name for p in tmp_path.iterdir()) == [target.name]
