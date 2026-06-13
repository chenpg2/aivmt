"""Case-directory storage for the portal: list / load / atomic save.

Lint status is obtained by reusing :func:`aivmt.case_lint.lint_path` on each
file — the portal never re-implements validation. Saves are atomic (temp file
in the same directory + ``os.replace``) and refuse to overwrite an existing
case unless explicitly told to. A schema-invalid case is never written: the
API layer validates the draft *before* calling :meth:`CaseStore.save`.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from omegaconf import OmegaConf
from omegaconf.errors import OmegaConfBaseException

from ..case_lint import lint_path

logger = logging.getLogger(__name__)

__all__ = [
    "PortalStorageError",
    "CaseExistsError",
    "CaseSummary",
    "CaseStore",
    "default_case_dir",
    "dump_yaml",
    "CASE_ID_RE",
]

#: Filesystem-safe case identifier (also the YAML file stem). Guards path traversal.
CASE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

#: Environment variable overriding the default case directory.
CASE_DIR_ENV = "AIVMT_CASE_DIR"


class PortalStorageError(RuntimeError):
    """Raised on storage-level failures (bad case_id, missing dir, write errors)."""


class CaseExistsError(PortalStorageError):
    """Raised when a save would overwrite an existing case without ``overwrite=True``."""


def default_case_dir() -> Path:
    """Resolve the case directory: ``$AIVMT_CASE_DIR`` or ``conf/case``."""
    return Path(os.environ.get(CASE_DIR_ENV, "conf/case"))


def dump_yaml(data: dict[str, Any]) -> str:
    """Serialize a normalized case dict to YAML (insertion order, unicode kept).

    Module-level on purpose so tests can monkeypatch it to simulate failures.
    """
    cfg = OmegaConf.create(data)
    return OmegaConf.to_yaml(cfg, sort_keys=False)


@dataclass(frozen=True)
class CaseSummary:
    """One row of the portal's case list."""

    case_id: str
    file_name: str
    title: Optional[str]
    language: Optional[str]
    specialty: Optional[str]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        """JSON-ready representation for the API layer."""
        return {
            "case_id": self.case_id,
            "file_name": self.file_name,
            "title": self.title,
            "language": self.language,
            "specialty": self.specialty,
            "n_errors": len(self.errors),
            "n_warnings": len(self.warnings),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def _read_raw(path: Path) -> dict[str, Any]:
    """Load a case YAML into a plain dict (no schema validation)."""
    try:
        cfg = OmegaConf.load(str(path))
        data = OmegaConf.to_container(cfg, resolve=True)
    except (OSError, OmegaConfBaseException) as exc:
        raise PortalStorageError(f"无法读取病例文件 {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise PortalStorageError(f"病例文件 {path.name} 顶层必须是映射(mapping)")
    return {str(k): v for k, v in data.items()}


@dataclass(frozen=True)
class CaseStore:
    """All filesystem access for the portal, rooted at one case directory."""

    case_dir: Path

    def __post_init__(self) -> None:
        if not self.case_dir.is_dir():
            raise FileNotFoundError(
                f"病例目录不存在 (case directory not found): {self.case_dir}"
            )

    # ------------------------------------------------------------------ #
    def path_for(self, case_id: str) -> Path:
        """Target YAML path for ``case_id`` (validates the identifier)."""
        if not CASE_ID_RE.match(case_id):
            raise PortalStorageError(
                f"非法病例编号 '{case_id}':只允许小写字母、数字、下划线,且以字母开头"
            )
        return self.case_dir / f"{case_id}.yaml"

    def exists(self, case_id: str) -> bool:
        """True if a case file for ``case_id`` already exists."""
        return self.path_for(case_id).is_file()

    def list_cases(self) -> list[CaseSummary]:
        """Summaries (with reused lint status) for every ``*.yaml`` in the dir.

        ``case_id`` is always the file stem — the routing identity used by
        ``GET /api/cases/{case_id}`` and :meth:`load`. Legacy hand-authored
        files may carry a different internal ``case_id``; using the stem here
        keeps every listed row loadable.
        """
        summaries: list[CaseSummary] = []
        for path in sorted(self.case_dir.glob("*.yaml")):
            report = lint_path(path)  # reuse: schema=ERROR, TODO_COLLAB=WARNING
            title = language = specialty = None
            case_id = path.stem
            try:
                raw = _read_raw(path)
            except PortalStorageError:
                raw = {}
            if raw:
                title = raw.get("title")
                language = raw.get("language")
                specialty = raw.get("specialty")
            summaries.append(
                CaseSummary(
                    case_id=case_id,
                    file_name=path.name,
                    title=str(title) if title is not None else None,
                    language=str(language) if language is not None else None,
                    specialty=str(specialty) if specialty is not None else None,
                    errors=report.errors,
                    warnings=report.warnings,
                )
            )
        return summaries

    def load(self, case_id: str) -> dict[str, Any]:
        """Raw dict of one case file. Raises ``FileNotFoundError`` if absent."""
        path = self.path_for(case_id)
        if not path.is_file():
            raise FileNotFoundError(f"病例不存在: {case_id}")
        return _read_raw(path)

    def save(self, data: dict[str, Any], *, overwrite: bool = False) -> Path:
        """Atomically write a *pre-validated* normalized case dict.

        Steps: serialize first (so serialization failures touch nothing), write
        to a temp file in the same directory, fsync, then ``os.replace``. The
        temp file is removed on any failure — no partial case file can remain.

        Raises:
            PortalStorageError: bad case_id or write failure.
            CaseExistsError: target exists and ``overwrite`` is False.
        """
        case_id = str(data.get("case_id", ""))
        target = self.path_for(case_id)
        if target.exists() and not overwrite:
            raise CaseExistsError(
                f"病例 {case_id} 已存在;如确认覆盖请勾选“覆盖已有病例”后重新保存"
            )

        text = dump_yaml(data)  # may raise — happens before any file is touched

        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{case_id}.", suffix=".tmp", dir=self.case_dir
        )
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, target)
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            raise PortalStorageError(f"写入病例文件失败: {exc}") from exc
        logger.info("portal: saved case %s -> %s", case_id, target)
        return target
