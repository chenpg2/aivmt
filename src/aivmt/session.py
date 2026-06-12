"""Collection front-end: run ONE standardized-patient encounter and save the transcript.

The student (or an instructor role-playing one) types their history-taking questions; the local
model plays the patient (answers only what is asked). `/done` ends history-taking and triggers the
out-loud reasoning probe. The full transcript + telemetry are saved for later scoring.

Usage:
  uv run --extra serve python -m aivmt.session --case obgyn_ectopic_zh_01 --id P03_ectopic
  uv run --extra serve --extra voice python -m aivmt.session --case obgyn_ectopic_zh_01 --id P03 --voice
  uv run python -m aivmt.session --case obgyn_ectopic_zh_01 --id SMOKE --model mock   # offline dry run
Voice mode: Enter starts/stops recording; the transcribed text is shown for
accept (Enter) / redo (r) / type-correction; the patient's reply is spoken aloud.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from .cases import load_case
from .dataio import save_transcript
from .llm import LLMFactory
from .patient import PatientAgent, build_transcript
from .schemas import Telemetry

ROOT = Path(__file__).resolve().parents[2]  # AIVMT/
CONF_CASE = ROOT / "conf" / "case"


def main() -> None:
    ap = argparse.ArgumentParser(description="Run one AI standardized-patient encounter.")
    ap.add_argument("--case", required=True, help="case_id, e.g. obgyn_ectopic_zh_01")
    ap.add_argument("--id", required=True, help="encounter id, e.g. P03_ectopic")
    ap.add_argument("--model", default="gpt-oss:20b", help="ollama model id, or 'mock' for offline")
    ap.add_argument("--base-url", default="http://localhost:11434/v1")
    ap.add_argument("--out", default=str(ROOT / "data" / "transcripts"))
    ap.add_argument("--voice", action="store_true", help="spoken encounter (local ASR + TTS)")
    ap.add_argument("--whisper-model", default="small", help="ASR size: small|medium")
    args = ap.parse_args()

    case = load_case(CONF_CASE / f"{args.case}.yaml")
    if args.model == "mock":
        llm = LLMFactory("mock")
    else:
        llm = LLMFactory(
            "openai_compat", model_id=args.model, base_url=args.base_url,
            api_key="ollama", temperature=0.7,
        )
    agent = PatientAgent(case, llm)

    transcriber = record_fn = speak_fn = None
    if args.voice:
        from .voice import Transcriber, record_push_to_talk, speak  # noqa: PLC0415

        transcriber = Transcriber(model_size=args.whisper_model)
        record_fn, speak_fn = record_push_to_talk, speak

    def hear(label: str) -> str:
        """Get one student utterance (voice or typed); '' means skip, '/done' ends."""
        if transcriber is None or record_fn is None:
            return input(f"{label}: ").strip()
        while True:
            cmd = input(f"{label} [回车=说话, d=结束问诊, q=放弃]: ").strip().lower()
            if cmd == "d":
                return "/done"
            if cmd == "q":
                raise KeyboardInterrupt
            audio = record_fn()
            if audio is None:
                print("[太短,重录]")
                continue
            text = transcriber.transcribe(audio, case.language)
            fix = input(f"  识别: “{text}”  [回车=确认, r=重录, 或直接输入更正]: ").strip()
            if fix == "":
                return text
            if fix.lower() == "r":
                continue
            return fix  # typed correction

    print(f"\n=== 病例 {case.case_id}: {case.title} ===")
    mode = "语音" if args.voice else "打字"
    print(f"[{mode}模式] 你是学生,开始问诊。/done 结束问诊进入'出声推理'; Ctrl-C 放弃。\n")

    turns: list[tuple[str, str]] = []
    n_questions = n_repeats = 0
    t0 = time.time()

    while True:  # phase 1: history-taking
        try:
            utt = hear("学生")
        except (EOFError, KeyboardInterrupt):
            print("\n[放弃,未保存]")
            return
        if not utt:
            continue
        if utt == "/done":
            break
        if utt == "/repeat":
            n_repeats += 1
            print("[已记一次重复]")
            continue
        turns.append(("student", utt))
        n_questions += 1
        try:
            reply = agent.reply(utt)
        except Exception as exc:  # noqa: BLE001 - surface model errors to the operator
            print(f"[模型错误] {exc}")
            return
        print(f"病人: {reply}")
        if speak_fn:
            speak_fn(reply, case.language)
        turns.append(("patient", reply))

    print(f"\n系统: {agent.reasoning_prompt}")  # phase 2: reasoning probe
    if speak_fn:
        speak_fn(agent.reasoning_prompt, case.language)
    try:
        reasoning = hear("学生(推理)")
    except (EOFError, KeyboardInterrupt):
        reasoning = ""
    if reasoning == "/done":
        reasoning = ""
    if reasoning:
        turns.append(("student", reasoning))
        n_questions += 1

    telemetry = Telemetry(
        duration_s=round(time.time() - t0, 1),
        n_student_questions=n_questions,
        n_voluntary_repeats=n_repeats,
    )
    transcript = build_transcript(args.id, case, turns, telemetry)
    out = save_transcript(transcript, Path(args.out) / f"{args.id}.json")
    print(f"\n[已保存] {out}  ({n_questions} 轮提问, {telemetry.duration_s:.0f} 秒)")


if __name__ == "__main__":
    main()
