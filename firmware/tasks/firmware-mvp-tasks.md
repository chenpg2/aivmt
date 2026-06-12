# Firmware MVP — goals & acceptance criteria (feed for goal-driven build)

Each task = one goal with an acceptance criterion. Order respects dependencies. Tasks map to
`../../../plan/firmware-spec.md` (requirement) and the `aivmt_sp` files in this scaffold.

> Prereq G0 — Fork & build baseline
> - **Goal:** fork `78/xiaozhi-esp32`, add `components/aivmt_sp`, build for `bread-compact-wifi`.
> - **Accept:** `idf.py build` succeeds with the empty `aivmt_sp` component linked.

## G1 — Session state machine (`sp_session.*`)  [req: clinical skills / standardization]
- **Goal:** implement the full transition table (ARCHITECTURE.md) with per-state entry actions.
- **Accept:** logged transitions Consent→CaseBrief→Encounter→ReasoningProbe→Feedback→Ended on a
  scripted event sequence; `kAbort` from any state → Aborted.

## G2 — Push-to-talk turns (`sp_ptt.*` + application hook)  [req: validity + no-AEC mitigation]
- **Goal:** GPIO button starts/stops a student turn; ASR is gated so it never listens during TTS.
- **Accept:** holding the button captures one clean utterance; releasing ends the turn; no echo
  self-trigger while the patient voice is playing.

## G3 — Patient persona display (`sp_persona.*`)  [req: embodiment / H2]
- **Goal:** show the patient identity ("Patient: 58M, chest pain") + current state on the OLED.
- **Accept:** persona label + state visible throughout the encounter (zh + en).

## G4 — Behavioral telemetry (`sp_telemetry.*`)  [req: H2 engagement composite]
- **Goal:** count student questions + voluntary repeats; measure duration via esp_timer.
- **Accept:** telemetry emitted with the encounter; values match a hand-counted test run.

## G5 — Local-only transport + encounter export (`emit_encounter` hook)  [req: confidentiality]
- **Goal:** send transcript + telemetry to the self-hosted server only; no cloud fallback path.
- **Accept:** with internet to the cloud blocked, a full encounter still completes + exports locally.

## G6 — De-identified participant code (`sp_participant.*`)  [req: academic integrity]
- **Goal:** prompt for a short de-identified code at consent; attach to the encounter; reject PII.
- **Accept:** "P017" accepted; long/PII-like inputs rejected; code present in the export.

## G7 — Bilingual prompts/UI (en primary, zh supported)  [req: equity / collection scope]
- **Goal:** all device-spoken/displayed prompts switch on `SpConfig.language` (default English).
- **Accept:** a full session runs end-to-end in both en and zh.

> Out of scope (do NOT build now): animated avatar, on-device vision, free-dialogue/AEC mode,
> multi-case browser. (See firmware-spec.md §A "explicitly out of scope".)
