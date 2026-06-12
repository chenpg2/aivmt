"""SYNTHETIC golded transcripts for the robustness batch runner (NOT real patient data).

A small ladder of graded synthetic chest-pain encounters with a DESIGNED quality ordering (the
"gold"). The same caveat as the SQ1 pilot applies: this gold is constructed and partly correlated
with what the scorer measures, so the paraphrase ICC is an OPTIMISTIC stability probe, not the
validity claim. It exists so robustness can be measured offline (mock LLM) and on real models
without depending on faculty data. All text below is invented for illustration only.
"""

from __future__ import annotations

from typing import Sequence

from ..schemas import Case, Speaker, Telemetry, Transcript, Turn
from .core import GoldedTranscript

# SYNTHETIC graded encounters: (designed_gold, [(speaker, text), ...]). Invented, not real cases.
_TIERS: tuple[tuple[float, tuple[tuple[Speaker, str], ...]], ...] = (
    (
        0.20,
        (
            ("student", "What's wrong?"),
            ("patient", "My chest hurts."),
            ("student", "Okay, I'll get the doctor."),
        ),
    ),
    (
        0.45,
        (
            ("student", "What brings you in?"),
            ("patient", "Chest pain."),
            ("student", "When did it start?"),
            ("patient", "About two hours ago."),
        ),
    ),
    (
        0.65,
        (
            ("student", "Hi, what's the problem today?"),
            ("patient", "Chest pain."),
            ("student", "When did it start, what does it feel like, and does it spread?"),
            ("patient", "Two hours ago, crushing, goes to my left arm."),
            ("student", "It might be a heart problem; I'll arrange tests."),
        ),
    ),
    (
        0.85,
        (
            ("student", "Hello, I'm a medical student. What brings you in today?"),
            ("patient", "Chest pain."),
            ("student", "When did it start, what's it like, does it radiate, any sweating?"),
            ("patient", "Two hours ago, crushing, to the left arm, with sweating."),
            ("student", "Do you have high blood pressure or diabetes, or smoke?"),
            ("patient", "Hypertension, and I smoke."),
            ("student", "I'm concerned about acute coronary syndrome and will order an ECG and troponin."),
        ),
    ),
)


def build_golded_dataset(case: Case, n_transcripts: int) -> list[GoldedTranscript]:
    """Return up to ``n_transcripts`` SYNTHETIC golded transcripts cycling the graded tiers.

    Transcripts are made distinct by appending a deterministic ``(case i)`` marker to the opening
    turn (no randomness — same ``n_transcripts`` always yields the same dataset).

    Raises:
        ValueError: if ``n_transcripts < 2`` (ICC needs >=2 targets).
    """
    if n_transcripts < 2:
        raise ValueError("build_golded_dataset needs n_transcripts >= 2 (ICC requires n>=2 targets)")
    dataset: list[GoldedTranscript] = []
    for i in range(n_transcripts):
        gold, turns = _TIERS[i % len(_TIERS)]
        tt = list(turns)
        tt[0] = (tt[0][0], f"{tt[0][1]} (case {i})")
        transcript = Transcript(
            encounter_id=f"syn_rob_{i:03d}",
            case_id=case.case_id,
            language=case.language,
            turns=tuple(Turn(s, x) for s, x in tt),
            telemetry=Telemetry(),
        )
        dataset.append((transcript, float(gold)))
    return dataset


def transcripts_only(dataset: Sequence[GoldedTranscript]) -> list[Transcript]:
    """Drop the gold column (test-retest does not need it)."""
    return [t for t, _ in dataset]
