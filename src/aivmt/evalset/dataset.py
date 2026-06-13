"""Aggregate the per-case generator into the full zh OB/GYN eval set + (de)serialize it.

The eval set is the union of :func:`aivmt.evalset.generator.generate_for_case`
over the three collaborator-reviewed zh OB/GYN cases. Each transcript is written
as one self-contained JSON file (``encounter_id``, ``case_id``, ``language``,
``turns``, ``provenance='synthetic'``, ``designed_quality``) into
``data/eval_transcripts/`` — the directory the Stream-A blinded faculty tool
serves. ``designed_quality`` is persisted for validation/audit; the faculty tool
MUST NOT surface it.

All clinical content originates in the case YAMLs (see
:mod:`aivmt.evalset.grounding`); ``provenance`` is hard-set to ``"synthetic"`` on
every record so neither a reader nor a downstream contract mistakes the apparatus
for real patient data.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Sequence, Union

from ..case_schema import ClinicalCase, load_clinical_case
from ..schemas import Transcript, Turn
from .generator import GeneratedTranscript, generate_for_case

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

__all__ = [
    "OBGYN_CASE_FILES",
    "PROVENANCE",
    "default_case_dir",
    "default_eval_dir",
    "load_obgyn_cases",
    "build_eval_set",
    "eval_transcript_to_dict",
    "write_eval_set",
    "load_eval_transcript",
    "load_eval_set",
]

#: The three zh OB/GYN case files this eval set is grounded in (stems under conf/case).
OBGYN_CASE_FILES: tuple[str, ...] = (
    "obgyn_ectopic_zh_01.yaml",
    "obgyn_aub_zh_01.yaml",
    "obgyn_vaginitis_zh_01.yaml",
)

#: Provenance tag stamped on every generated record. The set is synthetic apparatus.
PROVENANCE = "synthetic"

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def default_case_dir() -> Path:
    """The repo's case directory (``conf/case``)."""
    return _PROJECT_ROOT / "conf" / "case"


def default_eval_dir() -> Path:
    """The default output directory for the generated (blinded) eval transcripts."""
    return _PROJECT_ROOT / "data" / "eval_transcripts"


def default_keys_dir() -> Path:
    """The default directory for the answer-key sidecars (NOT served to raters).

    The designed-quality / covered-item answer key lives here, separate from the served transcript
    dir, so a rater cannot de-blind by opening a transcript file on disk — blinding is structural,
    not just enforced at the API layer.
    """
    return _PROJECT_ROOT / "data" / "eval_keys"


def load_obgyn_cases(case_dir: PathLike | None = None) -> list[ClinicalCase]:
    """Load the three zh OB/GYN structured cases (validated) in declared order."""
    base = Path(case_dir) if case_dir is not None else default_case_dir()
    cases: list[ClinicalCase] = []
    for name in OBGYN_CASE_FILES:
        path = base / name
        if not path.is_file():
            raise FileNotFoundError(f"OB/GYN case file missing: {path}")
        cases.append(load_clinical_case(path))
    return cases


def build_eval_set(
    cases: Sequence[ClinicalCase],
    *,
    seed: int,
    per_case: int,
) -> list[GeneratedTranscript]:
    """Generate ``per_case`` graded transcripts for each case (deterministic, ordered)."""
    out: list[GeneratedTranscript] = []
    for case in cases:
        out.extend(generate_for_case(case, seed=seed, n_transcripts=per_case))
    logger.info(
        "eval set built: %d transcripts over %d cases (per_case=%d, seed=%d)",
        len(out), len(cases), per_case, seed,
    )
    return out


def eval_transcript_to_dict(generated: GeneratedTranscript) -> dict:
    """Serialize one transcript to a BLINDED dict (no answer key — safe to serve to raters).

    The designed-quality / covered-item answer key is written separately by
    :func:`eval_key_to_dict`; keeping it out of the served file means a rater cannot de-blind by
    opening the transcript JSON on disk.
    """
    tx: Transcript = generated.transcript
    return {
        "encounter_id": tx.encounter_id,
        "case_id": tx.case_id,
        "language": tx.language,
        "provenance": PROVENANCE,
        "turns": [{"speaker": t.speaker, "text": t.text} for t in tx.turns],
    }


def eval_key_to_dict(generated: GeneratedTranscript) -> dict:
    """Serialize one transcript's answer key (designed quality + covered items) — NOT served."""
    return {
        "encounter_id": generated.transcript.encounter_id,
        "designed_quality": generated.designed_quality,
        "covered_item_ids": list(generated.covered_item_ids),
    }


def _atomic_write_json(data: dict, path: Path) -> None:
    """Write ``data`` as UTF-8 JSON atomically (temp file + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def write_eval_set(
    dataset: Sequence[GeneratedTranscript],
    out_dir: PathLike,
    keys_dir: PathLike | None = None,
) -> list[Path]:
    """Write blinded transcripts to ``out_dir`` and the answer keys to ``keys_dir`` (atomic per file).

    ``keys_dir`` defaults to :func:`default_keys_dir`. The served transcript files carry NO answer
    key, so the served directory can be shared with raters without de-blinding risk.
    """
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)
    keys = Path(keys_dir) if keys_dir is not None else default_keys_dir()
    keys.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for generated in dataset:
        eid = generated.transcript.encounter_id
        path = base / f"{eid}.json"
        _atomic_write_json(eval_transcript_to_dict(generated), path)
        _atomic_write_json(eval_key_to_dict(generated), keys / f"{eid}.json")
        written.append(path)
    logger.info("eval set written: %d blinded transcripts -> %s (keys -> %s)", len(written), base, keys)
    return written


def load_eval_transcript(path: PathLike, keys_dir: PathLike | None = None) -> tuple[Transcript, float]:
    """Load one eval transcript into ``(Transcript, designed_quality)``.

    The transcript is read from ``path`` (blinded, no key); the designed quality is read from the
    answer-key sidecar in ``keys_dir`` (default :func:`default_keys_dir`).

    Raises:
        ValueError: if provenance is not the synthetic apparatus tag (fail-loud: the scoring path
            must never ingest non-synthetic data).
        FileNotFoundError: if the answer-key sidecar for this encounter is missing.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    provenance = data.get("provenance")
    if provenance != PROVENANCE:
        raise ValueError(
            f"{path}: provenance must be {PROVENANCE!r} (got {provenance!r}); "
            "this loader only serves synthetic apparatus"
        )
    turns = tuple(Turn(speaker=t["speaker"], text=t["text"]) for t in data["turns"])
    transcript = Transcript(
        encounter_id=data["encounter_id"],
        case_id=data["case_id"],
        language=data["language"],
        turns=turns,
    )
    keys = Path(keys_dir) if keys_dir is not None else default_keys_dir()
    key_path = keys / f"{transcript.encounter_id}.json"
    if not key_path.exists():
        raise FileNotFoundError(
            f"answer-key sidecar missing for {transcript.encounter_id}: {key_path} "
            "(regenerate the eval set with scripts/build_eval_set.py)"
        )
    key = json.loads(key_path.read_text(encoding="utf-8"))
    return transcript, float(key["designed_quality"])


def load_eval_set(
    eval_dir: PathLike, keys_dir: PathLike | None = None
) -> list[tuple[Transcript, float]]:
    """Load every ``*.json`` in ``eval_dir`` (sorted) into ``(Transcript, designed_quality)`` pairs."""
    base = Path(eval_dir)
    files = sorted(base.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"no eval transcripts in {base}")
    return [load_eval_transcript(f, keys_dir) for f in files]
