# AIVMT firmware architecture

Our firmware is a **deep-customized fork of `78/xiaozhi-esp32`**. We do NOT rewrite the base
(wake/ASR↔server/TTS/MCP/OTA/display are reused). We add **one ESP-IDF component, `aivmt_sp`**,
that drives the standardized-patient OSCE session on top of the base `Application`.

## Where our layer sits
```
xiaozhi base firmware (fork)
   Application (audio loop, protocol, display, MCP)         <- upstream, reused
        │  hooks (show_text / speak / start|stop listening / emit_encounter)
        ▼
   components/aivmt_sp   <- OURS (this scaffold)
     ├─ SpSession      session state machine (the OSCE flow)
     ├─ PushToTalk     half-duplex turn control (also no-AEC mitigation)
     ├─ TelemetryRecorder  behavioral metrics (H2 engagement composite)
     ├─ PatientPersona render patient identity/state to OLED
     └─ ParticipantCode de-identified code (logging + academic integrity)
```

## Session state machine (the OSCE flow)
```
 Idle ──Start──▶ Consent ──ConsentGiven──▶ CaseBrief ──BriefDone──▶ Encounter
                                                                        │
                                                  (push-to-talk turns)  │ ProbeStart
                                                                        ▼
   Ended ◀──FeedbackShown── Feedback ◀──ProbeAnswered── ReasoningProbe
     ▲                                                                  
     └────────────────────── (any) ──Abort──▶ Aborted ─────────────────┘
```

## Requirements traceability
Every component maps to a row in `../../plan/firmware-spec.md` (collection requirement → feature).
The session is **standardized + deterministic** (assessment validity/fairness); **local-only**
transport (patient confidentiality); telemetry feeds H2; participant code supports integrity.

## Build target
Base board profile: `bread-compact-wifi`. Rollback image: `../../xiaozhi-s3-fullflash-backup-20260609.bin`.
See `INTEGRATION.md` for how to merge this component into the fork and build with `idf.py`.
