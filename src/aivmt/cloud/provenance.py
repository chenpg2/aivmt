"""Structural PHI guard for the local-vs-cloud comparison.

The cloud head-to-head sends transcripts to a third-party endpoint (DeepSeek / DashScope / OpenAI).
Under the ABSOLUTE PHI RULE, ONLY synthetic or de-identified transcripts may ever leave the device.
This module makes that rule *structural* rather than a runtime convention:

  1. THE ACTIVE GUARD (type gate). Every cloud-bound transcript travels inside a
     :class:`CloudSafeDataset` whose provenance is stamped at construction. The only public
     constructors here (``synthetic_cloud_dataset`` and ``deidentified_cloud_dataset``) require the
     caller to assert, in code, that the data is off-device safe. There is no constructor that yields
     a cloud-safe dataset from a real-data file, and :func:`compare_local_vs_cloud` accepts ONLY this
     type — a raw transcript list (which could originate from real data) is refused. This is what
     keeps PHI off the wire today.
  2. DEFENSE-IN-DEPTH (path guard, not yet wired). :func:`assert_path_is_offdevice_safe` hard-refuses
     any path that resolves inside the real-data directories (``data/transcripts`` /
     ``data/encounters``, case-insensitively). The runner has no real-data file-loading path today,
     so this check is exercised by the sanity control and tests only; it is the seam a FUTURE
     real-data / ``--transcripts-dir`` run must route through before transmitting, so that run fails
     loud here instead of leaking PHI.

No silent fallback: a violation raises :class:`PhiLeakError`; nothing is sanitized or dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Union

from ..robustness import GoldedTranscript, build_golded_dataset
from ..schemas import Case
from ..utils import get_logger

logger = get_logger(__name__)

PathLike = Union[str, Path]

#: Directories that hold REAL (de-identified study) encounters/transcripts. Nothing sourced from
#: here may be sent to a cloud endpoint by this lane. Matched by path *containment* (any depth), so
#: ``data/transcripts/SMOKE01.json`` and ``.../data/encounters/x/y.json`` both trip the guard.
REAL_DATA_DIRS: tuple[str, ...] = ("data/transcripts", "data/encounters")

#: Provenance tags a cloud-safe dataset may carry. A real-data tag can never reach a cloud provider
#: because no constructor in this module produces a cloud-safe dataset from real data.
SYNTHETIC = "synthetic"
DEIDENTIFIED = "deidentified"
_CLOUD_SAFE_PROVENANCE: frozenset[str] = frozenset({SYNTHETIC, DEIDENTIFIED})


class PhiLeakError(RuntimeError):
    """Raised when the cloud path is asked to transmit data that is not provably off-device safe."""


@dataclass(frozen=True)
class CloudSafeDataset:
    """A golded transcript set whose provenance has been asserted off-device safe.

    Instances are produced only by :func:`synthetic_cloud_dataset` / :func:`deidentified_cloud_dataset`,
    so possession of a ``CloudSafeDataset`` is itself the proof the data may leave the device. The
    cloud compare function accepts ONLY this type; a raw ``Sequence[GoldedTranscript]`` is rejected.
    """

    provenance: str
    transcripts: tuple[GoldedTranscript, ...]
    source: str = "synthetic-fixture"

    def __post_init__(self) -> None:
        if self.provenance not in _CLOUD_SAFE_PROVENANCE:
            raise PhiLeakError(
                f"CloudSafeDataset provenance {self.provenance!r} is not cloud-safe; "
                f"allowed: {sorted(_CLOUD_SAFE_PROVENANCE)}"
            )
        if len(self.transcripts) < 2:
            raise ValueError("CloudSafeDataset needs >=2 transcripts (ICC requires n>=2 targets)")

    def __len__(self) -> int:
        return len(self.transcripts)


def _resolved_parts(path: Path) -> str:
    """POSIX-normalized resolved path, LOWERCASED, for case-insensitive containment checks.

    macOS's default filesystem is case-insensitive, so ``Data/Transcripts/x.json`` and
    ``data/transcripts/x.json`` name the SAME real-data file. Comparing in lowercase prevents a
    mixed-case path from slipping past a case-sensitive substring match.
    """
    return path.resolve().as_posix().lower()


def assert_path_is_offdevice_safe(path: PathLike) -> Path:
    """Defense-in-depth path guard: raise on any path that resolves inside a real-data directory.

    DEFENSE-IN-DEPTH, NOT YET ON AN ACTIVE CODE PATH. The wired structural guard that actually keeps
    PHI off the wire is the TYPE gate — the cloud compare function accepts ONLY a provenance-stamped
    :class:`CloudSafeDataset` (see :func:`assert_dataset_cloud_safe`), and there is no real-data
    file-loading path in the runner today. This function is the seam a FUTURE real-data /
    ``--transcripts-dir`` option must route through before transmitting; until that option exists it
    is exercised by the sanity control and tests only. Synthetic-fixture paths (anywhere outside the
    real-data dirs) pass through.

    The containment check is case-insensitive (lowercased resolved path) so a mixed-case real-data
    path (``Data/Transcripts/...``) cannot bypass it on a case-insensitive filesystem.

    Raises:
        PhiLeakError: if ``path`` resolves inside ``data/transcripts`` or ``data/encounters``
            (case-insensitively).
    """
    resolved = _resolved_parts(Path(path))
    for real_dir in REAL_DATA_DIRS:
        real_dir_lc = real_dir.lower()
        needle = f"/{real_dir_lc}/"
        if resolved.endswith(f"/{real_dir_lc}") or needle in resolved:
            raise PhiLeakError(
                f"PHI GUARD: refusing to send {path!r} to a cloud provider — it resolves inside the "
                f"real-data directory '{real_dir}'. Only synthetic/de-identified transcripts may "
                "leave the device. (See src/aivmt/cloud/provenance.py.)"
            )
    return Path(path)


def assert_dataset_cloud_safe(dataset: object) -> CloudSafeDataset:
    """Refuse anything that is not a provenance-stamped :class:`CloudSafeDataset`.

    Passing a bare ``list``/``tuple`` of ``GoldedTranscript`` (e.g. straight from
    ``build_golded_dataset`` or a real-data loader) is rejected: the cloud path demands the explicit
    off-device-safe assertion that only the synthetic/de-identified constructors can make.

    Raises:
        PhiLeakError: if ``dataset`` is not a cloud-safe, provenance-stamped dataset.
    """
    if not isinstance(dataset, CloudSafeDataset):
        raise PhiLeakError(
            "PHI GUARD: cloud comparison only accepts a CloudSafeDataset whose provenance was "
            "asserted off-device safe; got "
            f"{type(dataset).__name__}. Wrap synthetic data via synthetic_cloud_dataset(); a raw "
            "transcript list (which could originate from real data) is refused."
        )
    if dataset.provenance not in _CLOUD_SAFE_PROVENANCE:  # defensive: frozen dc already enforces
        raise PhiLeakError(f"dataset provenance {dataset.provenance!r} is not cloud-safe")
    return dataset


def synthetic_cloud_dataset(case: Case, n_transcripts: int) -> CloudSafeDataset:
    """Build the SAME designed synthetic golded set the other lanes use, stamped cloud-safe.

    Reuses :func:`aivmt.robustness.build_golded_dataset` so the cloud head-to-head scores byte-for-byte
    the identical transcripts as the local model — the comparison is therefore apples-to-apples.
    The transcripts are invented fixtures (no patient data), so they are off-device safe by
    construction; this is the only place that off-device assertion is made for synthetic data.
    """
    transcripts = tuple(build_golded_dataset(case, n_transcripts))
    logger.info(
        "built synthetic cloud-safe dataset: n=%d case=%s (off-device transmission permitted)",
        len(transcripts), case.case_id,
    )
    return CloudSafeDataset(provenance=SYNTHETIC, transcripts=transcripts, source="synthetic-fixture")


def deidentified_cloud_dataset(
    transcripts: Sequence[GoldedTranscript], *, source: str
) -> CloudSafeDataset:
    """Wrap an ALREADY de-identified transcript set as cloud-safe (caller asserts de-identification).

    This is the deliberate, auditable seam a future real-data comparison must pass through: the
    caller takes explicit responsibility that ``transcripts`` carry no PHI (de-identified upstream).
    It does NOT load from disk. A future real-data loader feeding this constructor would additionally
    route its source paths through :func:`assert_path_is_offdevice_safe` (defense-in-depth) so a
    ``data/transcripts``/``data/encounters`` path fails loud before any byte is read.
    """
    return CloudSafeDataset(
        provenance=DEIDENTIFIED, transcripts=tuple(transcripts), source=source
    )


__all__ = [
    "PhiLeakError",
    "CloudSafeDataset",
    "REAL_DATA_DIRS",
    "SYNTHETIC",
    "DEIDENTIFIED",
    "assert_path_is_offdevice_safe",
    "assert_dataset_cloud_safe",
    "synthetic_cloud_dataset",
    "deidentified_cloud_dataset",
]
