# Validity–Cost Frontier v1 (synthetic floor pilot) — 2026-06-10

All five tiers scored with the SAME rebuilt scorers (anchored SEGUE + reasoning, fail-loud JSON),
same 30 graded English synthetic encounters, temp 0, seed fixed. Gold = designed quality ordering
(**optimistic floor — NOT the validity claim**; the real curve comes from faculty-scored data).

| model | params | disk | ICC(2,1) vs gold | ICC(2,k) | parse | gate |
|---|---|---|---|---|---|---|
| qwen2.5:3b | 3B | 1.9GB | 0.737 | 0.849 | 100% | ✅ |
| qwen2.5:7b | 7B | 4.7GB | 0.678 | 0.808 | 100% | ✅ |
| llama3.1:8b | 8B | 4.9GB | **0.915** | 0.956 | 100% | ✅ |
| qwen2.5:14b | 14B | 9.0GB | 0.905 | 0.950 | 100% | ✅ |
| gpt-oss:20b | 20B | 13.8GB | 0.888 | 0.941 | 100% | ✅ |

## Reads (honest)
1. **Floor cleared everywhere** (all ≥0.6 gate; JSON 100% across 450 calls) → R1 GO holds across the size range.
2. **Plateau ≈0.9 reached by 8B**; 14B/20B add nothing → headline candidate: "an 8B-class local model may suffice" (cheapest deployable tier).
3. **Non-monotonic below the plateau** (7B 0.68 < 3B 0.74): n=30 noise (CI ~±0.1) + **family effects ≥ size effects** — do not claim a clean size law from this pilot.
4. **Language caveat:** this pilot is ENGLISH transcripts. Llama-3.1-8B is EN-centric; its zh performance must be re-checked on the collection-day Chinese data before any zh deployment choice.
5. Checkpointed scoring (partial_*.jsonl) now in place — kills no longer lose progress.
