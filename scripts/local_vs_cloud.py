"""Local-vs-cloud scoring head-to-head runner (scoop defense for SQ1).

Scores the SAME off-device-safe synthetic golded set with (a) the LOCAL model and (b) each requested
CLOUD comparator (DeepSeek / Qwen-Max / GPT-4o), through the IDENTICAL scorers and prompts, then
reports overall + per-SEGUE-domain ICC-vs-gold and the pre-registered local-vs-cloud non-inferiority
deltas (margin delta = 0.10, HYPOTHESIS.md). The registered ``phase_local_vs_cloud`` harness phase
validates and summarizes the artifact it writes.

ABSOLUTE PHI RULE: only the explicitly-synthetic dataset is ever transmitted off-device. The dataset
is built via ``aivmt.cloud.synthetic_cloud_dataset`` (provenance-stamped), and the compare function
refuses any non-cloud-safe dataset. Real-data directories can never reach a cloud endpoint.

Provider keys come from env vars (NAMES only; values never logged). A provider whose key is unset is
SKIPPED with a loud log (a partial-key run still works); nothing degrades silently.

Usage (offline mock smoke — safe with no keys / no network; the GPU may be busy):
  uv run python scripts/local_vs_cloud.py --providers deepseek qwen-max gpt-4o \
      --local-model llama3.1:8b --transcripts 30 --mock

Usage (real head-to-head — run separately once keys are exported and the local model is free):
  export DEEPSEEK_API_KEY=...  DASHSCOPE_API_KEY=...  OPENAI_API_KEY=...
  uv run --extra serve python scripts/local_vs_cloud.py \
      --providers deepseek qwen-max gpt-4o --local-model llama3.1:8b --transcripts 30
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from omegaconf import OmegaConf

from aivmt.cases import load_case
from aivmt.cloud import (
    DEFAULT_NI_MARGIN,
    MissingApiKeyError,
    build_cloud_client,
    compare_local_vs_cloud,
    resolve_provider,
    synthetic_cloud_dataset,
    write_local_vs_cloud_artifacts,
)
from aivmt.llm.base import BaseLLMClient

ROOT = Path(__file__).resolve().parents[1]
OLLAMA = "http://localhost:11434/v1"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("local_vs_cloud")


def load_seed() -> int:
    """Seed from configs/seed.yaml — never hardcoded in analysis code."""
    cfg = OmegaConf.load(ROOT / "configs" / "seed.yaml")
    return int(cfg.seed)  # type: ignore[attr-defined]


def _local_client(model_tag: str, mock: bool) -> BaseLLMClient:
    if mock:
        from aivmt.llm.mock import MockLLMClient

        return MockLLMClient(model_id=model_tag)
    from aivmt.llm.openai_compat import OpenAICompatClient

    return OpenAICompatClient(
        model_id=model_tag, base_url=OLLAMA, api_key="ollama", temperature=0.0
    )


def _resolve_cloud(
    provider_names: list[str], mock: bool
) -> tuple[list[tuple[str, str, BaseLLMClient]], list[str]]:
    """Build (name, model_id, client) for each provider with a key set; SKIP keyless ones loudly.

    In ``--mock`` mode every provider is exercised with the deterministic mock client (no key, no
    network) so the comparison LOGIC is verified offline. In real mode a provider whose env key is
    unset is skipped with a loud log (partial-key runs still work) rather than crashing the batch.

    Returns the (resolved triples, skipped provider names). The skipped list is recorded in the
    artifact so a requested-but-keyless provider leaves a durable, auditable trace — not just a log
    line that vanishes after the run.
    """
    from aivmt.llm.mock import MockLLMClient

    triples: list[tuple[str, str, BaseLLMClient]] = []
    skipped: list[str] = []
    for name in provider_names:
        provider = resolve_provider(name)
        if mock:
            triples.append((name, f"mock::{provider.model_id}", MockLLMClient(model_id=name)))
            continue
        try:
            client = build_cloud_client(provider)
        except MissingApiKeyError as exc:
            logger.warning(
                "SKIP cloud provider %s: %s (set $%s to include it)",
                name, exc, provider.env_key_name,
            )
            skipped.append(name)
            continue
        triples.append((name, provider.model_id, client))
    return triples, skipped


def _print_plan(args: argparse.Namespace, n_cloud: int) -> None:
    logger.info("=== local-vs-cloud plan ===")
    logger.info("local model : %s", args.local_model)
    logger.info("providers   : %s", ", ".join(args.providers))
    logger.info("cloud active: %d (keyless providers skipped)", n_cloud)
    logger.info("transcripts : %d (synthetic golded, off-device safe)", args.transcripts)
    logger.info("variant     : %s", args.variant)
    logger.info("ni margin   : %.2f", args.ni_margin)
    logger.info("mock        : %s", args.mock)
    logger.info("===========================")


def main() -> None:
    parser = argparse.ArgumentParser(description="local-vs-cloud scoring head-to-head (SQ1 scoop defense)")
    parser.add_argument(
        "--providers", nargs="+", default=["deepseek", "qwen-max", "gpt-4o"],
        help="cloud comparators to include (keyless ones are skipped with a loud log)",
    )
    parser.add_argument("--local-model", default="llama3.1:8b", help="local model tag (Ollama)")
    parser.add_argument("--transcripts", type=int, default=30)
    parser.add_argument(
        "--variant", default="zero_shot", choices=["zero_shot", "few_shot"],
        help="scorer prompting arm (same arm applied to every model — must be identical to compare)",
    )
    parser.add_argument(
        "--ni-margin", type=float, default=DEFAULT_NI_MARGIN,
        help="pre-registered non-inferiority margin (default 0.10 per HYPOTHESIS.md)",
    )
    parser.add_argument("--case", default=str(ROOT / "conf" / "case" / "example_chestpain_en.yaml"))
    parser.add_argument("--mock", action="store_true", help="use the deterministic mock LLM (offline)")
    args = parser.parse_args()

    if args.transcripts < 2:
        parser.error("--transcripts must be >= 2 (ICC requires n>=2 targets)")

    seed = load_seed()
    case = load_case(Path(args.case))
    dataset = synthetic_cloud_dataset(case, args.transcripts)  # provenance-stamped, off-device safe

    cloud, skipped = _resolve_cloud(args.providers, args.mock)
    _print_plan(args, len(cloud))

    # Real-mode fail-loud: if the user EXPLICITLY requested >=1 cloud provider but NOT ONE resolved a
    # key, exit non-zero instead of silently writing a local-only artifact that reads as a "valid"
    # head-to-head. (Mock mode resolves every provider, so this never fires there.)
    if not args.mock and args.providers and not cloud:
        parser.error(
            "no requested cloud provider resolved an API key, so the head-to-head would collapse to a "
            f"local-only run. Requested {args.providers}; all were skipped (keys unset). Export "
            "DEEPSEEK_API_KEY / DASHSCOPE_API_KEY / OPENAI_API_KEY (see .env.example), or pass "
            "--providers with at least one keyed provider. (Use --mock for an offline logic smoke.)"
        )
    if skipped:
        logger.warning(
            "PARTIAL head-to-head: %d of %d requested provider(s) skipped (key unset): %s. The "
            "artifact records skipped_providers so the omission is auditable, not just logged.",
            len(skipped), len(args.providers), ", ".join(skipped),
        )

    comparison = compare_local_vs_cloud(
        case, dataset, args.local_model, _local_client(args.local_model, args.mock), cloud,
        seed=seed, variant=args.variant, ni_margin=args.ni_margin,
        requested_providers=args.providers, skipped_providers=skipped,
    )

    # Mock smoke output goes to a SEPARATE dir so it can never masquerade as the real phase artifact
    # (the phase reads results/phase_local_vs_cloud/local_vs_cloud.json; a uniformly-degenerate mock
    # artifact there would correctly fail the contract and sink run_all).
    out_dir = ROOT / "results" / (
        "phase_local_vs_cloud_mock" if args.mock else "phase_local_vs_cloud"
    )
    json_path, md_path = write_local_vs_cloud_artifacts(comparison, out_dir)
    logger.info("\nwrote %s", json_path)
    logger.info("wrote %s", md_path)
    logger.info("local overall ICC(2,1)=%s", comparison.local.overall_icc2_1)
    for d in comparison.deltas:
        logger.info("delta vs %s: overall=%s", d.cloud_provider, d.delta_overall)
    if args.mock:
        logger.info(
            "NOTE: --mock output is in %s (NOT the phase artifact dir). The mock cells are uniformly "
            "degenerate by construction; run without --mock with >=1 cloud key for the real head-to-head.",
            out_dir,
        )


if __name__ == "__main__":
    main()
