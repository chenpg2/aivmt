# Driving the firmware build with `/goal`

`/goal <condition>` keeps Claude working across turns until a fast evaluator confirms the
condition. **The evaluator judges only from what Claude shows in the transcript — it does not run
commands or read files itself.** So every condition must be tied to a command Claude runs whose
output appears in the conversation (a build/test that prints PASS), not to a hardware behavior.

Requires Claude Code ≥ v2.1.139, a trusted workspace, hooks enabled. Pair with **auto mode** so
each goal turn runs unattended. Always add an `or stop after N turns` safety clause.

## The verifiable target we wired
`firmware/test_host/` builds the `SpSession` state machine on the host (no ESP-IDF, no hardware)
and prints `ALL TESTS PASS` only when the transition table is implemented. It is **currently RED
on purpose** — that is what `/goal` converges on.

```bash
make -C AIVMT/firmware/test_host test   # prints ALL TESTS PASS when sp_session.cc is done
```

## Ready-to-paste goals (in order)

**Goal 1 — implement the SP state machine (fully host-verifiable, no hardware):**
```
/goal Running `make -C AIVMT/firmware/test_host test` prints "ALL TESTS PASS" and exits 0, with the full SpSession transition table implemented in AIVMT/firmware/components/aivmt_sp/sp_session.cc per AIVMT/firmware/ARCHITECTURE.md. Show the make output each turn. Constraints: only edit files under components/aivmt_sp/; do NOT modify test_host/test_fsm.cc or any public header API. Or stop after 20 turns.
```

**Goal 2 — finish the MVP logic + no leftover stubs (host-verifiable parts):**
```
/goal `make -C AIVMT/firmware/test_host test` prints "ALL TESTS PASS" AND `grep -rn "TODO(goal:" AIVMT/firmware/components/aivmt_sp` prints no matches, with tasks G1, G4, G6 in AIVMT/firmware/tasks/firmware-mvp-tasks.md implemented (state machine, telemetry, participant code). Show the make output and the grep result each turn. Do not change public header APIs or the host test. Or stop after 40 turns.
```

**Goal 3 — ESP-IDF build green (only after ESP-IDF is installed and the fork is set up):**
```
/goal `idf.py build` for the bread-compact-wifi target exits 0 with the aivmt_sp component linked and the hooks from firmware/main_patches/application_hooks.md wired into main/application.cc. Show the build tail each turn. Do not modify upstream base files except the documented hook insertions. Or stop after 30 turns.
```

## What `/goal` CANNOT verify → manual on-device QA
These are hardware behaviors the evaluator can't see in the transcript; verify them by hand on the
device (and record results for the paper's Methods):
- **G2** push-to-talk captures one clean utterance; no echo self-trigger while TTS plays (no-AEC check).
- **G3** patient persona + state visible on the OLED throughout (zh + en).
- **G5** with cloud blocked, a full encounter still completes + exports to the local server.
- Audio quality / ASR WER on real student speech.

## Notes
- Prereq for Goal 3 is task **G0** in `tasks/firmware-mvp-tasks.md` (fork + ESP-IDF + component linked).
- Goal 1/2 need only a C++17 compiler (already present) — start there; they exercise the core logic
  before any hardware is involved.
