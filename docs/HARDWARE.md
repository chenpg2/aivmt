# Hardware Package

This is the **hardware leg** of AIVMT: what to buy, how it is wired, the on-device control scheme,
and how to recover the unit. For the step-by-step flashing + acceptance procedure see
[../firmware/FLASH_AND_QA.md](../firmware/FLASH_AND_QA.md); for building the firmware image see
[../firmware/INTEGRATION.md](../firmware/INTEGRATION.md).

The design goal is an SP terminal that an LMIC medical school can reproduce for the price of a
textbook — so everything below is commodity, off-the-shelf, and self-hosted.

## Bill of materials (≈ US$15–20)

| Part | What we used | Notes |
|------|--------------|-------|
| MCU module | **ESP32-S3 (N16R8)** — 16 MB flash, 8 MB PSRAM | The PSRAM is needed for audio buffers. |
| USB–UART bridge | **CH340** | Exposes a serial port for flashing; on macOS it enumerates as `/dev/cu.usbserial-XXXX` (ours: `/dev/cu.usbserial-1410`). |
| Display | small **I²C OLED** (SSD1306-class) | Shows the patient persona + session state. |
| Microphone | I²S MEMS mic | Captures the student's speech. |
| Speaker | small speaker + amp | The patient's voice (TTS) plays here. |
| Button | the on-board **BOOT** button (GPIO0) | The entire UX runs on this one button — see below. |
| Power | USB 5 V | A phone charger or laptop port is enough. |

> **Board profile.** The firmware is built for the `bread-compact-wifi` profile, which matches this
> unit. Other ESP32-S3 audio boards work too — pick the matching profile in `idf.py menuconfig` and
> adjust GPIOs.

## Control scheme — one button

The board has **no hardware AEC** (acoustic echo cancellation) and the on-device front-end is
**VAD-only (no wake word)**. Rather than fight echo with free-form duplex audio, AIVMT uses simple,
robust **half-duplex, push-to-engage** turn-taking on a single button:

| Action | Effect |
|--------|--------|
| **Short click** (BOOT / GPIO0) | `ToggleChatState` — start or stop the voice conversation. Speak your question; the patient answers; click again (or just pause) to take turns. |
| **1-second long-press** (BOOT / GPIO0) | **Export the encounter** — POSTs the transcript + telemetry to the server's `/aivmt/encounter` endpoint. |

The long-press is layered *on top of* the base firmware's existing BOOT-click handler, so the two
coexist. On our unit a capacitive **touch** pad (GPIO47) and **volume** keys (GPIO39/40) also exist,
but they were hard to locate on a breadboard build — **BOOT-only is the reliable UX** and what the
demonstrations used.

## Wiring

For the `bread-compact-wifi` profile the mic (I²S), speaker (I²S/DAC), and OLED (I²C) follow the
standard `xiaozhi-esp32` pin map for that board — do not re-invent it; use the board profile and let
the base firmware drive the peripherals. AIVMT adds **no new wiring**: the SP layer reuses the
existing display, audio, and BOOT button. The only values you set are software
(`idf.py menuconfig`): the server URL, push-to-talk enable/GPIO, and audio-turn timing — see
[../firmware/FLASH_AND_QA.md](../firmware/FLASH_AND_QA.md).

## Flashing (overview)

Full procedure + QA gates: **[../firmware/FLASH_AND_QA.md](../firmware/FLASH_AND_QA.md)**. In short:

```bash
idf.py set-target esp32s3
idf.py menuconfig          # board profile, server URL, PTT enable/GPIO
idf.py build flash monitor -p /dev/cu.usbserial-1410
```

## Recovery / rollback

A full 16 MB flash image of the known-good factory state was captured before any AIVMT flashing:
`xiaozhi-s3-fullflash-backup-20260609.bin` (kept outside this repo; `*.bin` is git-ignored so large
images are never committed). To restore the device to that image:

```bash
esptool --port /dev/cu.usbserial-1410 write_flash 0x0 xiaozhi-s3-fullflash-backup-20260609.bin
```

This makes every flashing step reversible — if a build misbehaves, roll back and retry.

## On-device QA gates

Four acceptance checks must pass on real hardware (full detail in the runbook):

1. **Push-to-talk / no echo** — one clean utterance per turn; the device does not self-trigger while
   the patient voice is playing (the no-AEC check).
2. **OLED persona** — the patient persona + session state stay visible throughout (zh/en).
3. **Offline** — with the cloud blocked, a full encounter still completes against the local server.
4. **Real-speech WER** — word-error rate on real student speech is within the target (≤ ~20%).

---

### Cross-references
[../README.md](../README.md) · [SERVER.md](SERVER.md) · [USAGE.md](USAGE.md) ·
[../firmware/FLASH_AND_QA.md](../firmware/FLASH_AND_QA.md) ·
[../firmware/INTEGRATION.md](../firmware/INTEGRATION.md)
