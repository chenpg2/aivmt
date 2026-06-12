"""Phase registry — orchestration objects for tasks that produce paper numbers."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Type

from omegaconf import OmegaConf

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_seed() -> int:
    """Seed from configs/seed.yaml — never hardcoded in analysis code."""
    cfg = OmegaConf.load(PROJECT_ROOT / "configs" / "seed.yaml")
    return int(cfg.seed)  # type: ignore[attr-defined]


SEED: int = load_seed()
PHASE_REGISTRY: Dict[str, Type["Phase"]] = {}


def register_phase(name: str):
    """Class decorator registering a Phase under ``name``."""

    def decorator(cls: Type["Phase"]) -> Type["Phase"]:
        PHASE_REGISTRY[name] = cls
        return cls

    return decorator


class Phase:
    """A unit of work that produces evidence. Override run/benchmark/sanity."""

    inputs: List[Path] = []
    outputs: List[Path] = []
    seed: int = SEED

    def run(self) -> dict:  # pragma: no cover - overridden
        raise NotImplementedError

    def benchmark(self) -> dict:
        """Flat metric dict for the evidence table (no nesting)."""
        return {}

    def sanity(self) -> List[Callable[[], dict]]:
        """Negative controls — each must FAIL when the effect is absent."""
        return []

    def inputs_exist(self) -> bool:
        return bool(self.inputs) and all(Path(p).exists() for p in self.inputs)


@register_phase("phase_scoring_validity")
class PhaseScoringValidity(Phase):
    """SQ1: validity of local-model automated scores vs faculty (full encounters x raters suite)."""

    inputs = [PROJECT_ROOT / "data" / "encounters", PROJECT_ROOT / "data" / "faculty_ratings.csv"]
    outputs = [PROJECT_ROOT / "results" / "phase_scoring_validity" / "validity_suite.json"]
    seed = SEED

    @staticmethod
    def _load_system_scores(enc_dir: Path) -> dict[str, dict[str, float]]:
        """Flatten each scored encounter into {encounter_id: {dimension: score}}."""
        import json

        from aivmt.metrics.validity import SEGUE_DOMAINS

        system: dict[str, dict[str, float]] = {}
        for f in sorted(enc_dir.glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            score = d["score"]
            row: dict[str, float] = {
                "overall": float(score["overall"]),
                "history_completion": float(score["history_completion"]),
                "reasoning": float(score["reasoning"]),
            }
            for dom in SEGUE_DOMAINS:
                row[dom] = float(score["segue"][dom])
            system[d["encounter_id"]] = row
        return system

    @staticmethod
    def _load_faculty_rows(fac_csv: Path) -> list[dict[str, object]]:
        import csv

        with fac_csv.open(encoding="utf-8") as fh:
            return [dict(row) for row in csv.DictReader(fh)]

    def run(self) -> dict:
        from harness.contracts.scoring_validity import check_scoring_validity_inputs
        from aivmt.metrics import run_validity_suite, write_validity_artifacts

        check_scoring_validity_inputs(self.inputs[0], self.inputs[1])
        system = self._load_system_scores(Path(self.inputs[0]))
        faculty_rows = self._load_faculty_rows(Path(self.inputs[1]))

        result = run_validity_suite(system, faculty_rows, seed=self.seed)
        write_validity_artifacts(result, Path(self.outputs[0]).parent)
        return result

    def benchmark(self) -> dict:
        # Real headline numbers once data exists; until then, the full-suite fixture cross-check
        # (true-vs-shuffled overall ICC) populates the evidence table reproducibly.
        from aivmt.metrics import headline_metrics
        from harness.sanity.scoring_validity import check_validity_suite_negative_control

        if self.inputs_exist():
            return {"status": "REAL_DATA", **headline_metrics(self.run())}

        m = check_validity_suite_negative_control(seed=self.seed)
        return {
            "status": "PENDING_REAL_DATA",
            "fixture_true_overall_icc": round(m["true_icc"], 3),
            "fixture_shuffled_overall_icc": round(m["shuffled_icc"], 3),
        }

    def sanity(self) -> List[Callable[[], dict]]:
        from harness.sanity.scoring_validity import (
            check_shuffled_pairing_collapses_icc,
            check_validity_suite_negative_control,
        )

        return [
            lambda: check_shuffled_pairing_collapses_icc(seed=self.seed),
            lambda: check_validity_suite_negative_control(seed=self.seed),
        ]
