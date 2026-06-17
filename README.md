# AIVMT — A Low-Cost Embodied Standardized Patient for Medical Education

An open, self-hostable platform that turns a **≈US$15–20 ESP32-S3 device** into a voice
**standardized patient (SP)**: a student takes a clinical history out loud, a **self-hosted
open-weight LLM** plays the patient *and* **automatically scores** the encounter, and those
automated scores are **validated against faculty**.

It is built for **LMIC / resource-limited medical schools**, where trained human SPs and faculty
grading time are the scarce, expensive bottleneck. AIVMT is the research vehicle for a submission to
the *npj Digital Medicine* collection **“Transforming Medical Education through Artificial
Intelligence.”**

> **Status — end-to-end working.** The device is flashed and has driven a full encounter on real
> hardware; the server `POST /aivmt/encounter` endpoint is live; and the **faculty validation study
> is complete**: the automated *overall* competency score agrees with the blinded 3-faculty
> consensus at **ICC(2,1) = 0.903 (95% CI 0.737–0.958)**, against an **inter-faculty ceiling of
> 0.765**. Every number in this repo traces to a registered artifact under [`results/`](results/).

<p align="center">
  <img src="docs/demo.jpg" alt="The AIVMT device: an ESP32-S3 (N16R8) module on a carrier board with an OLED patient display and a BOOT button, powered over USB-C on a desk." width="460">
  <br><em>The AIVMT device — a ≈US$15–20 ESP32-S3 (N16R8) standardized patient: OLED persona display + single-BOOT-button control, fully self-hosted.</em>
</p>

---

## How it works

<p align="center">
  <img src="docs/architecture.svg" alt="AIVMT system architecture: a student speaks to an ESP32-S3 device; audio streams over WebSocket to a self-hosted server (FunASR ASR → Ollama patient LLM → TTS); a long-press exports the encounter via POST /aivmt/encounter; the supporting-software layer scores the encounter and validates it against faculty (overall ICC 0.903)." width="880">
</p>

A student presses the device's **BOOT** button and asks the patient a question (the on-device
front-end is **VAD-only — no wake word**). The audio streams over Wi-Fi/WebSocket to the
**self-hosted server**, where **FunASR** transcribes it, an **Ollama** open-weight model answers
*in character* as the patient, and **TTS** speaks the reply back through the device. The board has
**no hardware AEC**, so turn-taking is half-duplex (you talk, then the patient talks) — deliberate,
and it keeps transcripts clean. A **1-second long-press** exports the full transcript + telemetry to
the server's `POST /aivmt/encounter` endpoint, which archives a de-identified encounter. The
**supporting-software** layer then scores that encounter (history checklist + SEGUE communication +
out-loud reasoning) into a `CompetencyScore` + `Feedback`, and the validation harness compares those
scores against blinded faculty ratings. Everything runs **on your LAN — no cloud fallback** — so
patient/persona content and student speech never leave the building.

---

## Components & repositories

**This repository is the project — everything in it is our own work.** AIVMT runs on two excellent
open-source bases, but we do **not** redistribute them; we keep only our additions here and show you
how to combine them with a fresh upstream checkout:

| # | Track | Our code (in **this** repo) | Combine with (upstream, clone separately) |
|---|-------|-----------------------------|--------------------------------------------|
| ② | **Infrastructure** (server) | [`firmware/server_patches/`](firmware/server_patches/) — `aivmt_handler.py` (the de-identified `POST /aivmt/encounter` endpoint) + route patch | [xinnan-tech/xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server) |
| ① | **Firmware** (device) | **our original work** — [`firmware/components/aivmt_sp/`](firmware/components/aivmt_sp/), the SP layer (~440 lines: state machine, BOOT-button turn-taking, OLED persona, telemetry, export) + [`firmware/main_patches/`](firmware/main_patches/) integration (~230 lines) | [78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) — base audio / display / Wi-Fi / protocol |
| ③ | **Supporting software** (analysis) | [`src/aivmt/`](src/aivmt/) + [`harness/`](harness/) — case authoring, persona, scoring pipeline, faculty portal, validation | — (entirely ours) |

