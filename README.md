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
> 0.765** — i.e. the model tracks the faculty consensus about as well as the faculty track each
> other. Every number in this repo traces to a registered artifact under [`results/`](results/).

---

## What's in this package

The four deliverables are all self-contained in this repository:

| # | Deliverable | Where | What it is |
|---|-------------|-------|------------|
| 1 | **Firmware** | [`firmware/`](firmware/) | The `aivmt_sp` ESP-IDF component — SP session state machine, single-BOOT-button turn-taking, OLED patient persona, per-turn telemetry, and encounter export — plus the integration patches that wire it into the `xiaozhi-esp32` base. |
| 2 | **Server / system** | [`firmware/server_patches/`](firmware/server_patches/) · [docs/SERVER.md](docs/SERVER.md) | The self-hosted `xiaozhi-esp32-server` (FunASR ASR + **Ollama** patient LLM + TTS + Silero VAD) plus our additive, de-identified `POST /aivmt/encounter` archival endpoint. |
| 3 | **Supporting software** | [`src/aivmt/`](src/aivmt/) · [`harness/`](harness/) | Case-authoring portal, persona compiler, the automated scoring pipeline (history checklist + SEGUE communication + out-loud reasoning), the faculty-scoring portal, and the validation harness (ICC / QWK / Bland–Altman / G-theory). |
| 4 | **Hardware package** | [docs/HARDWARE.md](docs/HARDWARE.md) · [`firmware/FLASH_AND_QA.md`](firmware/FLASH_AND_QA.md) | Board profile & bill of materials, wiring, the flash + on-device QA runbook, and a full-image rollback. |

---

## How it works

```
                          ┌──────────────────────────────────────────────────────────┐
   student speaks         │                  Self-hosted server (LAN)                  │
   (history-taking)       │            xiaozhi-esp32-server  +  /aivmt/encounter       │
        │                 │                                                            │
        ▼                 │   FunASR ASR ─▶ Ollama patient LLM ─▶ TTS (patient voice)  │
 ┌───────────────┐  Wi-Fi │        ▲                  │                    │           │
 │  ESP32-S3      │◀──────▶│        └───── transcript ─┘                    │           │
 │  ≈US$15–20     │   WS   │                                                ▼           │
 │  • BOOT button │        │                          encounter JSON ─▶ data/aivmt_encounters/
 │  • OLED persona│        └──────────────────────────────────────────────┬───────────┘
 │  • mic+speaker │                                                        │
 └───────────────┘                                                        ▼
   click = talk (VAD, no wake word)                         Automated scoring pipeline
   1-s long-press = export encounter ───────────────────▶   (history + SEGUE + reasoning)
                                                                          │
                                                                          ▼
                                                       CompetencyScore + Feedback
                                                                          │
                                                                          ▼
                                              Validation harness ◀── blinded faculty ratings
                                              ICC / QWK / Bland–Altman / G-theory
```

- **No wake word.** The on-device AFE is **VAD-only**; a short **BOOT-button click toggles the
  conversation** on/off. The board has **no hardware AEC**, so turn-taking is half-duplex (you talk,
  then the patient talks) — this is deliberate and keeps transcripts clean.
- **Local-only by design.** The device points at the self-hosted server and there is **no cloud
  fallback** — patient/persona content and student speech stay on the LAN.

---

## Quickstart

AIVMT has three legs. Stand them up in this order.

### 1. Server (the brain) — [docs/SERVER.md](docs/SERVER.md)
Run `xiaozhi-esp32-server` against a local **Ollama** model, with our encounter endpoint:
```bash
# in your xiaozhi-esp32-server checkout
.venv/bin/python app.py        # WebSocket :8000, HTTP :8003 (POST /aivmt/encounter)
```
> ⚠️ The patient LLM is selected by a local `data/.config.yaml` override (`OllamaLLM`). If that file
> is missing the base config falls back to a **cloud** model — see [docs/SERVER.md](docs/SERVER.md)
> to keep it local-only.

### 2. Device / firmware — [docs/HARDWARE.md](docs/HARDWARE.md) → [firmware/FLASH_AND_QA.md](firmware/FLASH_AND_QA.md)
Apply the `aivmt_sp` component to a `xiaozhi-esp32` checkout ([firmware/INTEGRATION.md](firmware/INTEGRATION.md)), point it at your server's LAN IP, then:
```bash
idf.py set-target esp32s3
idf.py build flash monitor -p /dev/cu.usbserial-1410
```

