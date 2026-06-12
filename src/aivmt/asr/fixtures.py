"""SYNTHETIC zh golded transcripts for the ASR-degradation curve (NOT real patient data).

A small ladder of graded synthetic Chinese history-taking encounters with a DESIGNED quality
ordering (the "gold"). Unlike the English robustness fixture, these are zh so the confusion-table
operators actually bite — letting the curve and its negative controls demonstrate genuine
ICC degradation as CER rises. Every line is invented for illustration only; the same caveat as the
SQ1 pilot applies (the gold is constructed and partly correlated with what a scorer measures, so the
clean ICC is an OPTIMISTIC anchor, not the validity claim).
"""

from __future__ import annotations

from typing import Sequence

from ..robustness import GoldedTranscript
from ..schemas import Case, Speaker, Telemetry, Transcript, Turn

# SYNTHETIC graded zh encounters: (designed_gold, [(speaker, text), ...]). Invented, not real cases.
_TIERS: tuple[tuple[float, tuple[tuple[Speaker, str], ...]], ...] = (
    (
        0.20,
        (
            ("student", "哪里不舒服"),
            ("patient", "肚子疼"),
            ("student", "好的我去叫医生"),
        ),
    ),
    (
        0.45,
        (
            ("student", "您今天哪里不舒服来的"),
            ("patient", "我腹痛"),
            ("student", "什么时候开始的疼"),
            ("patient", "昨天开始疼的"),
        ),
    ),
    (
        0.65,
        (
            ("student", "您好今天什么不舒服"),
            ("patient", "我腹痛还有阴道流血"),
            ("student", "疼了多久末次月经什么时候有没有头晕"),
            ("patient", "疼了一天末次月经六周前站起来头晕"),
            ("student", "我担心是宫外孕需要检查"),
        ),
    ),
    (
        0.85,
        (
            ("student", "您好我是医学生今天什么不舒服来的"),
            ("patient", "我右下腹痛还有阴道流血"),
            ("student", "疼了多久末次月经什么时候有没有头晕坠胀"),
            ("patient", "疼了一整天末次月经六周前站起来头晕肛门坠胀"),
            ("student", "您有没有高血压糖尿病做过手术吗"),
            ("patient", "没有高血压也没有糖尿病"),
            ("student", "我高度怀疑异位妊娠需要立刻做超声和血检"),
        ),
    ),
)


def build_zh_golded_dataset(case: Case, n_transcripts: int) -> list[GoldedTranscript]:
    """Return up to ``n_transcripts`` SYNTHETIC zh golded transcripts cycling the graded tiers.

    Transcripts are made distinct by appending a deterministic ``(case i)`` marker to the opening
    turn (no randomness — same ``n_transcripts`` always yields the same dataset).

    Raises:
        ValueError: if ``n_transcripts < 2`` (ICC needs >=2 targets).
    """
    if n_transcripts < 2:
        raise ValueError("build_zh_golded_dataset needs n_transcripts >= 2 (ICC requires n>=2)")
    dataset: list[GoldedTranscript] = []
    for i in range(n_transcripts):
        gold, turns = _TIERS[i % len(_TIERS)]
        tt = list(turns)
        tt[0] = (tt[0][0], f"{tt[0][1]} case{i}")
        transcript = Transcript(
            encounter_id=f"syn_asr_{i:03d}",
            case_id=case.case_id,
            language="zh",
            turns=tuple(Turn(s, x) for s, x in tt),
            telemetry=Telemetry(),
        )
        dataset.append((transcript, float(gold)))
    return dataset


def zh_transcripts_only(dataset: Sequence[GoldedTranscript]) -> list[Transcript]:
    """Drop the gold column."""
    return [t for t, _ in dataset]


__all__ = ["build_zh_golded_dataset", "zh_transcripts_only"]
