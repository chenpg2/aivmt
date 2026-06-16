# AIVMT Device Bring-Up Runbook — flash + device↔server↔local-model + on-hardware QA

> The device-side code is complete and **build-verified** (`idf.py build` is GREEN, the host FSM test PASSes, and the server endpoint has a passing unit test).
> This checklist is the part that **requires your hands + real hardware**. The firmware fork lives in `xiaozhi-esp32/`; the server in `xiaozhi-esp32-server/`.

## Current state (device side, ready)
- Firmware: persona→OLED, scripted lines→display, BOOT-button control (Kconfig-gated), start/stop listening, transcript accumulation (from stt/tts), encounter export (HTTP POST). `SpSession` no longer sleeps — all hooks are wired in.
- Server: `POST /aivmt/encounter` receives and archives locally (de-identified, atomic write, path-traversal guard); local Ollama is already supported.
- **3 on-device values for you to set** (see below) — all are configuration / on-hardware tuning, not coding.

---

## A. Start the local server + point it at Ollama (one-time)

1. Confirm Ollama is running and the model is present:
   ```
   ollama serve   # if not already running
   ollama list | grep llama3.1:8b
   ```
2. Point the server LLM at local Ollama (the config slot already exists): `xiaozhi-esp32-server/main/xiaozhi-server/data/.config.yaml`
   ```
   LLM:
     type: ollama
     base_url: http://localhost:11434
     model_name: llama3.1:8b
   ```
   - The patient LLM is served by Ollama; ASR is FunASR; TTS is EdgeTTS.
3. Start the server (from the project virtualenv `xiaozhi-esp32-server/.venv`, Python 3.10):
   ```
   cd xiaozhi-esp32-server/main/xiaozhi-server && python app.py
   ```
   - WebSocket (device conversation) defaults to `:8000`; HTTP (OTA + `/aivmt/encounter`) defaults to `:8003`.
   - Note the host's LAN IP: `ipconfig getifaddr en0` (e.g. `<SERVER_LAN_IP>`).
4. Encounter archive directory: defaults to `data/aivmt_encounters/` (override with the `AIVMT_ENCOUNTER_DIR` environment variable).

## B. Configure the three firmware values (menuconfig)

```
cd xiaozhi-esp32 && source $HOME/esp/esp-idf/export.sh && idf.py menuconfig
```
In the menu (or by editing `sdkconfig` directly), set:
1. **BOOT-button control**: `CONFIG_AIVMT_PTT_ENABLE=y`, `CONFIG_AIVMT_PTT_GPIO=0` (the BOOT button on the bread-compact-wifi board is GPIO0). The demonstrated final control scheme uses a single BOOT button on GPIO0: a **short click** calls `ToggleChatState` to start/stop the VAD-driven conversation (there is **no wake word** — the AFE is VAD-only); a **1-second long-press** exports the encounter via `POST /aivmt/encounter`. Note that reusing the BOOT button can collide with the board's built-in OnClick handler, so be mindful of that conflict.
2. **Encounter-report URL**: `CONFIG_AIVMT_ENCOUNTER_POST_URL="http://<SERVER_LAN_IP>:8003/aivmt/encounter"`.
3. **Device → server connection**: set `server_url` (WebSocket) in `sp_config.h` to `ws://<SERVER_LAN_IP>:8000/xiaozhi/v1/`; fill in Wi-Fi through the device's first-boot provisioning flow.

> `participant_code` defaults to `"device01"` because the server rejects an empty code.

## C. Build + flash

```
cd xiaozhi-esp32 && source $HOME/esp/esp-idf/export.sh
idf.py build
idf.py -p /dev/cu.usbserial-1410 flash monitor
```
- Serial port: CH340 over `/dev/cu.usbserial-1410`; find it with `ls /dev/cu.*`. Flashing is done with `idf.py` / `esptool` over this port.
- `monitor` shows the logs (Ctrl+] to exit). On boot you should see `AIVMT.SpSession: enter Consent`.
- Rollback: the full-flash recovery image is `xiaozhi-s3-fullflash-backup-20260609.bin`.

## D. On-hardware QA (4 acceptance checks — this is the proof that "it runs")

| # | Acceptance item | How to test | Pass criterion |
|---|---|---|---|
| QA1 | **PTT, no echo (critical on a board with no hardware AEC)** | Hold PTT and speak while the device is playing TTS | After releasing, the ASR text does **not** contain the device's own speech recognized back in |
| QA2 | **OLED persona** | Run one encounter | The screen shows "[患者 Patient] <label> · <state>", and the state changes through the flow (Encounter/Feedback) |
| QA3 | **Cloud cut / offline** | Pull the network / firewall off the public internet, leaving only the LAN server | A full encounter still completes (answered by local Ollama) |
| QA4 | **Real-speech WER** | Record a real human encounter, compare the ASR text against the true speech | WER ≤ ~20% (exceeding it means the near-field / button scheme needs tuning) |

QA1–QA4 all green = the device can run one complete encounter. At the end of the encounter the device POSTs to `/aivmt/encounter`, and you'll see `<participant>__<case>__<ts>.json` in the server's `data/aivmt_encounters/`.

## E. Closed-loop verification (end-to-end)

1. The server is running (A).
2. Device boots → enter participant code → consent → case brief → **PTT encounter** (hold to speak, release to hear the patient's answer) → state the differential diagnosis → view feedback.
3. The encounter JSON for that run (transcript + telemetry) appears in the server's `data/aivmt_encounters/`.
4. Feed that JSON into the scoring pipeline (same schema as the faculty scoring set) to produce the system score.

---

## What to report back to me
- QA1–QA4 results (especially the measured WER value) → I'll use them to tune the PTT / audio timing (the `TODO(on-device)` markers in `application.integration.patch`).
- If build/flash errors out, send me the last ~30 lines of `idf.py build` / `flash`.

The device-side patches and components are already synced into `AIVMT/firmware/` (`components/aivmt_sp/`, `main_patches/application.integration.patch`, `server_patches/`); versions are traceable.
