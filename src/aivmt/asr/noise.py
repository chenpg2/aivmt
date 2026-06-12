"""Deterministic ASR-noise corruption model for zh transcripts (CER-targeted).

The real AIVMT device has NO hardware AEC, so the transcript the scorer reads is degraded by TTS
echo + far-field zh ASR error. This module simulates that degradation DETERMINISTICALLY: given a
``(transcript, target_wer, seed)`` it applies the taxonomy operators from :mod:`.operators` to the
PATIENT/STUDENT utterance text until the measured corruption reaches an approximate target rate,
preserving the :class:`~aivmt.schemas.Transcript` structure (speakers, turns, telemetry, ids).

We target CHARACTER ERROR RATE (CER), the standard severity metric for Chinese ASR (no orthographic
word boundaries), and expose ``measured_cer``. A whitespace-token WER (``measured_wer``) is provided
for English/spaced text; for zh it degenerates to a token-as-line measure, so CER is the operating
metric and that choice is stated in the report.

Fail-loud invariants (AI4S — no silent fallback):
  - ``target_wer`` must lie in [0, 1]; otherwise :class:`ValueError`.
  - the transcript must have >=1 turn with non-empty corruptible text; otherwise :class:`ValueError`.
  - ``target_wer == 0`` is the IDENTITY path (byte-for-byte equal transcript, CER exactly 0).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Sequence

import numpy as np

from ..schemas import Speaker, Transcript, Turn
from .confusion import ConfusionTable, load_confusion_table
from .operators import CorruptionOperator, default_operators

logger = logging.getLogger(__name__)

#: Speakers whose utterance text the simulator may corrupt (the ASR-transcribed human turns).
#: Both student and patient turns pass through the same un-AEC microphone, so both are corrupted.
CORRUPTIBLE_SPEAKERS: tuple[Speaker, ...] = ("student", "patient")

#: Safety cap on operator applications per call (target may be unreachable on short/clean text).
_MAX_ITERS_FACTOR = 8


@dataclass(frozen=True)
class AsrNoiseConfig:
    """Immutable configuration for one corruption run.

    ``negation_bias`` controls how often function-word deletion prefers a polarity-flipping 不/没/无.
    ``scramble`` is the negative-control switch: when True the driver replaces every corruptible
    character via the confusion maps where possible (a catastrophic ceiling), collapsing downstream
    validity — used by the sanity control, never in a reported operating point.
    """

    target_wer: float
    seed: int
    negation_bias: float = 0.5
    scramble: bool = False


def _levenshtein(a: str, b: str) -> int:
    """Character-level edit distance (substitution/insertion/deletion all cost 1)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def measured_cer(original: str, corrupted: str) -> float:
    """Character Error Rate = edit_distance(original, corrupted) / len(original).

    ``len(original) == 0`` raises (an empty reference has no defined CER). This is the operating
    metric for zh (no word boundaries), and is also what the harness curve is anchored on.
    """
    if len(original) == 0:
        raise ValueError("measured_cer: empty reference string has no defined CER")
    return _levenshtein(original, corrupted) / len(original)


def _tokens(text: str) -> list[str]:
    """Whitespace tokens; for unspaced zh this yields one token per run, so CER is preferred there."""
    return text.split()


def measured_wer(original: str, corrupted: str) -> float:
    """Word Error Rate over whitespace tokens (meaningful for spaced/English text).

    For unspaced Chinese this collapses (each line is one token), so callers should use
    :func:`measured_cer` for zh; we expose WER for completeness and English transcripts.
    ``len(tokens(original)) == 0`` raises.
    """
    ref = _tokens(original)
    if not ref:
        raise ValueError("measured_wer: empty reference (no tokens) has no defined WER")
    hyp = _tokens(corrupted)
    return _token_levenshtein(ref, hyp) / len(ref)


def _token_levenshtein(a: Sequence[str], b: Sequence[str]) -> int:
    if list(a) == list(b):
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def transcript_cer(original: Transcript, corrupted: Transcript) -> float:
    """Aggregate CER over all corruptible turns (concatenate references, sum edit distances)."""
    ref_chars = 0
    edits = 0
    for o, c in zip(original.turns, corrupted.turns):
        if o.speaker not in CORRUPTIBLE_SPEAKERS:
            continue
        ref_chars += len(o.text)
        edits += _levenshtein(o.text, c.text)
    if ref_chars == 0:
        raise ValueError("transcript_cer: no corruptible reference characters")
    return edits / ref_chars


#: Catastrophic-ceiling character shift for the scramble control: rotate every CJK ideograph by a
#: fixed offset in the Unicode CJK block so even un-mapped characters are corrupted. Purely a
#: negative control (never a reported operating point), it guarantees CER -> ~1 so ICC collapses.
_CJK_LO = 0x4E00
_CJK_HI = 0x9FA5
_SCRAMBLE_SHIFT = 1


