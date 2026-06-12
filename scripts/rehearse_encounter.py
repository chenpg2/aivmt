"""Collection-day rehearsal: drive one full encounter with a SCRIPTED student against the
AI patient (local model), save the transcript, then score it. Validates Chinese patient acting
(answers only when asked, stays in role), transcript capture, and end-to-end scoring on an
OB/GYN case — all BEFORE collection day, no human needed.

Run: uv run --extra serve python scripts/rehearse_encounter.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from aivmt.cases import load_case
from aivmt.dataio import save_encounter, save_transcript
from aivmt.llm.openai_compat import OpenAICompatClient
from aivmt.patient import PatientAgent, build_transcript
from aivmt.pipeline import ScoringPipeline
from aivmt.schemas import Telemetry

ROOT = Path(__file__).resolve().parents[1]
OLLAMA = "http://localhost:11434/v1"

# A scripted "good student" history for the ectopic-pregnancy case (covers all checklist items).
GOOD_STUDENT = [
    "您好,我是医学生,可以问您几个问题吗?今天是什么不舒服来的?",
    "这种肚子疼是什么时候开始的?有多久了?",
    "您末次月经是什么时候?平时月经规律吗,大概多少天一次?",
    "除了肚子疼,有没有阴道流血?如果有,量多不多、什么颜色?",
    "疼在肚子的哪个位置?是一直疼还是阵阵疼,有没有加重?",
    "有没有头晕、眼前发黑,或者肛门那种往下坠的感觉?",
    "您结婚了吗?有性生活吗?平时怎么避孕的?",
    "以前怀过孕吗?生过孩子或做过流产吗?",
    "以前有没有得过盆腔炎,或者做过妇科方面的手术?",
]
REASONING = (
    "我主要考虑异位妊娠,因为停经六周、有下腹痛和少量阴道流血,还有头晕和肛门坠胀,"
    "加上既往盆腔炎史是高危因素。我会先查尿和血 hCG、做经阴道超声看宫内有没有孕囊,"
    "监测生命体征,必要时查血红蛋白评估有无内出血。"
)


def main() -> None:
    case_id = sys.argv[1] if len(sys.argv) > 1 else "obgyn_ectopic_zh"
    case = load_case(ROOT / "conf" / "case" / f"{case_id}.yaml")

    patient_llm = OpenAICompatClient("gpt-oss:20b", base_url=OLLAMA, api_key="ollama", temperature=0.7)
    agent = PatientAgent(case, patient_llm)

    print(f"=== REHEARSAL: {case.case_id} — {case.title} ===\n", flush=True)
    turns: list[tuple[str, str]] = []
    for q in GOOD_STUDENT:
        print(f"学生: {q}", flush=True)
        reply = agent.reply(q)
        print(f"病人: {reply}\n", flush=True)
        turns.append(("student", q))
        turns.append(("patient", reply))

    print(f"系统: {agent.reasoning_prompt}", flush=True)
    print(f"学生(推理): {REASONING}\n", flush=True)
    turns.append(("student", REASONING))

    telemetry = Telemetry(duration_s=0.0, n_student_questions=len(GOOD_STUDENT), n_voluntary_repeats=0)
    transcript = build_transcript("REHEARSAL_good", case, turns, telemetry)
    tx_path = save_transcript(transcript, ROOT / "data" / "transcripts" / "REHEARSAL_good.json")
    print(f"[transcript saved] {tx_path}", flush=True)

    print("\n=== SCORING (gpt-oss:20b, temp 0) ===", flush=True)
    scorer_llm = OpenAICompatClient("gpt-oss:20b", base_url=OLLAMA, api_key="ollama", temperature=0.0)
    result = ScoringPipeline(scorer_llm).run(case, transcript)
    s = result.score
    print(f"history_completion: {s.history_completion:.2f}", flush=True)
    print(f"items covered: {[i.item_id for i in s.item_scores if i.covered]}", flush=True)
    print(f"items MISSED:  {[i.item_id for i in s.item_scores if not i.covered]}", flush=True)
    print(f"SEGUE: { {k: round(v,2) for k,v in s.segue.items()} }", flush=True)
    print(f"reasoning: {s.reasoning:.2f}", flush=True)
    print(f"OVERALL: {s.overall:.3f}", flush=True)
    print(f"feedback: {result.feedback.summary}", flush=True)

    out = save_encounter(result, transcript, ROOT / "results" / "rehearsal_good_scored.json")
    print(f"\n[scored encounter saved] {out}", flush=True)
    print("=== REHEARSAL COMPLETE ===", flush=True)


if __name__ == "__main__":
    main()
