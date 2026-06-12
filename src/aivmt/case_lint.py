"""Validate every standardized-patient case YAML against the formal schema.

Run as:  ``uv run python -m aivmt.case_lint conf/case``

Exit codes (fail-loud):

* schema violations (bad/missing structural fields, wrong types) -> **ERROR**, exit 1,
* required clinical fields left as the ``TODO_COLLAB`` placeholder -> **WARNING**, exit 0.

This separation lets unfinished-but-structurally-valid cases ship for collaborative
authoring while hard schema breaks still fail the build.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from .case_schema import CaseValidationError, ClinicalCase, load_clinical_case

logger = logging.getLogger(__name__)

__all__ = ["LintReport", "lint_path", "main"]


@dataclass(frozen=True)
class LintReport:
    """Aggregated lint outcome over a set of case files."""

    n_files: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """True when there are no ERROR-level findings (warnings are allowed)."""
        return len(self.errors) == 0


def _iter_yaml(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.is_dir():
        raise FileNotFoundError(f"case_lint: path not found: {root}")
    return sorted(p for p in root.rglob("*.yaml"))


def _lint_one(path: Path) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a single case file."""
    try:
        case: ClinicalCase = load_clinical_case(path)
    except CaseValidationError as exc:
        return ([f"ERROR {exc}"], [])
    except (OSError, ValueError) as exc:  # YAML / OmegaConf parse problems
        return ([f"ERROR {path}: could not load — {exc}"], [])

    warnings = [
        f"WARN {path}:{field_path} — placeholder '{'TODO_COLLAB'}' awaiting collaborative authoring"
        for field_path in case.placeholder_paths()
    ]
    return ([], warnings)


def lint_path(root: Path) -> LintReport:
    """Validate every ``*.yaml`` under ``root`` (or a single file)."""
    files = _iter_yaml(root)
    errors: list[str] = []
    warnings: list[str] = []
    for path in files:
        errs, warns = _lint_one(path)
        errors.extend(errs)
        warnings.extend(warns)
    return LintReport(n_files=len(files), errors=tuple(errors), warnings=tuple(warnings))


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Lint standardized-patient case YAML files.")
    parser.add_argument("path", nargs="?", default="conf/case", help="case dir or single YAML file")
    args = parser.parse_args(argv)

    root = Path(args.path)
    try:
        report = lint_path(root)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    for warning in report.warnings:
        logger.warning("%s", warning)
    for error in report.errors:
        logger.error("%s", error)

    logger.info(
        "case_lint: %d file(s), %d error(s), %d warning(s) -> %s",
        report.n_files, len(report.errors), len(report.warnings),
        "PASS" if report.ok else "FAIL",
    )
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
