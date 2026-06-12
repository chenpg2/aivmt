"""Scorer-robustness batch runner (SQ1).

Quantifies how stable the local-model automated scores are under perturbations that must NOT change
a valid clinical judgement:
  (a) PROMPT-PARAPHRASE sensitivity — rescore a synthetic golded set under each semantics-preserving
      system-prompt rewording and report the spread (SD / range) of ICC-vs-gold; and
  (b) STOCHASTICITY / TEST-RETEST — rescore the same transcripts K=len(seeds) times per temperature
      and report the across-repeat ICC + mean coefficient of variation.

Runs per (model x scorer-variant). Writes results/phase_robustness/{robustness.json,robustness.md},
which the registered ``phase_robustness`` harness phase validates and summarizes.

NOTE: the gold here is DESIGNED synthetic (an optimistic stability probe, not the validity claim).
The seed comes from configs/seed.yaml; it is never hardcoded.

Usage (tiny smoke):
  uv run --extra serve python scripts/robustness.py --models qwen2.5:3b \
      --transcripts 3 --paraphrases 5 --seeds 2 --temps 0 --variants zero_shot

Usage (full real matrix — run separately, see how_to_run_full_matrix):
  uv run --extra serve python scripts/robustness.py \
      --models llama3.1:8b qwen2.5:14b gpt-oss:20b qwen2.5:3b qwen2.5:7b \
      --transcripts 30 --paraphrases 5 --seeds 3 --temps 0 0.3 --variants zero_shot few_shot
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from omegaconf import OmegaConf

from aivmt.cases import load_case
from aivmt.llm.base import BaseLLMClient
from aivmt.llm.openai_compat import OpenAICompatClient
from aivmt.robustness import (
    PARAPHRASE_TEMPLATES,
    RobustnessReport,
    build_golded_dataset,
    paraphrase_sensitivity,
    retest_reliability,
    transcripts_only,
    write_robustness_artifacts,
)
from aivmt.robustness.types import ParaphraseSensitivity

ROOT = Path(__file__).resolve().parents[1]
OLLAMA = "http://localhost:11434/v1"
DEFAULT_MODELS = ("llama3.1:8b", "qwen2.5:14b", "gpt-oss:20b", "qwen2.5:3b", "qwen2.5:7b")

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("robustness")


def load_seed() -> int:
    """Seed from configs/seed.yaml — never hardcoded in analysis code."""
    cfg = OmegaConf.load(ROOT / "configs" / "seed.yaml")
    return int(cfg.seed)  # type: ignore[attr-defined]


def _ollama_factory(model_id: str):
    """Return a ``client_factory(seed, temperature)`` building a fresh Ollama client per repeat.

    Ollama's OpenAI-compatible endpoint is driven by temperature; the seed is threaded for
    provenance (and passed via ``extra_body`` would pin a backend that honors it). A fresh client
    per repeat keeps observability counters per-repeat.
    """

    def factory(seed: int, temperature: float) -> BaseLLMClient:
        return OpenAICompatClient(
            model_id=model_id, base_url=OLLAMA, api_key="ollama", temperature=temperature
        )

    return factory


def _print_plan(args: argparse.Namespace, n_cells: int) -> None:
    logger.info("=== robustness plan ===")
    logger.info("models      : %s", ", ".join(args.models))
    logger.info("variants    : %s", ", ".join(args.variants))
    logger.info("transcripts : %d (synthetic golded)", args.transcripts)
    logger.info("paraphrases : %d registered templates", len(PARAPHRASE_TEMPLATES))
    logger.info("seeds       : %d repeats", args.seeds)
    logger.info("temps       : %s", ", ".join(str(t) for t in args.temps))
    logger.info("cells       : %d (model x variant)", n_cells)
    logger.info("output      : %s", ROOT / "results" / "phase_robustness")
    logger.info("=======================")


def run_cell(
    model_id: str,
    variant: str,
    dataset,
    seeds: Sequence[int],
    temps: Sequence[float],
    client_factory,
) -> RobustnessReport:
    """Compute paraphrase sensitivity + per-temperature test-retest for one (model x variant)."""
    case = dataset.case
    base_seed = dataset.seed

    # Paraphrase sensitivity uses a single deterministic (temp 0) client.
    logger.info("[%s/%s] paraphrase sensitivity over %d templates ...", model_id, variant, len(PARAPHRASE_TEMPLATES))
    para_client = client_factory(base_seed, 0.0)
    para: ParaphraseSensitivity = paraphrase_sensitivity(
        case, dataset.golded, para_client, variant=variant  # type: ignore[arg-type]
    )
    logger.info(
        "  icc_mean=%.3f icc_sd=%.3f icc_range=%.3f", para.icc_mean, para.icc_sd, para.icc_range
    )

    retests = []
    transcripts = transcripts_only(dataset.golded)
    for temp in temps:
        logger.info("[%s/%s] test-retest temp=%s over %d repeats ...", model_id, variant, temp, len(seeds))
        tr = retest_reliability(
            case, transcripts, client_factory, temperature=temp, seeds=seeds, variant=variant  # type: ignore[arg-type]
        )
        logger.info(
            "  retest_icc=%s mean_cv=%.3f degenerate=%s", tr.retest_icc, tr.mean_cv, tr.degenerate
        )
        retests.append(tr)

    return RobustnessReport(
        model_id=model_id,
        variant=variant,
        seed=base_seed,
        paraphrase=para,
        test_retest=tuple(retests),
    )


class _Dataset:
    """Bundle of the synthetic case + golded transcripts + seed used for one run."""

    def __init__(self, case, golded, seed: int) -> None:
        self.case = case
        self.golded = golded
        self.seed = seed


def main() -> None:
    parser = argparse.ArgumentParser(description="SQ1 scorer-robustness batch runner")
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--transcripts", type=int, default=12)
    parser.add_argument(
        "--paraphrases", type=int, default=5,
        help="declared minimum (>=5); the registered template set is always used in full",
    )
    parser.add_argument("--seeds", type=int, default=3, help="number of test-retest repeats (K>=2)")
    parser.add_argument("--temps", type=float, nargs="+", default=[0.0, 0.3])
    parser.add_argument(
        "--variants", nargs="+", default=["zero_shot", "few_shot"],
        choices=["zero_shot", "few_shot"],
    )
    parser.add_argument(
        "--case", default=str(ROOT / "conf" / "case" / "example_chestpain_en.yaml"),
    )
    parser.add_argument("--mock", action="store_true", help="use the deterministic mock LLM (offline)")
    args = parser.parse_args()

    if args.paraphrases < 5:
        parser.error("--paraphrases must be >= 5 (the contract requires it)")
    if args.seeds < 2:
        parser.error("--seeds must be >= 2 (test-retest needs K>=2)")

    base_seed = load_seed()
    case = load_case(Path(args.case))
    golded = build_golded_dataset(case, args.transcripts)
    dataset = _Dataset(case, golded, base_seed)

    n_cells = len(args.models) * len(args.variants)
    _print_plan(args, n_cells)

    seeds = [base_seed + i for i in range(args.seeds)]
    reports: list[RobustnessReport] = []
    cell = 0
    for model_id in args.models:
        if args.mock:
            from aivmt.llm.mock import MockLLMClient

            def factory(seed: int, temperature: float) -> BaseLLMClient:
                return MockLLMClient(model_id=model_id)
        else:
            factory = _ollama_factory(model_id)  # type: ignore[assignment]

        for variant in args.variants:
            cell += 1
            logger.info("\n--- cell %d/%d: model=%s variant=%s ---", cell, n_cells, model_id, variant)
            try:
                reports.append(run_cell(model_id, variant, dataset, seeds, args.temps, factory))
            except Exception as exc:  # one bad cell must not sink the rest
                logger.error("CELL FAILED (model=%s variant=%s): %s", model_id, variant, exc)

    out_dir = ROOT / "results" / "phase_robustness"
    json_path, md_path = write_robustness_artifacts(reports, out_dir)
    logger.info("\nwrote %s", json_path)
    logger.info("wrote %s", md_path)
    logger.info("cells completed: %d/%d", len(reports), n_cells)


if __name__ == "__main__":
    main()