### 3. Supporting software — [docs/USAGE.md](docs/USAGE.md) · [docs/FACULTY_SCORING.md](docs/FACULTY_SCORING.md)
```bash
uv sync --extra dev                         # create the env
uv run --extra dev pytest                   # mock-LLM tests, no model needed
uv run --extra portal python -m aivmt.portal --port 8765         # author a clinical case
uv run --extra portal python -m aivmt.faculty_portal --port 8770 # faculty scoring portal
```

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

## Repository map

```
AIVMT/
├── README.md                 ← you are here
├── docs/                     ← English usage guides (SERVER, HARDWARE, USAGE, FACULTY_SCORING)
├── firmware/                 ← (1) aivmt_sp ESP-IDF component + integration patches + flash/QA runbook
│   ├── components/aivmt_sp/  ←     the SP firmware layer (source of truth, host-testable)
│   ├── main_patches/         ←     how to wire it into xiaozhi-esp32 main/application.cc
│   └── server_patches/       ← (2) the /aivmt/encounter handler + route patch for the server
├── src/aivmt/                ← (3) scoring, case schema, persona, case-authoring + faculty portals
├── harness/                  ←     validation phases + contracts + evidence table
├── conf/ , configs/          ←     Hydra configs (cases, models, scorers)
├── data/                     ←     SYNTHETIC eval apparatus only (real study data is git-ignored)
├── results/                  ←     registered metric artifacts (every paper number traces here)
├── paper/                    ←     IMRAD manuscript skeleton (npj DM)
├── plan/                     ←     protocol, pre-registration, TRIPOD-LLM checklist, study instruments
├── scripts/ , tests/         ←     tooling + test suite
├── check_science.sh          ←     governance gate (numbers ↔ artifacts; frozen eval set)
└── pyproject.toml            ←     uv-managed package + optional extras (dev / serve / voice / portal)
```

---

## Documentation index

| Doc | For |
|---|---|
| [docs/SERVER.md](docs/SERVER.md) | Stand up the self-hosted server, Ollama, and the `/aivmt/encounter` endpoint contract. |
| [docs/HARDWARE.md](docs/HARDWARE.md) | The hardware package: board, BOM, wiring, control scheme, rollback. |
| [firmware/FLASH_AND_QA.md](firmware/FLASH_AND_QA.md) | Step-by-step flash + on-device QA runbook. |
| [firmware/INTEGRATION.md](firmware/INTEGRATION.md) | Apply the `aivmt_sp` component to a `xiaozhi-esp32` checkout. |
| [docs/USAGE.md](docs/USAGE.md) | Author a case, customize the persona, run an encounter, score it. |
| [docs/FACULTY_SCORING.md](docs/FACULTY_SCORING.md) | How a faculty rater uses the blinded scoring portal. |

---

## Design & language notes

- **Bilingual on purpose.** All code, docs, and usage instructions are in **English**. The
  **clinical study instruments** (case content, the faculty scoring manual under
  [`plan/`](plan/), the by-case scoring packet) are in **Chinese** — the validation study was run
  with **Chinese OB/GYN faculty on Chinese encounters**, and preserving that language is part of the
  validity claim, not an oversight. Every scorer prompt switches on `Case.language` (`en`/`zh`).
- **Reproducibility & data governance.** Only **synthetic** apparatus is tracked
  (`data/eval_transcripts/`, provenance `synthetic`). De-identified real study data — faculty
  ratings and encounter transcripts — is **git-ignored and not distributed**. `check_science.sh`
  enforces that every number in `paper/` resolves to an artifact in `results/`, and that the
  evaluation set stays frozen during scoring.

---

## License & citation

This is research code accompanying a manuscript **under review** at *npj Digital Medicine*.
© 2026 the AIVMT authors. **All rights reserved pending publication**; an open-source license will be
applied on acceptance. The firmware under `firmware/components/aivmt_sp/` is an additive layer over
[`xiaozhi-esp32`](https://github.com/78/xiaozhi-esp32) and the server builds on
`xiaozhi-esp32-server`, both open source — their upstream licenses govern those bases.

If you reference this work before the paper appears, please cite it as *“AIVMT: a low-cost embodied
standardized patient for medical education (manuscript under review, 2026)”* and open an issue to
coordinate.

## Acknowledgements

Built on the excellent open-source [`xiaozhi-esp32`](https://github.com/78/xiaozhi-esp32) firmware
and `xiaozhi-esp32-server`, with on-device ASR by **FunASR** and a self-hosted patient LLM via
**Ollama**.
