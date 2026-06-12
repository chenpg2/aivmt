"""Deterministic ASR-noise simulation for zh transcripts (SQ1 ASR-robustness lane).

The un-flashed AIVMT voice puck has no hardware AEC, so the transcript the scorer reads is degraded
by TTS echo + far-field Mandarin ASR error. This package simulates that degradation deterministically
so we can quantify how scorer validity (ICC vs gold) falls as Character Error Rate rises — turning
the device's missing AEC into a measured robustness result without flashing hardware.

Public surface:
  - :func:`corrupt` — degrade a :class:`~aivmt.schemas.Transcript` toward a target CER (seeded).
  - :func:`measured_cer` / :func:`measured_wer` / :func:`transcript_cer` — corruption metrics.
  - :class:`AsrNoiseConfig` — immutable run config (target, seed, negation bias, scramble control).
  - :func:`load_confusion_table` + :class:`ConfusionTable` — the SYNTHETIC confusion lexicon.
  - the taxonomy operators (homophone/tone, medical-term, segmentation, number/unit, deletion, echo).
"""

from __future__ import annotations

from .confusion import (
    ConfusionTable,
    ConfusionTableError,
    DEFAULT_CONFUSION_PATH,
    load_confusion_table,
)
from .curve import (
    DEFAULT_WER_LEVELS,
    AsrDegradationCurve,
    CurvePoint,
    compute_curve,
)
from .fixtures import build_zh_golded_dataset, zh_transcripts_only
from .report import render_markdown, write_curve_artifacts
from .noise import (
    CORRUPTIBLE_SPEAKERS,
    AsrNoiseConfig,
    corrupt,
    measured_cer,
    measured_wer,
    transcript_cer,
)
from .operators import (
    CorruptionOperator,
    FunctionWordDeletion,
    HomophoneToneOperator,
    MedicalTermOperator,
    NumberUnitOperator,
    SegmentationOperator,
    TtsEchoInsertion,
    default_operators,
)

__all__ = [
    # corruption driver + metrics
    "corrupt",
    "measured_cer",
    "measured_wer",
    "transcript_cer",
    "AsrNoiseConfig",
    "CORRUPTIBLE_SPEAKERS",
    # confusion table
    "ConfusionTable",
    "ConfusionTableError",
    "DEFAULT_CONFUSION_PATH",
    "load_confusion_table",
    # operators
    "CorruptionOperator",
    "HomophoneToneOperator",
    "MedicalTermOperator",
    "SegmentationOperator",
    "NumberUnitOperator",
    "FunctionWordDeletion",
    "TtsEchoInsertion",
    "default_operators",
    # degradation curve
    "compute_curve",
    "AsrDegradationCurve",
    "CurvePoint",
    "DEFAULT_WER_LEVELS",
    # report
    "render_markdown",
    "write_curve_artifacts",
    # synthetic zh fixtures
    "build_zh_golded_dataset",
    "zh_transcripts_only",
]
