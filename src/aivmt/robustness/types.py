"""Result dataclasses for the scorer-robustness analysis (immutable, JSON-serializable)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ParaphraseSensitivity:
    """Spread of ICC-vs-gold across semantics-preserving system-prompt paraphrases.

    A small ``icc_sd``/``icc_range`` means the scorer's output tracks the rubric, not the wording.
    ``per_paraphrase_icc`` keeps every cell so the result is auditable, not just summarized.
    """

    variant: str
    n_paraphrases: int
    n_transcripts: int
    per_paraphrase_icc: dict[str, float]
    icc_mean: float
    icc_sd: float
    icc_min: float
    icc_max: float
    icc_range: float


@dataclass(frozen=True)
class TestRetest:
    """Stochasticity / test-retest reliability of one scorer at one temperature.

    ``retest_icc`` is the ICC across the K repeated scorings (targets = encounters, raters =
    repeats) — at temp 0 a deterministic model gives identical repeats (degenerate variance ->
    ``nan``, reported explicitly, never silently coerced). ``mean_cv`` is the mean per-encounter
    coefficient of variation across repeats.
    """

    variant: str
    temperature: float
    n_repeats: int
    n_seeds: int
    n_transcripts: int
    retest_icc: float
    mean_cv: float
    degenerate: bool


@dataclass(frozen=True)
class RobustnessReport:
    """Top-level robustness result for one model x scorer-variant, ready to serialize."""

    model_id: str
    variant: str
    seed: int
    paraphrase: ParaphraseSensitivity
    test_retest: tuple[TestRetest, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return asdict(self)