def _scramble_char(ch: str, subs: dict[str, str]) -> str:
    """Confusion-map the char if possible, else rotate a CJK ideograph by a fixed offset."""
    if ch in subs:
        return subs[ch]
    code = ord(ch)
    if _CJK_LO <= code <= _CJK_HI:
        shifted = _CJK_LO + (code - _CJK_LO + _SCRAMBLE_SHIFT) % (_CJK_HI - _CJK_LO + 1)
        return chr(shifted)
    return ch


def _scramble_text(text: str, table: ConfusionTable) -> str:
    """Negative-control ceiling: corrupt EVERY character (confusion map first, CJK rotation else).

    This is the 'scramble everything' control: it drives CER toward 1 so the downstream ICC-vs-gold
    collapses toward 0, proving the curve responds to corruption rather than being inert.
    """
    subs = dict(table.char_substitutions)
    return "".join(_scramble_char(ch, subs) for ch in text)


def _corrupt_text(
    text: str,
    operators: Sequence[CorruptionOperator],
    rng: np.random.Generator,
    target_edits: int,
) -> str:
    """Apply operators (cycled in fixed order) to ``text`` until ~``target_edits`` chars are edited.

    Operators that find no applicable site contribute 0 edits and are skipped; the loop stops early
    once the budget is met or after a bounded number of iterations (target may exceed what the
    confusion table can reach on a short string — that is reported as the achieved CER, never faked).
    """
    if target_edits <= 0 or not text:
        return text
    current = text
    edits_done = 0
    max_iters = max(len(text), 1) * _MAX_ITERS_FACTOR
    op_idx = 0
    for _ in range(max_iters):
        if edits_done >= target_edits:
            break
        op = operators[op_idx % len(operators)]
        op_idx += 1
        new_text, n = op.apply(current, rng)
        if n > 0:
            current = new_text
            edits_done += n
    return current


def corrupt(
    transcript: Transcript,
    target_wer: float,
    seed: int,
    *,
    table: ConfusionTable | None = None,
    config: AsrNoiseConfig | None = None,
) -> Transcript:
    """Return a deterministically-corrupted copy of ``transcript`` near CER == ``target_wer``.

    Only corruptible (student/patient) turn TEXT is altered; encounter id, case id, language,
    speakers, timings and telemetry are preserved. ``target_wer`` is interpreted as a CER target for
    zh (the metric is stated in the report). The result is reproducible: same ``(transcript,
    target_wer, seed)`` always yields the same transcript.

    Args:
        transcript: the clean transcript to degrade (must have >=1 corruptible non-empty turn).
        target_wer: desired corruption rate in [0, 1] (CER for zh). ``0`` is the identity path.
        seed: RNG seed (originates from ``configs/seed.yaml`` in callers — never hardcoded).
        table: optional pre-loaded confusion table (defaults to the synthetic repo table).
        config: optional full config; ``negation_bias``/``scramble`` come from here if supplied.

    Raises:
        ValueError: if ``target_wer`` is outside [0, 1] or the transcript has no corruptible text.
    """
    if not 0.0 <= target_wer <= 1.0:
        raise ValueError(f"target_wer must be in [0, 1], got {target_wer}")

    cfg = config or AsrNoiseConfig(target_wer=target_wer, seed=seed)
    tbl = table if table is not None else load_confusion_table()
    operators = default_operators(tbl, negation_bias=cfg.negation_bias)

    corruptible = [t for t in transcript.turns if t.speaker in CORRUPTIBLE_SPEAKERS and t.text]
    if not corruptible:
        raise ValueError("corrupt: transcript has no corruptible (non-empty student/patient) turns")

    # Identity fast-path: target 0 reproduces the clean transcript EXACTLY (CER guaranteed 0.0).
    if target_wer == 0.0 and not cfg.scramble:
        return transcript

    rng = np.random.default_rng(seed)
    new_turns: list[Turn] = []
    for turn in transcript.turns:
        if turn.speaker not in CORRUPTIBLE_SPEAKERS or not turn.text:
            new_turns.append(turn)
            continue
        if cfg.scramble:
            new_text = _scramble_text(turn.text, tbl)
        else:
            target_edits = int(round(target_wer * len(turn.text)))
            new_text = _corrupt_text(turn.text, operators, rng, target_edits)
        new_turns.append(replace(turn, text=new_text))

    corrupted = replace(transcript, turns=tuple(new_turns))
    achieved = transcript_cer(transcript, corrupted)
    logger.debug(
        "corrupt(target=%.3f seed=%d scramble=%s) -> achieved CER=%.3f",
        target_wer, seed, cfg.scramble, achieved,
    )
    return corrupted


__all__ = [
    "AsrNoiseConfig",
    "CORRUPTIBLE_SPEAKERS",
    "corrupt",
    "measured_cer",
    "measured_wer",
    "transcript_cer",
]
