"""Composable, deterministic character-level corruption operators for zh ASR-noise simulation.

Each operator implements the :class:`CorruptionOperator` protocol: given the source text and a
seeded ``numpy`` RNG, it returns a corrupted string plus the number of character-level edits it
introduced (substitutions/deletions/insertions). The edit count lets the driver in ``noise.py``
titrate corruption toward a target CER without re-aligning after every step.

Operators model the published Chinese-ASR error taxonomy:
  - :class:`HomophoneToneOperator`   — pinyin-homophone + tone-confusion substitution (1->1 char)
  - :class:`MedicalTermOperator`     — OOV medical-entity mis-recognition (multi-char term swap)
  - :class:`SegmentationOperator`    — word-boundary / compound mis-segmentation (compound swap)
  - :class:`NumberUnitOperator`      — ITN duration/unit confusion (天->点 etc.)
  - :class:`FunctionWordDeletion`    — acoustically-weak 虚词 deletion (incl. polarity-flipping 不/没)
  - :class:`TtsEchoInsertion`        — no-AEC TTS-echo token insertion at an utterance boundary

All operators are pure given (text, rng): no global state, no I/O. Determinism is guaranteed by
threading a single seeded RNG through the driver, so ``corrupt(..., seed)`` is reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .confusion import ConfusionTable

#: A corruption returns (corrupted_text, n_char_edits_introduced).
Corruption = tuple[str, int]


class CorruptionOperator(Protocol):
    """One taxonomy-grounded corruption applied to a single utterance string."""

    @property
    def name(self) -> str:
        """Stable operator name (used for auditing / report rows)."""
        ...

    def apply(self, text: str, rng: np.random.Generator) -> Corruption:
        """Return (corrupted_text, n_char_edits). Must be pure given (text, rng)."""
        ...


def _substitute_one(text: str, mapping: dict[str, str], rng: np.random.Generator) -> Corruption:
    """Replace ONE randomly-chosen occurrence of a mapped key with its confusion target.

    Returns the original text + 0 edits if no key is present (the driver then moves on — it never
    fabricates an edit). The number of edits equals the character length of the replacement (a
    multi-char term swap counts each changed position).
    """
    candidates = [i for i, ch in enumerate(text) if ch in mapping]
    if not candidates:
        return text, 0
    pos = int(rng.choice(candidates))
    src = text[pos]
    dst = mapping[src]
    corrupted = text[:pos] + dst + text[pos + 1 :]
    # Edit cost: changed characters. Equal length -> substitutions; differing -> sub+indel.
    n_edits = max(len(dst), 1)
    return corrupted, n_edits


def _substitute_term(text: str, mapping: dict[str, str], rng: np.random.Generator) -> Corruption:
    """Replace ONE occurrence of a multi-character term key (longest-first to avoid partial hits)."""
    present = [k for k in mapping if k in text]
    if not present:
        return text, 0
    present.sort(key=len, reverse=True)
    # Deterministically pick among present terms via the RNG (stable given seed).
    key = present[int(rng.integers(0, len(present)))]
    idx = text.find(key)
    dst = mapping[key]
    corrupted = text[:idx] + dst + text[idx + len(key) :]
    # Each character position in the term may change; count the changed positions.
    n_edits = sum(1 for a, b in zip(key, dst.ljust(len(key))) if a != b) or 1
    return corrupted, n_edits


@dataclass(frozen=True)
class HomophoneToneOperator:
    """Pinyin-homophone + tone-confusion single-character substitution."""

    table: ConfusionTable
    name: str = "homophone_tone"

    def apply(self, text: str, rng: np.random.Generator) -> Corruption:
        return _substitute_one(text, dict(self.table.char_substitutions), rng)


@dataclass(frozen=True)
class MedicalTermOperator:
    """OOV medical-entity mis-recognition (multi-character term -> wrong term)."""

    table: ConfusionTable
    name: str = "medical_term"

    def apply(self, text: str, rng: np.random.Generator) -> Corruption:
        return _substitute_term(text, dict(self.table.medical_term), rng)


@dataclass(frozen=True)
class SegmentationOperator:
    """Word-boundary / compound mis-segmentation (compound -> wrong compound)."""

    table: ConfusionTable
    name: str = "segmentation"

    def apply(self, text: str, rng: np.random.Generator) -> Corruption:
        return _substitute_term(text, dict(self.table.segmentation), rng)


@dataclass(frozen=True)
class NumberUnitOperator:
    """ITN number/unit confusion (天->点, 周->州, ...)."""

    table: ConfusionTable
    name: str = "number_unit"

    def apply(self, text: str, rng: np.random.Generator) -> Corruption:
        single = {k: v for k, v in self.table.number_unit.items() if len(k) == 1}
        multi = {k: v for k, v in self.table.number_unit.items() if len(k) > 1}
        # Prefer multi-char unit terms when present, else single-char.
        out, edits = _substitute_term(text, multi, rng)
        if edits:
            return out, edits
        return _substitute_one(text, single, rng)


@dataclass(frozen=True)
class FunctionWordDeletion:
    """Delete ONE acoustically-weak function word; negation deletion flips clinical polarity.

    ``negation_bias`` in [0, 1] is the probability of preferring a negation word (不/没/无) when both
    a negation and an ordinary function word are present — modelling the clinically-severe polarity
    flip without making it the ONLY behaviour.
    """

    table: ConfusionTable
    negation_bias: float = 0.5
    name: str = "function_word_deletion"

    def apply(self, text: str, rng: np.random.Generator) -> Corruption:
        neg_positions = [i for i, ch in enumerate(text) if ch in self.table.negation]
        del_positions = [i for i, ch in enumerate(text) if ch in self.table.deletable]
        prefer_negation = bool(neg_positions) and (
            not del_positions or rng.random() < self.negation_bias
        )
        positions = neg_positions if prefer_negation else del_positions
        if not positions:
            return text, 0
        pos = int(rng.choice(positions))
        corrupted = text[:pos] + text[pos + 1 :]
        return corrupted, 1  # one deleted character == one edit


@dataclass(frozen=True)
class TtsEchoInsertion:
    """Insert a short TTS-echo fragment at the utterance start (no-AEC echo leakage).

    Models the un-flashed device re-transcribing fragments of its own TTS prompt into the patient
    turn. The fragment is drawn deterministically from a fixed synthetic prompt pool.
    """

    echo_pool: tuple[str, ...] = ("您好", "请描述", "您的症状", "好的", "请问")
    name: str = "tts_echo_insertion"

    def apply(self, text: str, rng: np.random.Generator) -> Corruption:
        frag = self.echo_pool[int(rng.integers(0, len(self.echo_pool)))]
        corrupted = frag + text
        return corrupted, len(frag)  # inserted characters == edits


def default_operators(table: ConfusionTable, negation_bias: float = 0.5) -> tuple[CorruptionOperator, ...]:
    """The standard taxonomy operator suite, in a fixed order (determinism + auditability)."""
    ops: list[CorruptionOperator] = [
        HomophoneToneOperator(table),
        MedicalTermOperator(table),
        SegmentationOperator(table),
        NumberUnitOperator(table),
        FunctionWordDeletion(table, negation_bias=negation_bias),
        TtsEchoInsertion(),
    ]
    return tuple(ops)


__all__ = [
    "Corruption",
    "CorruptionOperator",
    "HomophoneToneOperator",
    "MedicalTermOperator",
    "SegmentationOperator",
    "NumberUnitOperator",
    "FunctionWordDeletion",
    "TtsEchoInsertion",
    "default_operators",
]
