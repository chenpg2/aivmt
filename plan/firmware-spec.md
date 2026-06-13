# Firmware Spec — requirements-driven (deep-customized fork of xiaozhi-esp32)

> Principle: **every device-side feature traces to a collection requirement and/or a pre-registered
> measure.** No gold-plating. Base = fork of `78/xiaozhi-esp32` (reuse wake/ASR↔server/TTS/MCP/OTA);
> we change only the SP-specific layer. This matrix → the paper's "system design rationale".
> Companions: `protocol-v0.1.md`, `preregistration-v0.1.md`, `w2-build-spec.md`.

## A. Traceability matrix — collection requirement → device feature → server counterpart
| npj-collection requirement / our measure | Device-side (firmware) feature | Server-side counterpart | MVP (W2)? |
|---|---|---|---|
| **Clinical skills / case-based learning** | OSCE-style session flow: brief → patient encounter → out-loud reasoning probe → feedback; on-device **case selection** | Case persona + history via prompt + RAG; withholds info | ✅ |
| **Assessment fairness & validity** | **Standardized, deterministic** encounter: identical opening, fixed structure/timing; **push-to-talk** clean turn segmentation → cleaner transcripts | Standardized scoring rubric (SEGUE + checklist) | ✅ |
| **Feedback mechanisms & competency measurement** | Post-encounter **feedback rendering** (score + structured feedback) via OLED + voice; capture reasoning-probe answer | SEGUE/checklist/reasoning scoring + feedback generation | ✅ (basic) |
| **Impact on learning & engagement (H2)** | Patient **persona/state display** (not a generic assistant); **behavioral telemetry**: time-on-task, # questions asked, # voluntary practice reps | Derive engagement composite from logs | ✅ telemetry; persona basic |
| **Patient confidentiality / governance** | **Local-only server path** (no cloud), on-device/local logging, visible **"local/offline" indicator** | Local storage, de-identified IDs, no third-party calls | ✅ (core novelty: edge/confidentiality) |
| **Academic integrity** | Consent/ID screen; session logging keyed to a **de-identified participant code** | Audit log of encounters | ✅ (lightweight) |
| **Equity / access (cost)** | **Keep the ultra-low-cost board** (see §C) — preserves the cost claim | Open-weight local model, shared server | ✅ (the cost narrative) |
| **Human-in-the-loop / faculty review** | Reliable **encounter recording + export** | Export bundle for blinded faculty scoring | ✅ |

**Explicitly out of scope (avoid gold-plating):** animated avatar, on-device vision, multi-language UI,
elaborate menus. None trace to a requirement within our scope/timeline.

## B. Firmware MVP (W2) — minimum to run a valid, standardized, study-grade encounter
1. **SP session state machine**: consent/ID → case brief → encounter (history-taking) → reasoning probe → feedback → end.
2. **Push-to-talk** turn-taking (also the no-AEC mitigation — see §C).
3. **Patient persona** on OLED (label/state, e.g., "Patient: 58F, chest pain"); device speaks as the patient.
4. **Telemetry hooks**: per-turn timestamps, # student turns/questions, session duration, voluntary-repeat events → emitted to server with the transcript.
5. **Local-only routing**: point OTA/chat endpoint at our self-hosted server; no cloud fallback; confidentiality indicator.
6. **Participant code** entry/selection (de-identified) for logging + integrity.

Nice-to-have (post-MVP): richer feedback UI, multi-case library browser, free-dialogue (AEC) mode.

## C. Board / audio decision (resolved by a requirement, not preference)
- Current board `bread-compact-wifi` has **no hardware AEC** → echo would corrupt ASR (a measured outcome).
- **Decision: keep the low-cost board + use push-to-talk half-duplex** (student speaks only while TTS
  is silent) → echo problem largely avoided **without buying an AEC board**. This *also strengthens
  the equity/ultra-low-cost claim* (an ESP32-S3-BOX3 with AEC is pricier).
- AEC board (ESP32-S3-BOX3 / Korvo) = **optional later** only if a naturalistic free-dialogue
  condition is wanted (could even become a secondary study variable — but out of scope for now).

## D. Base & toolchain
- Fork `78/xiaozhi-esp32`; start from the `bread-compact-wifi` board profile (matches our unit).
- ESP-IDF toolchain (W2 setup); keep our 16MB backup as the rollback.
- Server side = self-hosted `xiaozhi-esp32-server` (separate track in `w2-build-spec.md`).

## E. Decisions needed to start building (defaults in **bold**; reply 继续 to accept)
1. **Encounter language**: **English (primary), Chinese supported** — drives ASR/TTS/scoring prompts; confirm the per-cohort mix (and which SEGUE language version) with the collaborator.
2. **Repo/project name**: **`mededu-sp/`** under this workspace (firmware fork + server + scoring as sibling packages).
3. **Confirm**: keep low-cost board + push-to-talk (no AEC board purchase) for the study. **Recommended yes.**
