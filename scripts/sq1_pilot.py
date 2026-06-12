"""SQ1 feasibility pilot (R1 GO/NO-GO floor check).

Builds graded synthetic transcripts with a DESIGNED quality ordering (the "gold"), scores each
with a local model, and computes ICC(system_overall, gold) + JSON-parse robustness.

This is NOT the real validity claim (that uses faculty). It is the cheapest make-or-break test:
if a local model cannot even track designed quality on clean synthetic text, it will not match
faculty on noisy real ASR. Gate: ICC(2,1) >= 0.6 AND JSON-parse >= 98% AND refusals <= 1%.

CAVEAT: the gold is constructed and partly correlated with checklist coverage that the scorer
measures, so this ICC is an OPTIMISTIC floor, not the validity result.

Usage: uv run --extra serve python scripts/sq1_pilot.py [model ...]   (default: gpt-oss:20b)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from aivmt.cases import load_case
from aivmt.llm.base import LLMOutputError
from aivmt.llm.openai_compat import OpenAICompatClient
from aivmt.metrics import icc
from aivmt.pipeline import DEFAULT_WEIGHTS
from aivmt.schemas import Telemetry, Transcript, Turn
from aivmt.scoring import ScorerFactory

ROOT = Path(__file__).resolve().parents[1]
OLLAMA = "http://localhost:11434/v1"

# Quality tiers: (gold_base, [(speaker, text), ...]) for the English chest-pain case.
TIERS: list[tuple[float, list[tuple[str, str]]]] = [
    (0.15, [
        ("student", "What's wrong?"),
        ("patient", "My chest hurts."),
        ("student", "Okay, I'll get the doctor."),
    ]),
    (0.35, [
        ("student", "What brings you in?"),
        ("patient", "Chest pain."),
        ("student", "When did it start?"),
        ("patient", "About two hours ago."),
        ("student", "Alright."),
    ]),
    (0.55, [
        ("student", "Hi, what's the problem today?"),
        ("patient", "Chest pain."),
        ("student", "When did it start, what does it feel like, and does it spread anywhere?"),
        ("patient", "Two hours ago, crushing, goes to my left arm."),
        ("student", "Any other symptoms?"),
        ("patient", "Some sweating."),
        ("student", "It might be a heart problem."),
    ]),
    (0.75, [
        ("student", "Hello, I'm a medical student. What brings you in today?"),
        ("patient", "Chest pain."),
        ("student", "When did it start, what's it like, and does it radiate?"),
        ("patient", "Two hours ago, crushing, to the left arm."),
        ("student", "Any sweating, nausea or breathlessness? Do you have high blood pressure or diabetes, or smoke?"),
        ("patient", "Sweating and nausea; I have hypertension and I smoke."),
        ("student", "That sounds frightening. I'm considering acute coronary syndrome and will order an ECG and troponin."),
    ]),
    (0.90, [
        ("student", "Hello, I'm Alex, a medical student. May I ask you some questions about what's going on? What brings you in today?"),
        ("patient", "I have chest pain."),
        ("student", "I'm sorry to hear that. When did it start and what does the pain feel like?"),
        ("patient", "Two hours ago, a crushing pressure."),
        ("student", "Does it spread anywhere, and is there any sweating, nausea, or shortness of breath?"),
        ("patient", "It goes to my left arm; I'm sweating and a bit nauseous."),
        ("student", "Do you have past conditions like high blood pressure or diabetes, and do you smoke?"),
        ("patient", "Hypertension, and I smoke."),
        ("student", "What are you most worried about?"),
        ("patient", "That it's my heart."),
        ("student", "Understandable. To summarize: two hours of crushing chest pain radiating to the left arm with sweating and nausea, with hypertension and smoking. I'm most concerned about acute coronary syndrome, so I'd like an ECG and troponin now, aspirin if appropriate, and to keep you monitored. Does that sound okay, and any questions?"),
        ("patient", "Okay, thank you."),
    ]),
]

VARIANTS = 6  # per tier -> 30 encounters


def build_dataset(case):
    data = []
    for t, (base, turns) in enumerate(TIERS):
        for i in range(VARIANTS):
            jitter = (i - (VARIANTS - 1) / 2) * 0.012
            gold = min(1.0, max(0.0, base + jitter))
            tt = list(turns)
            tt[0] = (tt[0][0], tt[0][1] + f" (case {i})")  # keep transcripts distinct
            transcript = Transcript(
                encounter_id=f"syn_t{t}_{i}",
                case_id=case.case_id,
                language="en",
                turns=tuple(Turn(s, x, 0.0, 0.0) for s, x in tt),
                telemetry=Telemetry(),
            )
            data.append((transcript, gold))
    return data


def score_overall(case, transcript, scorers, llm) -> float:
    acc: dict = {}
    for s in scorers:
        acc.update(s.score(case, transcript, llm))
    history = float(acc.get("history_completion", 0.0))
    segue = acc.get("segue", {})
    reasoning = float(acc.get("reasoning", 0.0))
    segue_mean = sum(segue.values()) / len(segue) if segue else 0.0
    return (
        DEFAULT_WEIGHTS["history"] * history
        + DEFAULT_WEIGHTS["segue"] * segue_mean
        + DEFAULT_WEIGHTS["reasoning"] * reasoning
    )


def run_model(model_id: str, case, dataset) -> dict:
    """Score all encounters with one model. CHECKPOINTED: each encounter's result is appended
    to a .jsonl so a kill mid-run loses nothing — re-running resumes from where it stopped."""
    llm = OpenAICompatClient(model_id=model_id, base_url=OLLAMA, api_key="ollama", temperature=0.0)
    scorers = [ScorerFactory(n) for n in ("checklist", "segue", "reasoning")]
    safe = model_id.replace(":", "_").replace("/", "_")
    ckpt = ROOT / "results" / "phase_scoring_validity" / f"partial_{safe}.jsonl"
    ckpt.parent.mkdir(parents=True, exist_ok=True)

    done: dict[str, dict] = {}
    if ckpt.exists():
        for line in ckpt.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["eid"]] = rec
        print(f"  [resume] {len(done)} encounters already done for {model_id}", flush=True)

    failures = 0
    with ckpt.open("a", encoding="utf-8") as fh:
        for idx, (transcript, gold) in enumerate(dataset):
            eid = transcript.encounter_id
            if eid in done:
                continue
            try:
                sysv = score_overall(case, transcript, scorers, llm)
                rec = {"eid": eid, "sys": sysv, "gold": gold}
                done[eid] = rec
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
            except LLMOutputError as exc:
                failures += 1
                print(f"  [parse-fail] {eid}: {exc}", flush=True)
            print(f"  scored {idx + 1}/{len(dataset)}", flush=True)

    sys_scores = [r["sys"] for r in done.values()]
    golds = [r["gold"] for r in done.values()]
    n = len(sys_scores)
    matrix = np.column_stack([sys_scores, golds]) if n >= 2 else None
    parse_rate = 1.0 - llm.n_parse_failures / max(llm.n_calls, 1)
    refusal_rate = llm.n_refusals / max(llm.n_calls, 1)
    result = {
        "model": model_id,
        "n_scored": n,
        "n_encounter_failures": failures,
        "llm_calls": llm.n_calls,
        "parse_failures": llm.n_parse_failures,
        "parse_success_rate": round(parse_rate, 4),
        "refusal_rate": round(refusal_rate, 4),
        "icc2_1": round(icc(matrix, "icc2_1"), 4) if matrix is not None else None,
        "icc2_k": round(icc(matrix, "icc2_k"), 4) if matrix is not None else None,
    }
    gate_icc = result["icc2_1"] is not None and result["icc2_1"] >= 0.6
    gate_parse = parse_rate >= 0.98
    gate_refusal = refusal_rate <= 0.01
    result["GATE_PASS"] = bool(gate_icc and gate_parse and gate_refusal)
    return result


def main() -> None:
    models = sys.argv[1:] or ["gpt-oss:20b"]
    case = load_case(ROOT / "conf" / "case" / "example_chestpain_en.yaml")
    dataset = build_dataset(case)
    out_dir = ROOT / "results" / "phase_scoring_validity"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    for model_id in models:
        print(f"\n=== model: {model_id} ({len(dataset)} synthetic encounters) ===", flush=True)
        try:
            res = run_model(model_id, case, dataset)
        except Exception as exc:  # one bad model must not sink the others
            print(f"MODEL FAILED ({model_id}): {exc}", flush=True)
            all_results.append({"model": model_id, "error": str(exc), "GATE_PASS": False})
            continue
        all_results.append(res)
        safe = model_id.replace(":", "_").replace("/", "_")
        (out_dir / f"pilot_{safe}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(json.dumps(res, indent=2), flush=True)
        verdict = "PASS -> proceed" if res["GATE_PASS"] else "FAIL -> investigate / Tier C"
        print(f"GATE ({model_id}): {verdict}", flush=True)

    (out_dir / "pilot_summary.json").write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print("\nCAVEAT: gold is designed (optimistic floor); the real validity claim uses faculty.", flush=True)


if __name__ == "__main__":
    main()
