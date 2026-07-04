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

        # utf-8-sig tolerates the BOM that Excel's "CSV UTF-8" export prepends
        with fac_csv.open(encoding="utf-8-sig") as fh:
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


@register_phase("phase_robustness")
class PhaseRobustness(Phase):
    """SQ1 robustness: stability of local-model scores under prompt paraphrase + stochasticity.

    Real numbers come from the batch runner (``scripts/robustness.py``) which writes the artifact
    this phase validates and summarizes. Until that batch is run on real models the phase reports a
    seeded fixture cross-check (true-vs-shuffled test-retest ICC) so the evidence table is populated
    reproducibly and the negative controls still fire.
    """

    inputs = [PROJECT_ROOT / "results" / "phase_robustness" / "robustness.json"]
    outputs = [PROJECT_ROOT / "results" / "phase_robustness" / "robustness.json"]
    seed = SEED

    def run(self) -> dict:
        from harness.contracts.robustness import check_robustness_inputs

        check_robustness_inputs(self.inputs[0])
        import json

        return {"reports": json.loads(Path(self.inputs[0]).read_text(encoding="utf-8"))}

    def benchmark(self) -> dict:
        from harness.sanity.robustness import check_shuffled_repeats_collapse_retest_icc

        if self.inputs_exist():
            from harness.contracts.robustness import check_robustness_inputs

            check_robustness_inputs(self.inputs[0])
            return {"status": "COMPUTED", "artifact": str(self.inputs[0].name)}

        m = check_shuffled_repeats_collapse_retest_icc(seed=self.seed)
        return {
            "status": "PENDING_REAL_DATA",
            "fixture_true_retest_icc": round(m["true_icc"], 3),
            "fixture_shuffled_retest_icc": round(m["shuffled_icc"], 3),
        }

    def sanity(self) -> List[Callable[[], dict]]:
        from harness.sanity.robustness import (
            check_degenerate_input_is_nan_not_silent,
            check_shuffled_repeats_collapse_retest_icc,
        )

        return [
            lambda: check_shuffled_repeats_collapse_retest_icc(seed=self.seed),
            lambda: check_degenerate_input_is_nan_not_silent(seed=self.seed),
        ]


@register_phase("phase_asr_robustness")
class PhaseAsrRobustness(Phase):
    """SQ1 ASR-robustness: how scorer validity (ICC vs gold) degrades as ASR CER rises.

    The un-flashed AIVMT voice puck has no hardware AEC, so the transcript the scorer reads is
    corrupted by TTS echo + far-field zh ASR error. This phase quantifies the resulting validity loss
    as an ICC-degradation curve over CER in {0, 0.05, 0.15, 0.30}. Real numbers come from the batch
    runner (``scripts/asr_robustness.py``) which writes the artifact this phase validates. Until that
    batch runs on real models the phase reports a seeded fixture cross-check (clean-anchor ICC and the
    high-CER drop on the synthetic zh fixture) so the evidence table is populated reproducibly and the
    negative controls still fire.
    """

    inputs = [PROJECT_ROOT / "results" / "phase_asr_robustness" / "asr_robustness.json"]
    outputs = [PROJECT_ROOT / "results" / "phase_asr_robustness" / "asr_robustness.json"]
    seed = SEED

    def run(self) -> dict:
        from harness.contracts.asr_robustness import check_asr_robustness_inputs

        check_asr_robustness_inputs(self.inputs[0])
        import json

        return {"curves": json.loads(Path(self.inputs[0]).read_text(encoding="utf-8"))}

    def benchmark(self) -> dict:
        from harness.sanity.asr_robustness import check_degradation_is_monotone_ish

        if self.inputs_exist():
            from harness.contracts.asr_robustness import check_asr_robustness_inputs

            check_asr_robustness_inputs(self.inputs[0])
            return {"status": "COMPUTED", "artifact": str(self.inputs[0].name)}

        m = check_degradation_is_monotone_ish(seed=self.seed)
        return {
            "status": "PENDING_REAL_DATA",
            "fixture_clean_icc": round(m["clean_icc"], 3),
            "fixture_high_cer_icc": round(m["high_cer_icc"], 3),
            "fixture_icc_drop": round(m["drop"], 3),
        }

    def sanity(self) -> List[Callable[[], dict]]:
        from harness.sanity.asr_robustness import (
            check_clean_level_reproduces_anchor,
            check_degenerate_curve_point_is_nan_not_silent,
            check_degradation_is_monotone_ish,
            check_scramble_collapses_icc,
        )

        return [
            lambda: check_clean_level_reproduces_anchor(seed=self.seed),
            lambda: check_degradation_is_monotone_ish(seed=self.seed),
            lambda: check_scramble_collapses_icc(seed=self.seed),
            lambda: check_degenerate_curve_point_is_nan_not_silent(seed=self.seed),
        ]