> The **hardware package** (board, BOM, wiring, flash/QA runbook, rollback) is documented in
> [docs/HARDWARE.md](docs/HARDWARE.md) and [firmware/FLASH_AND_QA.md](firmware/FLASH_AND_QA.md).

---

## Deployment

**Deploy in this order:** ② Infrastructure → ① Firmware → ③ Supporting software. The device needs a
running server to talk to; the analysis tools are independent and can be set up any time. Each track
below is self-contained; follow the linked doc for full detail and troubleshooting.

Prerequisites across all tracks: **git**, a machine on the same **LAN** as the device (macOS/Linux),
and for the analysis tools the **[uv](https://docs.astral.sh/uv/)** Python manager.

---

### ② Infrastructure — the self-hosted server (deploy this first)

The server runs FunASR (ASR), an Ollama patient LLM, and TTS, and exposes the encounter endpoint.
Full guide: **[docs/SERVER.md](docs/SERVER.md)**.

```bash
# 0. Clone THIS repo first — our additions live here. Call its path $AIVMT:
#    git clone https://github.com/chenpg2/aivmt.git && export AIVMT="$PWD/aivmt"

# 1. Clone the upstream server, then add our /aivmt/encounter endpoint
git clone https://github.com/xinnan-tech/xiaozhi-esp32-server.git
cd xiaozhi-esp32-server
cp "$AIVMT/firmware/server_patches/aivmt_handler.py" main/xiaozhi-server/core/api/
git apply "$AIVMT/firmware/server_patches/http_server.route.patch"   # registers POST /aivmt/encounter
cd main/xiaozhi-server

# 2. Python 3.10 environment + dependencies
python3.10 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Install Ollama and pull the patient model (open-weight, local)
#    https://ollama.com/download
ollama pull qwen2.5:14b

# 4. Keep it LOCAL-ONLY: create data/.config.yaml selecting the Ollama LLM
#    (without this override the base config falls back to a CLOUD model — see docs/SERVER.md)
mkdir -p data
cat > data/.config.yaml <<'YAML'
selected_module:
  LLM: OllamaLLM
LLM:
  OllamaLLM:
    type: ollama
    model_name: qwen2.5:14b
    base_url: http://localhost:11434
YAML

# 5. Run it  → WebSocket :8000, HTTP :8003 (POST /aivmt/encounter)
python app.py
```

Note your machine's **LAN IP** (`ipconfig getifaddr en0` on macOS) — the device points at
`http://<SERVER_LAN_IP>:8003`. Configure the patient persona/case server-side as described in
[docs/SERVER.md](docs/SERVER.md).

---

### ① Firmware — flash the device

**The firmware SP layer is our own work** — the [`aivmt_sp`](firmware/components/aivmt_sp/) component
(~440 lines: SP state machine, BOOT-button turn-taking, OLED persona, telemetry, encounter export)
plus ~230 lines of integration — **developed on top of** the open-source
[`78/xiaozhi-esp32`](https://github.com/78/xiaozhi-esp32) base, which supplies the audio / display /
Wi-Fi / protocol stack. Deploying = drop our component into a fresh upstream checkout, apply our
integration patch, set the server URL, then build and flash. Hardware package:
**[docs/HARDWARE.md](docs/HARDWARE.md)** · flash + on-device QA runbook:
**[firmware/FLASH_AND_QA.md](firmware/FLASH_AND_QA.md)** · detailed integration:
**[firmware/INTEGRATION.md](firmware/INTEGRATION.md)**.

```bash
# 1. Install ESP-IDF v5.5.2 and source its environment
#    https://docs.espressif.com/projects/esp-idf/en/v5.5.2/esp32s3/get-started/
. $HOME/esp/esp-idf/export.sh

# 2. Clone the upstream base, drop in our component, apply our integration patch
#    ($AIVMT = your clone of THIS repo, as above)
git clone --recursive https://github.com/78/xiaozhi-esp32.git
cd xiaozhi-esp32
cp -r "$AIVMT/firmware/components/aivmt_sp" components/
git apply "$AIVMT/firmware/main_patches/application.integration.patch"

# 3. Target + configure: set the encounter POST URL to YOUR server's LAN IP
idf.py set-target esp32s3
idf.py menuconfig
#   → set CONFIG_AIVMT_ENCOUNTER_POST_URL = http://<SERVER_LAN_IP>:8003/aivmt/encounter
#   → confirm board profile (bread-compact-wifi) and PTT enable/GPIO

# 4. Build, flash, monitor (replace the port with yours; macOS example shown)
idf.py build flash monitor -p /dev/cu.usbserial-XXXX
```

On the device: **short BOOT click = talk**, **1-second long-press = export the encounter**. If a
build misbehaves, the device is fully recoverable from a saved flash image — see
[docs/HARDWARE.md](docs/HARDWARE.md#recovery--rollback). The full component-by-component
integration walk-through is in [firmware/INTEGRATION.md](firmware/INTEGRATION.md).

---

### ③ Supporting software — author cases, score encounters, validate

The Python package (this repo) authors cases, runs/scoring encounters, and validates against
faculty. Full guides: **[docs/USAGE.md](docs/USAGE.md)** · **[docs/FACULTY_SCORING.md](docs/FACULTY_SCORING.md)**.

```bash
# 1. Get this repo + create the environment (uv)
git clone https://github.com/chenpg2/aivmt.git
cd aivmt
uv sync --extra dev

# 2. Sanity check (mock LLM — no model or hardware needed)
uv run --extra dev pytest

# 3. Author a clinical case (teacher inputs case history, persona)
uv run --extra portal python -m aivmt.portal --port 8765            # → http://127.0.0.1:8765

# 4. Faculty scoring portal (blinded, by-case packet)
uv run --extra portal python -m aivmt.faculty_portal --port 8770    # → http://127.0.0.1:8770

# 5. Run an encounter end-to-end (text-only example; add --voice for audio)
uv run --extra serve python -m aivmt.session --case obgyn_ectopic_zh_01 --id demo01
```

Encounters are scored by the pipeline into a `CompetencyScore` + `Feedback`; faculty ratings feed
the validation harness (`check_science.sh` enforces that every reported number traces to
[`results/`](results/)). See [docs/USAGE.md](docs/USAGE.md) for case schema, persona knobs
(specialty / difficulty / disclosure / emotion / language), linting, and scoring details.

---

## Results — faculty validity (primary endpoint)

Automated overall score vs. blinded faculty **consensus** (n = 33 complete-case encounters, 3 OB/GYN
faculty, seed 42). Full table: [`results/phase_scoring_validity/summary.md`](results/phase_scoring_validity/summary.md).

| Measure | Value (95% CI) |
|---|---|
| **Overall** ICC(2,1) — system vs faculty consensus | **0.903** (0.737–0.958) |
| Overall ICC(2,k) | 0.949 (0.849–0.979) |
| Inter-faculty **ceiling** ICC(2,1) | 0.765 (0.533–0.884) |
| History completion ICC(2,1) | 0.931 (0.826–0.969) |
| End-encounter ICC(2,1) | 0.889 (0.573–0.959) |
| Bland–Altman bias (system − consensus) | −0.054, LoA [−0.228, 0.120] |

Communication sub-domains and out-loud *reasoning* are reported transparently as weaker
(see the summary) — the headline endpoint is overall competency agreement.

---

## Repository map (this repo)

```
aivmt/
├── README.md                 ← you are here
├── docs/                     ← English guides: SERVER, HARDWARE, USAGE, FACULTY_SCORING + architecture.svg
├── firmware/                 ← aivmt_sp ESP-IDF component (vendored) + integration/server patches + flash/QA
│   ├── components/aivmt_sp/  ←   the SP firmware layer (source of truth, host-testable)
│   ├── main_patches/         ←   how to wire it into xiaozhi-esp32 main/application.cc
│   └── server_patches/       ←   the /aivmt/encounter handler + route patch for the server
├── src/aivmt/                ← scoring, case schema, persona, case-authoring + faculty portals
├── harness/                  ← validation phases + contracts + evidence table
├── conf/ , configs/          ← Hydra configs (cases, models, scorers)
├── data/                     ← SYNTHETIC eval apparatus only (real study data is git-ignored)
├── results/                  ← registered metric artifacts (every paper number traces here)
├── paper/                    ← IMRAD manuscript skeleton (npj DM)
├── plan/                     ← protocol, pre-registration, TRIPOD-LLM checklist, study instruments
├── scripts/ , tests/         ← tooling + test suite
├── check_science.sh          ← governance gate (numbers ↔ artifacts; frozen eval set)
└── pyproject.toml            ← uv-managed package + optional extras (dev / serve / voice / portal)
```

## Documentation index

| Doc | For |
|---|---|
| [docs/SERVER.md](docs/SERVER.md) | Stand up the server, Ollama, and the `/aivmt/encounter` endpoint contract. |
| [docs/HARDWARE.md](docs/HARDWARE.md) | The hardware package: board, BOM, wiring, control scheme, rollback. |
| [firmware/FLASH_AND_QA.md](firmware/FLASH_AND_QA.md) | Step-by-step flash + on-device QA runbook. |
| [firmware/INTEGRATION.md](firmware/INTEGRATION.md) | Apply the `aivmt_sp` component to your own `xiaozhi-esp32` checkout. |
| [docs/USAGE.md](docs/USAGE.md) | Author a case, customize the persona, run an encounter, score it. |
| [docs/FACULTY_SCORING.md](docs/FACULTY_SCORING.md) | How a faculty rater uses the blinded scoring portal. |

---

## Design & language notes

- **Bilingual on purpose.** All code, docs, and usage instructions are in **English**. The
  **clinical study instruments** (case content, the faculty scoring manual under [`plan/`](plan/),
  the by-case scoring packet) are in **Chinese** — the validation study was run with **Chinese
  OB/GYN faculty on Chinese encounters**, and preserving that language is part of the validity
  claim, not an oversight. Every scorer prompt switches on `Case.language` (`en`/`zh`).
- **Reproducibility & data governance.** Only **synthetic** apparatus is tracked
  (`data/eval_transcripts/`, provenance `synthetic`). De-identified real study data — faculty
  ratings and encounter transcripts — is **git-ignored and not distributed**. `check_science.sh`
  enforces that every number in `paper/` resolves to an artifact in `results/`, and that the
  evaluation set stays frozen during scoring.

---

## License & citation

Research code accompanying a manuscript **submitted to** *npj Digital Medicine*.
© 2026 the AIVMT authors. **All rights reserved pending publication**; an open-source license will be
applied on acceptance. Our firmware layer (`firmware/components/aivmt_sp/`) builds on
[`xiaozhi-esp32`](https://github.com/78/xiaozhi-esp32) and our server endpoint
(`firmware/server_patches/`) builds on
[`xiaozhi-esp32-server`](https://github.com/xinnan-tech/xiaozhi-esp32-server), both open source —
their upstream licenses govern those bases. This repository redistributes neither base; it contains
only our own additions.

If you reference this work before the paper appears, please cite it as *“AIVMT: a low-cost embodied
standardized patient for medical education (manuscript submitted, 2026)”* and open an issue to
coordinate.

## Acknowledgements

Built on the excellent open-source [`xiaozhi-esp32`](https://github.com/78/xiaozhi-esp32) firmware
and [`xiaozhi-esp32-server`](https://github.com/xinnan-tech/xiaozhi-esp32-server), with on-device
ASR by **FunASR** and a self-hosted patient LLM via **Ollama**.
