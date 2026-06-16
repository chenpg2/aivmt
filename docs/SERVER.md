# AIVMT Server (Self-Hosted)

This document describes the **server side** of the AIVMT standardized-patient (SP)
platform: how to install it, run it, and how the ESP32-S3 device talks to it.

AIVMT runs entirely on a self-hosted machine on your LAN. The patient brain (LLM),
speech recognition (ASR), and the encounter archive all live locally. The design is
**local-only by policy** for patient confidentiality — the device never sends an
encounter to any cloud service, and the server provides no cloud fallback for the
encounter archive.

---

## 1. What the server is

The server is the open-source **`xiaozhi-esp32-server`** project plus one small,
**additive** AIVMT endpoint:

- **`xiaozhi-esp32-server`** is an `aiohttp`-based Python server. It runs:
  - a **WebSocket** service (real-time audio + chat with the device), and
  - a **simple HTTP** service (OTA, vision, and our AIVMT endpoint).
- **AIVMT addition:** a single route, **`POST /aivmt/encounter`**, implemented by
  `AivmtHandler`. It receives a finished, de-identified SP encounter from the device
  and archives it as one JSON file under a local directory. The scoring/analysis
  pipeline later reads those files directly. Nothing about this endpoint touches the
  network beyond the LAN.

The endpoint is **purely additive** — it does not modify any existing
`xiaozhi-esp32-server` behavior. It is registered alongside the stock routes.

### Where the AIVMT code lives

There are two copies of the handler, and they are kept **byte-identical**:

- **Source-of-truth mirror (in this repo):**
  `firmware/server_patches/aivmt_handler.py`
  and the route patch `firmware/server_patches/http_server.route.patch`.
- **Live server copy (where it actually runs):**
  `core/api/aivmt_handler.py` inside the `xiaozhi-esp32-server` checkout.

The route is wired in by adding the handler to `SimpleHttpServer` and registering
`POST` + `OPTIONS` for `/aivmt/encounter`. From the patch:

```python
from core.api.aivmt_handler import AivmtHandler
# ...
self.aivmt_handler = AivmtHandler(config)
# ...
app.add_routes(
    [
        web.post("/aivmt/encounter", self.aivmt_handler.handle_post),
        web.options("/aivmt/encounter", self.aivmt_handler.handle_options),
    ]
)
```

---

## 2. Prerequisites

The server is composed of local AI services plus the Python application. For the
**fully local** configuration that AIVMT runs:

| Component | Role | What runs locally |
| --- | --- | --- |
| **Ollama** + an open-weight chat model | The **patient LLM** (the SP "brain") | Yes — `http://localhost:11434` |
| **FunASR** (`SenseVoiceSmall`) | **ASR** (speech-to-text), bilingual zh/en | Yes — local model under `models/` |
| **SileroVAD** | Voice-activity detection | Yes — local model |
| **Python 3.10** virtual environment | Runs the `aiohttp` server | Yes |
| **EdgeTTS** | **TTS** (text-to-speech) | **Cloud** — see note below |

**Ollama.** Install Ollama and pull the open-weight chat model used as the patient.
The running AIVMT configuration uses **`qwen2.5:14b`**:

```bash
# install Ollama per https://ollama.com, then:
ollama pull qwen2.5:14b
ollama serve            # serves on http://localhost:11434
```

**FunASR / SileroVAD models.** The server uses local model files (e.g.
`models/SenseVoiceSmall` for ASR and the Silero VAD model). These live under the
`xiaozhi-esp32-server` `models/` directory; follow the upstream
`xiaozhi-esp32-server` model-download instructions to populate them.

**Python 3.10.** The live server runs under a Python **3.10** virtualenv
(`.venv`). Newer/older minors are not assumed to work.

> **Note — EdgeTTS is cloud TTS.** EdgeTTS calls Microsoft Edge's online
> text-to-speech service, so audio synthesis leaves the LAN. The **encounter data
> and the patient LLM stay local**, but for a *fully offline* deployment you should
> swap the TTS module to a local engine (configured under `selected_module.TTS`).
> EdgeTTS is the current default and is marked as temporary in the deployment config.

---

## 3. Install & run

All paths below are relative to the `xiaozhi-esp32-server` server directory
(the folder that contains `app.py`, i.e. `main/xiaozhi-server/`).

### 3.1 Create and activate the virtualenv

```bash
python3.10 -m venv .venv
source .venv/bin/activate          # macOS / Linux
```

### 3.2 Install dependencies

```bash
pip install -r requirements.txt
```

