"""Real end-to-end scoring of one encounter with the local Ollama model (gpt-oss:20b).

Run: uv run --extra serve python scripts/real_score_demo.py
Proves the full research core works against a real local open-weight model (not the mock).
"""

from __future__ import annotations

from pathlib import Path

from aivmt.cases import load_case
from aivmt.dataio import save_encounter
from aivmt.llm.openai_compat import OpenAICompatClient
from aivmt.pipeline import ScoringPipeline
from aivmt.schemas import Telemetry, Transcript, Turn

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    case = load_case(ROOT / "conf" / "case" / "example_chestpain_en.yaml")

    # A realistic (good) student history-taking encounter for the chest-pain case (English primary).
    transcript = Transcript(
        encounter_id="demo_enc_1",
        case_id=case.case_id,
        language="en",
        turns=(
            Turn("student", "Hello, I'm a medical student. What brings you in today?", 0.0, 3.0),
            Turn("patient", "I have chest pain.", 3.0, 5.0),
            Turn("student", "When did it start? What does it feel like? Does it radiate anywhere?", 5.0, 9.0),
            Turn("patient", "It started two hours ago, a crushing pressure, radiating to my left arm, and I'm sweating.", 9.0, 14.0),
            Turn("student", "Any nausea or shortness of breath? Do you have hypertension or diabetes? Do you smoke?", 14.0, 19.0),
            Turn("patient", "A little nausea, I have high blood pressure, and I smoke.", 19.0, 23.0),
            Turn("student", "I'm mainly considering acute coronary syndrome; I recommend an immediate ECG and troponin.", 23.0, 28.0),
        ),
        telemetry=Telemetry(duration_s=28.0, n_student_questions=3, n_voluntary_repeats=0),
    )

    llm = OpenAICompatClient(
        model_id="gpt-oss:20b",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        temperature=0.0,
    )

    print("scoring with gpt-oss:20b (4 LLM calls)...", flush=True)
    result = ScoringPipeline(llm).run(case, transcript)
    s = result.score

    print("\n================ REAL SCORE (gpt-oss:20b) ================")
    print(f"model:              {result.model_id}")
    print(f"history_completion: {s.history_completion:.2f}")
    print(f"SEGUE:              { {k: round(v, 2) for k, v in s.segue.items()} }")
    print(f"reasoning:          {s.reasoning:.2f}")
    print(f"OVERALL:            {s.overall:.3f}")
    print(f"items covered:      {[i.item_id for i in s.item_scores if i.covered]}")
    print("\nfeedback summary:   ", result.feedback.summary)
    print("strengths:          ", list(result.feedback.strengths))
    print("improvements:       ", list(result.feedback.improvements))

    out = save_encounter(result, transcript, ROOT / "outputs" / "demo_enc_1_scored.json")
    print("\nsaved:", out)


if __name__ == "__main__":
    main()
