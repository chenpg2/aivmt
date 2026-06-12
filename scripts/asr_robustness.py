"""ASR-robustness batch runner (SQ1): the ICC-degradation curve under simulated ASR error.

The un-flashed AIVMT voice puck has no hardware AEC, so the transcript the scorer reads is degraded
by TTS echo + far-field zh ASR error. This runner quantifies the resulting validity loss: it
corrupts a synthetic zh golded set DETERMINISTICALLY at each CER level, rescores with a local model,
and reports ICC(system_overall, gold) per level — an ICC-degradation curve per (model x variant).

Writes results/phase_asr_robustness/{asr_robustness.json,asr_robustness.md}, which the registered
``phase_asr_robustness`` harness phase validates and summarizes.

NOTE: the gold is DESIGNED synthetic (an optimistic anchor, not the validity claim). Corruption is
deterministic given the seed (from configs/seed.yaml — never hardcoded). The metric is CER (the
standard zh ASR severity metric); see the report for the WER-vs-CER note.

Usage (tiny mock smoke — safe while the GPU is busy):
  uv run python scripts/asr_robustness.py --mock --models mock \
      --transcripts 8 --wer 0 0.15 0.30 --variants zero_shot

Usage (full real curve — run separately, see how_to_run_real_curve):
  uv run --extra serve python scripts/asr_robustness.py \
      --models qwen2.5:14b gpt-oss:20b llama3.1:8b \
      --transcripts 12 --wer 0 0.05 0.15 0.30 --variants zero_shot few_shot
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from omegaconf import OmegaConf

from aivmt.asr import (
    AsrDegradationCurve,
    build_zh_golded_dataset,
    compute_curve,
    load_confusion_table,
    write_curve_artifacts,
)
from aivmt.llm.base import BaseLLMClient
from aivmt.schemas import Case, ChecklistItem

ROOT = Path(__file__).resolve().parents[1]
OLLAMA = "http://localhost:11434/v1"
DEFAULT_MODELS = ("qwen2.5:14b", "gpt-oss:20b", "llama3.1:8b")
DEFAULT_WER = (0.0, 0.05, 0.15, 0.30)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("asr_robustness")

#: A minimal synthetic zh case the fixture transcripts attach to (the curve scores against gold,
#: not against this case's checklist coverage specifically — it only supplies a case_id/language).
_SYN_CASE = Case(
    case_id="syn_zh_asr",
    title="ZH history-taking (synthetic)",
    language="zh",
    persona="(synthetic)",
    history_checklist=(
        ChecklistItem("q_onset", "asks onset", 1.0),
        ChecklistItem("q_assoc", "asks associated symptoms", 1.0),
        ChecklistItem("q_risk", "asks risk factors", 1.0),
        ChecklistItem("q_plan", "states plan", 1.0),
    ),
)


def load_seed() -> int:
    """Seed from configs/seed.yaml — never hardcoded in analysis code."""
    cfg = OmegaConf.load(ROOT / "configs" / "seed.yaml")
    return int(cfg.seed)  # type: ignore[attr-defined]


def measure_real_anchor(audio_path: Path, reference_text: str, language: str = "zh") -> float:
    """Measure the REAL CER of a faster-whisper transcription against a reference, to anchor the
    curve's operating point on actual device audio.

    This is the hook the manuscript uses to place the *empirical* operating CER on the simulated
    degradation curve. It requires (a) a rehearsal audio file and (b) its human reference transcript;
    neither is committed yet (the rehearsal transcript was produced via TTS + manual transcription,
    not from saved audio), so this runs only when both are supplied on disk. No silent fallback: a
    missing file or empty reference raises.
    """
    from aivmt.asr import measured_cer  # noqa: PLC0415
    from aivmt.voice import Transcriber  # noqa: PLC0415

    if not audio_path.is_file():
        raise FileNotFoundError(f"rehearsal audio not found: {audio_path}")
    if not reference_text.strip():
        raise ValueError("rehearsal reference transcript is empty")
    hypothesis = Transcriber(model_size="small").transcribe(str(audio_path), language)  # type: ignore[arg-type]
    cer = measured_cer(reference_text, hypothesis)
    logger.info("REAL rehearsal CER (faster-whisper vs reference) = %.3f", cer)
    return cer


def _client(model_id: str, mock: bool, temperature: float) -> BaseLLMClient:
    if mock:
        from aivmt.llm.mock import MockLLMClient

        return MockLLMClient(model_id=model_id)
    from aivmt.llm.openai_compat import OpenAICompatClient

    return OpenAICompatClient(
        model_id=model_id, base_url=OLLAMA, api_key="ollama", temperature=temperature
    )


def _print_plan(args: argparse.Namespace, n_cells: int) -> None:
    logger.info("=== asr-robustness plan ===")
    logger.info("models      : %s", ", ".join(args.models))
    logger.info("variants    : %s", ", ".join(args.variants))
    logger.info("transcripts : %d (synthetic zh golded)", args.transcripts)
    logger.info("wer levels  : %s (CER)", ", ".join(str(w) for w in args.wer))
    logger.info("cells       : %d (model x variant)", n_cells)
    logger.info("mock        : %s", args.mock)
    logger.info("output      : %s", ROOT / "results" / "phase_asr_robustness")
    logger.info("===========================")


def run_cell(
    model_id: str,
    variant: str,
    dataset,
    wer_levels: Sequence[float],
    seed: int,
    mock: bool,
    table,
) -> AsrDegradationCurve:
    """Compute the ICC-degradation curve for one (model x variant)."""
    logger.info("[%s/%s] sweeping %d CER levels ...", model_id, variant, len(wer_levels))
    llm = _client(model_id, mock, temperature=0.0)
    curve = compute_curve(
        _SYN_CASE, dataset, llm, seed=seed, wer_levels=wer_levels, variant=variant, table=table
    )
    for p in curve.points:
        logger.info(
            "  wer=%.2f achieved_cer=%.3f icc=%s degenerate=%s",
            p.target_wer, p.achieved_cer, p.icc_vs_gold, p.degenerate,
        )
    return curve


def main() -> None:
    parser = argparse.ArgumentParser(description="SQ1 ASR-robustness ICC-degradation runner")
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--transcripts", type=int, default=12)
    parser.add_argument(
        "--wer", type=float, nargs="+", default=list(DEFAULT_WER),
        help="CER target levels to sweep (must include 0.0 to anchor the clean ICC)",
    )
    parser.add_argument(
        "--variants", nargs="+", default=["zero_shot", "few_shot"],
        choices=["zero_shot", "few_shot"],
    )
    parser.add_argument("--mock", action="store_true", help="use the deterministic mock LLM (offline)")
    parser.add_argument(
        "--rehearsal-audio", default=None,
        help="optional path to rehearsal audio; with --rehearsal-ref, measures the REAL anchor CER",
    )
    parser.add_argument(
        "--rehearsal-ref", default=None,
        help="optional path to the rehearsal reference transcript text (for the real anchor CER)",
    )
    args = parser.parse_args()

    if 0.0 not in args.wer:
        parser.error("--wer must include 0.0 (the clean anchor)")

    if args.rehearsal_audio and args.rehearsal_ref:
        ref = Path(args.rehearsal_ref).read_text(encoding="utf-8")
        real_cer = measure_real_anchor(Path(args.rehearsal_audio), ref)
        logger.info("anchor the simulated curve at the measured operating CER = %.3f", real_cer)

    seed = load_seed()
    table = load_confusion_table()
    dataset = build_zh_golded_dataset(_SYN_CASE, args.transcripts)

    n_cells = len(args.models) * len(args.variants)
    _print_plan(args, n_cells)

    curves: list[AsrDegradationCurve] = []
    cell = 0
    for model_id in args.models:
        for variant in args.variants:
            cell += 1
            logger.info("\n--- cell %d/%d: model=%s variant=%s ---", cell, n_cells, model_id, variant)
            try:
                curves.append(
                    run_cell(model_id, variant, dataset, args.wer, seed, args.mock, table)
                )
            except Exception as exc:  # one bad cell must not sink the rest
                logger.error("CELL FAILED (model=%s variant=%s): %s", model_id, variant, exc)

    # Mock smoke output goes to a SEPARATE dir so it can never masquerade as the real phase artifact
    # (the phase reads results/phase_asr_robustness/asr_robustness.json; a uniformly-degenerate mock
    # artifact there would correctly fail the contract and sink run_all).
    out_dir = ROOT / "results" / ("phase_asr_robustness_mock" if args.mock else "phase_asr_robustness")
    json_path, md_path = write_curve_artifacts(curves, out_dir)
    logger.info("\nwrote %s", json_path)
    logger.info("wrote %s", md_path)
    logger.info("cells completed: %d/%d", len(curves), n_cells)
    if args.mock:
        logger.info(
            "NOTE: --mock output is in %s (NOT the phase artifact dir). The mock curve is uniformly "
            "degenerate by construction; run without --mock against real models for the reported curve.",
            out_dir,
        )


if __name__ == "__main__":
    main()