The requirements pin the relevant pieces, including `aiohttp`, `aiohttp_cors`,
`funasr`, `silero_vad`, `modelscope`, `torch`/`torchaudio`, and `numpy`. (EdgeTTS
and the Ollama HTTP client are likewise included via the requirements.)

### 3.3 Start the server

Make sure **Ollama is running** (`ollama serve`) and the ASR/VAD models are present,
then start the app:

```bash
python app.py
```

### 3.4 Ports that come up

On startup the server logs and binds:

| Service | Default port | URL shape |
| --- | --- | --- |
| WebSocket (device audio + chat) | **8000** | `ws://<SERVER_LAN_IP>:8000/xiaozhi/v1/` |
| Simple HTTP (OTA / vision / **AIVMT**) | **8003** | `http://<SERVER_LAN_IP>:8003/...` |

The AIVMT endpoint is therefore reachable at:

```
http://<SERVER_LAN_IP>:8003/aivmt/encounter
```

(The HTTP port comes from `server.http_port` in config, default `8003`; the
WebSocket port from `server.port`, default `8000`.)

---

## 4. The `/aivmt/encounter` endpoint contract

This section reflects `AivmtHandler` **exactly as implemented**. Do not assume any
field, flag, or behavior beyond what is listed here.

### Method & path

```
POST   /aivmt/encounter      -> archive a finished encounter
OPTIONS /aivmt/encounter     -> CORS preflight (handled, returns CORS headers)
```

### Request body (JSON object)

The body must be a JSON **object**. Recognized fields:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `participant_code` | string | **Yes** | De-identified participant token. Must match `^[A-Za-z0-9_-]{1,32}$`. |
| `case_id` | string | **Yes** | SP case identifier. Must match `^[A-Za-z0-9_-]{1,32}$`. |
| `transcript` | array | **Yes** | **Non-empty** list of turn objects; each turn must contain `role` and `text`. |
| `telemetry` | object | No | Free-form device telemetry; stored verbatim. Defaults to `{}` if omitted. |
| `meta` | object | No | Free-form metadata; stored verbatim. Defaults to `{}` if omitted. |

Notes derived from the code:

- `participant_code` and `case_id` are `str(...)`-coerced and `.strip()`-ed before
  validation.
- The validation regex is **`^[A-Za-z0-9_-]{1,32}$`** (1–32 chars; ASCII letters,
  digits, underscore, hyphen only). This both validates the token **and** guarantees
  it is a safe filename component (path-traversal guard).
- `transcript` must be a **non-empty `list`**, and **every** element must be an object
  containing both `role` and `text` keys. The handler does not constrain the *values*
  of `role`/`text` beyond their presence.

### What gets written (the archived record)

On success the server writes **one JSON file per encounter**. The stored record is:

```json
{
  "participant_code": "<validated token>",
  "case_id": "<validated token>",
  "telemetry": { /* body.telemetry or {} */ },
  "transcript": [ /* the posted turns */ ],
  "meta": { /* body.meta or {} */ },
  "received_at": "<server local time, %Y-%m-%dT%H:%M:%S%z>"
}
```

Storage details:

- **Archive directory:** `data/aivmt_encounters/` by default. Override with the
  environment variable **`AIVMT_ENCOUNTER_DIR`**.
- **Filename:** `{participant_code}__{case_id}__{unix_seconds}.json`. Safe by
  construction because both tokens already passed the regex.
- **Atomic write:** the server writes to a `*.json.tmp` file, then `os.replace()`s it
  into place, so a partially written file is never left in the archive.
- The JSON is written with `ensure_ascii=False, indent=2` (UTF-8, human-readable,
  non-ASCII preserved).

### Responses & status codes

| Situation | Status | JSON body |
| --- | --- | --- |
| Success | **200** | `{"success": true, "stored": "<filename>", "turns": <int>}` |
| Body is not valid JSON | **400** | `{"success": false, "message": "request body must be valid JSON"}` |
| Body is not a JSON object | **400** | `{"success": false, "message": "request body must be a JSON object"}` |
| Missing a required field | **400** | `{"success": false, "message": "missing required field: <name>"}` |
| `participant_code` fails regex | **400** | `{"success": false, "message": "participant_code must be a 1-32 char [A-Za-z0-9_-] token"}` |
| `case_id` fails regex | **400** | `{"success": false, "message": "case_id must be a 1-32 char [A-Za-z0-9_-] token"}` |
| `transcript` empty / not a list | **400** | `{"success": false, "message": "transcript must be a non-empty list of {role, text}"}` |
| A turn missing `role`/`text` | **400** | `{"success": false, "message": "each transcript turn must have 'role' and 'text'"}` |
| Disk/OS write failure | **500** | `{"success": false, "message": "server failed to archive encounter"}` |