@register_phase("phase_quant_frontier")
class PhaseQuantFrontier(Phase):
    """SQ3 edge-deployability: the validity-cost frontier over (model size x quant level).

    Answers "how small/cheap a model still scores at acceptable validity?" — per cell, ICC-vs-gold
    over the SAME designed synthetic golded set the robustness lane uses (so the lanes are directly
    comparable), plus JSON-parse/refusal robustness, per-encounter latency, loaded RAM/VRAM
    (``ollama ps``), and on-disk size (``ollama list``). Real numbers come from the batch runner
    (``scripts/quant_frontier.py``) which writes the artifact this phase validates and summarizes.
    Until that batch runs against the quant ladder the phase reports a seeded fixture cross-check
    (true-vs-shuffled-gold ICC) so the evidence table is populated reproducibly and the negative
    controls still fire.
    """

    inputs = [PROJECT_ROOT / "results" / "phase_quant_frontier" / "quant_frontier.json"]
    outputs = [PROJECT_ROOT / "results" / "phase_quant_frontier" / "quant_frontier.json"]
    seed = SEED

    def run(self) -> dict:
        from harness.contracts.quant_frontier import check_quant_frontier_inputs

        check_quant_frontier_inputs(self.inputs[0])
        import json

        return {"cells": json.loads(Path(self.inputs[0]).read_text(encoding="utf-8"))}

    def benchmark(self) -> dict:
        from harness.sanity.quant_frontier import check_shuffled_gold_collapses_icc

        if self.inputs_exist():
            from harness.contracts.quant_frontier import check_quant_frontier_inputs

            check_quant_frontier_inputs(self.inputs[0])
            return {"status": "COMPUTED", "artifact": str(self.inputs[0].name)}

        m = check_shuffled_gold_collapses_icc(seed=self.seed)
        return {
            "status": "PENDING_REAL_DATA",
            "fixture_true_icc": round(m["true_icc"], 3),
            "fixture_shuffled_icc": round(m["shuffled_icc"], 3),
        }

    def sanity(self) -> List[Callable[[], dict]]:
        from harness.sanity.quant_frontier import (
            check_degenerate_cell_is_nan_not_silent,
            check_shuffled_gold_collapses_icc,
        )

        return [
            lambda: check_shuffled_gold_collapses_icc(seed=self.seed),
            lambda: check_degenerate_cell_is_nan_not_silent(seed=self.seed),
        ]


@register_phase("phase_local_vs_cloud")
class PhaseLocalVsCloud(Phase):
    """Scoop defense: local-vs-cloud scoring head-to-head with pre-registered non-inferiority.

    AMTES/Liu 2025 reported ICC 0.92-0.98 for history-taking scoring on CLOUD models; our wedge is the
    first faculty-valid scoring on a LOCAL open model. This phase validates the head-to-head artifact
    (the SAME scorers / prompts / synthetic transcripts run through the local model AND each cloud
    comparator) and pre-registers the non-inferiority test (local vs cloud, margin delta = 0.10 per
    HYPOTHESIS.md) overall AND per SEGUE domain (ECOSBot showed cloud communication-subdomain ICC
    collapses to 0.31-0.44).

    Real numbers come from the batch runner (``scripts/local_vs_cloud.py``), which requires at least
    one cloud API key and writes the artifact this phase validates. Until that batch runs the phase
    reports a seeded fixture cross-check (true-vs-shuffled-gold overall ICC) so the evidence table is
    populated reproducibly and the negative controls — including the structural PHI guard — still fire.

    PHI: no real data is ever transmitted. The contract refuses any artifact whose provenance is not
    off-device safe, and the PHI-guard negative control proves a real-data path is hard-refused.
    """

    inputs = [PROJECT_ROOT / "results" / "phase_local_vs_cloud" / "local_vs_cloud.json"]
    outputs = [PROJECT_ROOT / "results" / "phase_local_vs_cloud" / "local_vs_cloud.json"]
    seed = SEED

    def run(self) -> dict:
        from harness.contracts.local_vs_cloud import check_local_vs_cloud_inputs

        check_local_vs_cloud_inputs(self.inputs[0])
        import json

        return {"comparison": json.loads(Path(self.inputs[0]).read_text(encoding="utf-8"))}

    def benchmark(self) -> dict:
        from harness.sanity.local_vs_cloud import check_shuffled_gold_collapses_icc

        if self.inputs_exist():
            from harness.contracts.local_vs_cloud import check_local_vs_cloud_inputs

            check_local_vs_cloud_inputs(self.inputs[0])
            return {"status": "COMPUTED", "artifact": str(self.inputs[0].name)}

        m = check_shuffled_gold_collapses_icc(seed=self.seed)
        return {
            "status": "PENDING_REAL_DATA",
            "ni_margin": 0.10,
            "fixture_true_icc": round(m["true_icc"], 3),
            "fixture_shuffled_icc": round(m["shuffled_icc"], 3),
        }

    def sanity(self) -> List[Callable[[], dict]]:
        from harness.sanity.local_vs_cloud import (
            check_degenerate_cell_is_nan_not_silent,
            check_phi_guard_blocks_real_data_path,
            check_shuffled_gold_collapses_icc,
        )

        return [
            lambda: check_shuffled_gold_collapses_icc(seed=self.seed),
            lambda: check_degenerate_cell_is_nan_not_silent(seed=self.seed),
            lambda: check_phi_guard_blocks_real_data_path(seed=self.seed),
        ]
