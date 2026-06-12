# AIVMT firmware (deep-customized fork of xiaozhi-esp32)

Device-side SP layer. **Do not write from scratch** — fork `78/xiaozhi-esp32` and customize only
the SP-specific parts. Base board profile: `bread-compact-wifi` (matches our unit). Rollback =
`../../xiaozhi-s3-fullflash-backup-20260609.bin`.

Feature scope is requirements-driven — see `../../plan/firmware-spec.md` (traceability matrix).

## MVP (W2)
1. SP **session state machine**: consent/ID → case brief → encounter → out-loud reasoning probe → feedback → end.
2. **Push-to-talk** turn-taking (also mitigates the no-AEC echo problem on this board).
3. **Patient persona** on the OLED (e.g. "Patient: 58M, chest pain"); device speaks as the patient.
4. **Telemetry**: per-turn timestamps, # student questions, session duration, voluntary repeats → emit with transcript.
5. **Local-only routing** to the self-hosted server; confidentiality/offline indicator.
6. **De-identified participant code** entry for logging + academic integrity.

## Setup (to do)
- [ ] Install ESP-IDF; `git clone` the fork; select `bread-compact-wifi` board.
- [ ] Point chat/OTA endpoint at the self-hosted `xiaozhi-esp32-server`.
- [ ] Implement the SP session state machine + PTT + telemetry hooks.
- [ ] Bilingual prompts/UI (en primary, zh supported) driven by case language.