Design intent (from the handler): **fail-loud on malformed input with 4xx, never
return 500 for a bad body.** A 500 is reserved for an actual filesystem/OS write
failure. All responses carry CORS headers.

### Example request

```bash
curl -X POST "http://<SERVER_LAN_IP>:8003/aivmt/encounter" \
  -H "Content-Type: application/json" \
  -d '{
        "participant_code": "device01",
        "case_id": "obgyn_ectopic_zh_01",
        "telemetry": {"duration_s": 312},
        "transcript": [
          {"role": "student", "text": "您好，哪里不舒服？"},
          {"role": "patient", "text": "我肚子疼。"}
        ],
        "meta": {"device": "esp32s3"}
      }'
```

Expected success response:

```json
{"success": true, "stored": "device01__obgyn_ectopic_zh_01__1781627145.json", "turns": 2}
```

---

## 5. How the device points at the server

The ESP32-S3 firmware POSTs the finished encounter to the server over the LAN.

- **Firmware config key:** `CONFIG_AIVMT_ENCOUNTER_POST_URL` (defined in the
  firmware's `aivmt_sp` `Kconfig`). Set it to the server's encounter endpoint:

  ```
  CONFIG_AIVMT_ENCOUNTER_POST_URL="http://<SERVER_LAN_IP>:8003/aivmt/encounter"
  ```

- **Server LAN IP:** use the IP of the machine running `app.py` on your local
  network. The HTTP service binds port **8003** by default. The device must be on the
  same LAN.

- **Local-only, no cloud fallback.** This is enforced by design on both sides:
  - The firmware's SP config is `local_only = true` and documents "no cloud fallback"
    for patient confidentiality.
  - The server endpoint only writes to the local archive directory; there is no remote
    upload path. If the local write fails, the server returns a 500 — it never falls
    back to any external destination.

The device-side WebSocket transport (for live audio/chat) points at the same machine,
e.g. `ws://<SERVER_LAN_IP>:8000/xiaozhi/v1/`.

---

## 6. Configuring the patient persona / case (server side)

The patient is realized by two server-side pieces: **which LLM** answers, and **which
persona prompt** that LLM is given. Both are set in the server's local deployment
override, `data/.config.yaml`, which the config loader merges **on top of** the base
`config.yaml` (the override wins on conflicts).

### 6.1 The patient LLM (Ollama)

The AIVMT deployment selects the local Ollama model as the brain:

```yaml
selected_module:
  VAD: SileroVAD
  ASR: FunASR          # local ASR (SenseVoiceSmall, zh/en)
  LLM: OllamaLLM       # local patient brain
  TTS: EdgeTTS         # cloud TTS (temporary; swap to local for full offline)
  Memory: nomem
  Intent: nointent

LLM:
  OllamaLLM:
    type: ollama
    model_name: qwen2.5:14b
    base_url: http://localhost:11434
```

### 6.2 The persona and the `case_id` mapping

The running persona is defined by:

- **`prompt_template: data/aivmt-sp-prompt.txt`** — the standardized-patient
  *framing* template. It instructs the model to play a standardized patient (answer
  only what is asked, speak in lay first-person, never break character, tolerate ASR
  errors, etc.) and contains placeholders such as `{{base_prompt}}` and
  `{{language}}`.
- **`prompt:`** (the inline persona in `data/.config.yaml`) — the **specific case
  details** that fill the template: a 28-year-old woman, ~6 weeks amenorrhea, right
  lower-quadrant pain with light dark-red vaginal bleeding, etc. This is the clinical
  content of the case the patient portrays.

**How `case_id` relates to this:** the device's default
**`default_case_id = "obgyn_ectopic_zh_01"`** (in the firmware `sp_config.h`) is the
**agreed label** identifying which case the server is currently running. The handler
stores this `case_id` verbatim on each archived encounter so the analysis pipeline can
attribute encounters to a case. The server runs **one active persona at a time** — the
persona configured in `data/.config.yaml` (the OB/GYN ectopic-pregnancy case). To run
a different case, change the server's `prompt`/`prompt_template`, and use the matching
`case_id` on the device.

> The `case_id` is **not** resolved against any per-case registry file on the server;
> it is metadata recorded on the encounter. Keeping the device's `default_case_id` and
> the server's configured persona in sync is an operational convention (the firmware
> comment notes the default `case_id` "matches the server's running persona").

---

## Cross-references

- Project overview: [`../README.md`](../README.md)
- Hardware / device setup: [`./HARDWARE.md`](./HARDWARE.md)
- End-to-end usage / running an encounter: [`./USAGE.md`](./USAGE.md)
