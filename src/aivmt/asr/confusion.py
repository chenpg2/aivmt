"""SYNTHETIC Chinese ASR confusion tables for the deterministic noise model.

The character/term mappings live in ``data/asr_confusion_zh.json`` (clearly labelled synthetic).
This module loads and freezes them into an immutable :class:`ConfusionTable` so the corruption
operators have a single, deterministic source of substitution targets. The table is NOT an
empirical lexicon — each mapping is a structurally-motivated, hand-authored example of a published
Chinese-ASR error mechanism (pinyin homophone, tone confusion, OOV medical-entity fallback,
function-word deletion, ITN number/unit error, segmentation boundary shift).

Fail-loud: a missing/malformed data file raises instead of silently degrading to an empty table.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

logger = logging.getLogger(__name__)

#: Default location of the synthetic confusion-table data file (repo-relative).
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFUSION_PATH = _PROJECT_ROOT / "data" / "asr_confusion_zh.json"


class ConfusionTableError(RuntimeError):
    """The confusion-table data file is missing or structurally malformed (fail loud)."""


@dataclass(frozen=True)
class ConfusionTable:
    """Frozen, validated Chinese ASR confusion mappings.

    All maps are character/term -> wrong character/term. ``deletable`` and ``negation`` are the sets
    of acoustically-weak function words an operator may delete (negation deletion flips polarity).
    Length is preserved by every substitution map (each key replaced by an equal-character-count
    value where structurally possible) so character-level CER bookkeeping stays interpretable.
    """

    homophone: Mapping[str, str]
    tone: Mapping[str, str]
    medical_term: Mapping[str, str]
    number_unit: Mapping[str, str]
    segmentation: Mapping[str, str]
    deletable: tuple[str, ...]
    negation: tuple[str, ...]

    @property
    def char_substitutions(self) -> dict[str, str]:
        """Single-character substitution maps merged (homophone + tone) for the char-level operator."""
        merged: dict[str, str] = {}
        merged.update(self.homophone)
        merged.update(self.tone)
        return merged


def _require_str_map(raw: object, ctx: str) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ConfusionTableError(f"{ctx}: expected an object, got {type(raw).__name__}")
    out: dict[str, str] = {}
    for k, v in raw.items():
        if k.startswith("_"):  # documentation keys (e.g. "_doc") are skipped, not data
            continue
        if not isinstance(k, str) or not isinstance(v, str):
            raise ConfusionTableError(f"{ctx}: non-string mapping {k!r} -> {v!r}")
        if k == v:
            raise ConfusionTableError(f"{ctx}: identity mapping {k!r} -> {v!r} (would not corrupt)")
        out[k] = v
    return out


def load_confusion_table(path: Path | str | None = None) -> ConfusionTable:
    """Load + validate the synthetic confusion table.

    Raises:
        ConfusionTableError: if the file is absent, not JSON, or missing a required section.
    """
    p = Path(path) if path is not None else DEFAULT_CONFUSION_PATH
    if not p.is_file():
        raise ConfusionTableError(f"confusion table missing: {p}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfusionTableError(f"confusion table is not valid JSON ({p}): {exc}") from exc

    for section in ("homophone", "tone", "medical_term", "number_unit", "segmentation",
                    "function_words"):
        if section not in raw:
            raise ConfusionTableError(f"confusion table missing section '{section}' ({p})")

    fw = raw["function_words"]
    deletable = tuple(fw.get("deletable", ()))
    negation = tuple(fw.get("negation", ()))
    if not deletable or not negation:
        raise ConfusionTableError(f"function_words must list non-empty 'deletable' and 'negation' ({p})")

    table = ConfusionTable(
        homophone=_require_str_map(raw["homophone"], "homophone"),
        tone=_require_str_map(raw["tone"], "tone"),
        medical_term=_require_str_map(raw["medical_term"], "medical_term"),
        number_unit=_require_str_map(raw["number_unit"], "number_unit"),
        segmentation=_require_str_map(raw["segmentation"], "segmentation"),
        deletable=deletable,
        negation=negation,
    )
    logger.debug(
        "loaded synthetic confusion table: %d char-subs, %d medical terms, %d deletable words",
        len(table.char_substitutions), len(table.medical_term), len(table.deletable),
    )
    return table


__all__ = [
    "ConfusionTable",
    "ConfusionTableError",
    "DEFAULT_CONFUSION_PATH",
    "load_confusion_table",
]
