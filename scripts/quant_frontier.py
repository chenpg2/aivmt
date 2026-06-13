"""Quantization-frontier batch runner (SQ3): the validity-cost surface over (model size x quant).

For each ``(model_tag, label)`` pair this scores the SAME designed synthetic golded set the
robustness lane uses, then measures: (a) ICC-vs-gold + JSON-parse/refusal robustness, (b) per-encounter
latency (median + p90, optional tokens/s), (c) loaded RAM/VRAM via ``ollama ps``, and (d) on-disk size
via ``ollama list``. All deterministic-seeded at temperature 0. Writes
results/phase_quant_frontier/{quant_frontier.json,quant_frontier.md}, which the registered
``phase_quant_frontier`` harness phase validates and summarizes.

The quant ladder is supplied as ``tag=label`` pairs so arbitrary tags work, e.g.:

  qwen2.5:7b-instruct-fp16=fp16  qwen2.5:7b-instruct-q8_0=q8_0  qwen2.5:7b=q4_K_M
  qwen2.5:7b-instruct-q3_K_M=q3_K_M

NOTE: the gold is DESIGNED synthetic (an optimistic stability probe, not the validity claim — the
real validity claim uses faculty). The seed comes from configs/seed.yaml; it is never hardcoded.

Usage (tiny mock smoke — safe while the GPU is busy / tags un-pulled):
  uv run python scripts/quant_frontier.py --mock --models mock=mock --transcripts 4

Usage (full real frontier — run separately once the ladder is pulled and the GPU is free):
  uv run --extra serve python scripts/quant_frontier.py \
      --models qwen2.5:7b-instruct-fp16=fp16 qwen2.5:7b-instruct-q8_0=q8_0 \
               qwen2.5:7b=q4_K_M qwen2.5:7b-instruct-q3_K_M=q3_K_M \
      --transcripts 30 --variant zero_shot
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from omegaconf import OmegaConf

from aivmt.cases import load_case
from aivmt.llm.base import BaseLLMClient
from aivmt.quant import (
    DiskUsage,
    MemoryUsage,
    QuantCell,
    run_quant_cell,
    write_quant_frontier_artifacts,
)
from aivmt.robustness import build_golded_dataset

ROOT = Path(__file__).resolve().parents[1]
OLLAMA = "http://localhost:11434/v1"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("quant_frontier")


def load_seed() -> int:
    """Seed from configs/seed.yaml — never hardcoded in analysis code."""
    cfg = OmegaConf.load(ROOT / "configs" / "seed.yaml")
    return int(cfg.seed)  # type: ignore[attr-defined]


def parse_model_specs(items: list[str], parser: argparse.ArgumentParser) -> list[tuple[str, str]]:
    """Parse ``tag=label`` (or bare ``tag``) pairs; the label is the quant level shown on the axis."""
    specs: list[tuple[str, str]] = []
    for it in items:
        tag, _, label = it.partition("=")
        label = label or tag
        if not tag or not label:
            parser.error(f"invalid model spec {it!r} (expected tag=label)")
        specs.append((tag, label))
    return specs


def _client(model_tag: str, mock: bool) -> BaseLLMClient:
    if mock:
        from aivmt.llm.mock import MockLLMClient

        return MockLLMClient(model_id=model_tag)
    from aivmt.llm.openai_compat import OpenAICompatClient

    return OpenAICompatClient(
        model_id=model_tag, base_url=OLLAMA, api_key="ollama", temperature=0.0
    )


def _stub_memory(model_tag: str) -> MemoryUsage:
    """Fake footprint for the offline mock path (real probing needs a loaded Ollama model)."""
    return MemoryUsage(
        model_tag=model_tag, size_bytes=1, size_display="1 B (mock)", processor="mock", context=None
    )


def _stub_disk(model_tag: str) -> DiskUsage:
    return DiskUsage(model_tag=model_tag, size_bytes=1, size_display="1 B (mock)")


def _print_plan(specs: list[tuple[str, str]], args: argparse.Namespace) -> None:
    logger.info("=== quant-frontier plan ===")
    logger.info("models      : %s", ", ".join(f"{t}={lab}" for t, lab in specs))
    logger.info("variant     : %s", args.variant)
    logger.info("transcripts : %d (synthetic golded)", args.transcripts)
    logger.info("mock        : %s", args.mock)
    logger.info("output      : %s", ROOT / "results" / "phase_quant_frontier")
    logger.info("===========================")


def main() -> None:
    parser = argparse.ArgumentParser(description="SQ3 quantization-frontier batch runner")
    parser.add_argument(
        "--models", nargs="+", required=True,
        help="quant ladder as tag=label pairs (label is the quant level on the frontier axis)",
    )
    parser.add_argument("--transcripts", type=int, default=30)
    parser.add_argument(
        "--variant", default="zero_shot", choices=["zero_shot", "few_shot"],
        help="scorer prompting arm (single — the frontier axis is model size x quant, not variant)",
    )
    parser.add_argument(
        "--case", default=str(ROOT / "conf" / "case" / "example_chestpain_en.yaml"),
    )
    parser.add_argument("--mock", action="store_true", help="use the deterministic mock LLM (offline)")
    args = parser.parse_args()

    if args.transcripts < 2:
        parser.error("--transcripts must be >= 2 (ICC requires n>=2 targets)")

    specs = parse_model_specs(args.models, parser)
    seed = load_seed()
    case = load_case(Path(args.case))
    dataset = build_golded_dataset(case, args.transcripts)
    _print_plan(specs, args)

    probe_memory = _stub_memory if args.mock else None
    probe_disk = _stub_disk if args.mock else None

    cells: list[QuantCell] = []
    for idx, (tag, label) in enumerate(specs, 1):
        logger.info("\n--- cell %d/%d: model=%s label=%s ---", idx, len(specs), tag, label)
        try:
            cells.append(
                run_quant_cell(
                    tag, label, case, dataset, _client(tag, args.mock),
                    seed=seed, variant=args.variant,
                    probe_memory=probe_memory, probe_disk=probe_disk,
                )
            )
        except Exception as exc:  # one bad cell must not sink the rest
            logger.error("CELL FAILED (model=%s label=%s): %s", tag, label, exc)

    # Mock smoke output goes to a SEPARATE dir so it can never masquerade as the real phase artifact
    # (the phase reads results/phase_quant_frontier/quant_frontier.json; a uniformly-degenerate mock
    # artifact there would correctly fail the contract and sink run_all).
    out_dir = ROOT / "results" / ("phase_quant_frontier_mock" if args.mock else "phase_quant_frontier")
    json_path, md_path = write_quant_frontier_artifacts(cells, out_dir)
    logger.info("\nwrote %s", json_path)
    logger.info("wrote %s", md_path)
    logger.info("cells completed: %d/%d", len(cells), len(specs))
    if args.mock:
        logger.info(
            "NOTE: --mock output is in %s (NOT the phase artifact dir). The mock cells are uniformly "
            "degenerate by construction; run without --mock against the quant ladder for the frontier.",
            out_dir,
        )


if __name__ == "__main__":
    main()
