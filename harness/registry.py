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
    """SQ1: agreement of local-model automated scores with faculty (ICC)."""

    inputs = [PROJECT_ROOT / "data" / "encounters", PROJECT_ROOT / "data" / "faculty_ratings.csv"]
    outputs = [PROJECT_ROOT / "results" / "phase_scoring_validity" / "icc.json"]
    seed = SEED

    def run(self) -> dict:
        import csv
        import json

        import numpy as np

        from harness.contracts.scoring_validity import check_scoring_validity_inputs
        from aivmt.metrics import icc

        check_scoring_validity_inputs(self.inputs[0], self.inputs[1])
        enc_dir, fac_csv = Path(self.inputs[0]), Path(self.inputs[1])

        # System overall per encounter (from saved encounter JSONs).
        system: dict[str, float] = {}
        for f in sorted(enc_dir.glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            system[d["encounter_id"]] = float(d["score"]["overall"])

        # Faculty overall per encounter (mean across raters).
        faculty: dict[str, list[float]] = {}
        with fac_csv.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row.get("overall"):
                    faculty.setdefault(row["encounter_id"], []).append(float(row["overall"]))

        ids = sorted(set(system) & {k for k, v in faculty.items() if v})
        if len(ids) < 2:
            raise AssertionError("need >=2 paired encounters for ICC")
        sys_scores = [system[i] for i in ids]
        fac_scores = [sum(faculty[i]) / len(faculty[i]) for i in ids]
        matrix = np.column_stack([sys_scores, fac_scores])
        result = {
            "n": len(ids),
            "icc2_1": icc(matrix, "icc2_1"),
            "icc2_k": icc(matrix, "icc2_k"),
        }
        out = Path(self.outputs[0])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    def benchmark(self) -> dict:
        # Real ICC once data exists. Until then, expose the machinery-verified fixture
        # (true-vs-shuffled ICC) so the evidence table is populated and reproducible.
        from harness.sanity.scoring_validity import check_shuffled_pairing_collapses_icc

        m = check_shuffled_pairing_collapses_icc(seed=self.seed)
        return {
            "status": "PENDING_REAL_DATA",
            "fixture_true_icc": round(m["true_icc"], 3),
            "fixture_shuffled_icc": round(m["shuffled_icc"], 3),
        }

    def sanity(self) -> List[Callable[[], dict]]:
        from harness.sanity.scoring_validity import check_shuffled_pairing_collapses_icc

        return [lambda: check_shuffled_pairing_collapses_icc(seed=self.seed)]
