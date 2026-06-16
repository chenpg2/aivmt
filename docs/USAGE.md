# AIVMT — Usage Guide

AIVMT (AI Virtual Medical Teacher) is an embodied, low-cost voice **standardized
patient (SP)** for medical education. A single self-hosted open-weight LLM plays
the patient behind an ESP32-S3 device; the encounter is recorded and an automated
pipeline produces a competency score plus formative feedback. Bilingual: English
(`en`) is primary, Chinese (`zh`) is supported, and every prompt switches on the
case's `language`.

This guide is end-to-end: install → author a case → customize the SP persona →
lint the case → run an encounter → see where it is stored and how it is scored.

> **Conventions in this guide**
> - All shell commands are run from the repository root.
> - Replace `<SERVER_LAN_IP>` and `<port>` with the real LAN address/port of the
>   machine running a portal when you share it with colleagues on the same Wi-Fi.
> - The double-click launchers (`.command` files) at the repo root wrap the exact
>   commands shown below for non-technical users on macOS.

---

## 1. Install

AIVMT uses [`uv`](https://docs.astral.sh/uv/). Dependencies are split into
optional extras so each role installs only what it needs (`pyproject.toml`):

| Extra | Pulls in | Used for |
|-------|----------|----------|
| `dev` | `pytest` | running the unit tests |
| `serve` | `openai` | OpenAI-compatible client for a local vLLM/Ollama endpoint |
| `voice` | `faster-whisper`, `sounddevice` | local bilingual ASR + microphone capture |
| `portal` | `fastapi`, `uvicorn`, `httpx` | the case-entry and faculty-scoring web portals |

Create the environment and run the tests (the test suite uses a mock LLM, so no
model is required):

```bash
uv sync --extra dev
uv run --extra dev pytest
```

Install additional extras as needed, e.g. for running an encounter against a
local model with voice and for the portals:

```bash
uv sync --extra serve --extra voice --extra portal --extra dev
```

You can also pass extras per-invocation with `uv run --extra <name> ...` (this is
what the launchers do), so a full pre-sync is optional.

There are **no `console_scripts`**; every entry point is a module invoked with
`python -m aivmt.<module>`.

---

## 2. Authoring a clinical case

### 2.1 The case model

A case is a YAML file under `conf/case/` (one file per case; the file's
`case_id` is also used as its filename when saved through the portal). Two layers
back a case:

- `aivmt.case_schema.ClinicalCase` — the formal, typed, immutable authoring
  schema (Stream B data layer).
- `aivmt.schemas.Case` — the flat legacy record the scoring pipeline consumes.
  Every `ClinicalCase` can project to a `Case` via `to_case()`, so the authoring
  schema stays backward compatible with `aivmt.cases.load_case` and the pipeline.

**Fields of `ClinicalCase`** (`src/aivmt/case_schema.py`):

| Field | Type | Notes |
|-------|------|-------|
| `case_id` | str | required; lowercase letters/digits/underscore, must start with a letter (e.g. `obgyn_aub_zh_02`); becomes the filename |
| `version` | str | required; portal default `1.0.0` |
| `language` | `en` \| `zh` | required |
| `specialty` | str | required (e.g. `obgyn`) |
| `title` | str | required |
| `demographics` | `Demographics` | `age`, `sex` required; `occupation`, `marital_status` optional |
| `chief_complaint` | str | the one symptom the SP opens with |
| `hpi` | `HPI` | OPQRST-style: `onset`, `location`, `duration`, `character`, `aggravating`, `relieving`, `timing`, `severity`, `associated_symptoms[]` (all optional) |
| `pmh`, `medications`, `allergies`, `family_history`, `social_history` | list[str] | required keys (may hold placeholders) |
| `pertinent_negatives` | list[str] | optional; load-bearing negatives ("no fever") the SP must disclose truthfully when asked |
| `hidden_info` | list[`HiddenInfoItem`] | each item is `info_id` + `content` + `trigger`; revealed **only** when the trigger question is asked |
| `red_herrings` | list[`RedHerring`] | `herring_id` + `content` + optional `note`; surfaced only at higher difficulty |
| `obgyn` | `OBGYNBlock` | optional specialty block: `lmp`, `menstrual_history`, `obstetric_history`, `contraception`, `sexual_history` |
| `history_checklist` | list[`ChecklistItem`] | required, ≥1 item; each is `item_id` + `text` + `weight` (default `1.0`, range `[0, 10]`); `item_id`s must be unique |
| `emotional_state` | str | the SP's emotional overlay |
| `disclosure_profile` | str | the case's baseline disclosure tendency |
| `persona` (`persona_text`) | str | free-text persona, used verbatim by the legacy path |
| `difficulty` (`clinical_complexity`) | `simple` \| `moderate` \| `complex` | a descriptive **clinical-complexity** label only |

> **Two different "difficulty" notions — don't conflate them.**
> - The case file's `difficulty` is a *clinical-complexity* label (`simple` /
>   `moderate` / `complex`), kept for legacy compatibility.
> - The SP's *behavioral* difficulty (`easy` / `standard` / `hard`) is **not**
>   stored in the case. It is a compile-time parameter of `aivmt.persona`
>   (see §3).

**Unfinished fields:** any required clinical field that has not yet been
collaboratively authored carries the literal sentinel `TODO_COLLAB`. The schema
treats placeholders as *structurally valid*; the linter reports them as
**warnings** (§4). Clinical content is never invented.

### 2.2 Writing / loading a case YAML

Author by hand or copy an existing file in `conf/case/` as a template (e.g.
`conf/case/obgyn_ectopic_zh_01.yaml`, `conf/case/example_chestpain_en.yaml`).
A minimal but complete case looks like:

```yaml
case_id: obgyn_aub_zh_02
version: "1.0.0"
title: Heavy menstrual bleeding with prolonged periods
language: en
specialty: obgyn
difficulty: moderate

demographics:
  age: "34"
  sex: female
  occupation: TODO_COLLAB        # placeholder -> lint WARNING, not an error
  marital_status: married

chief_complaint: Periods have been much heavier for three months

hpi:
  onset: about three months ago
  duration: each period now lasts 8-9 days
  character: heavy, with clots
  severity: TODO_COLLAB
  associated_symptoms: []

pmh: []
medications: [TODO_COLLAB]
allergies: [TODO_COLLAB]
family_history: [TODO_COLLAB]
social_history: [TODO_COLLAB]
pertinent_negatives: [no fever, no bleeding between periods]

hidden_info:
  - info_id: hi_anemia
    content: I have felt tired and short of breath climbing stairs lately.
    trigger: asks about fatigue / shortness of breath (hx_anemia)

emotional_state: colloquial, brief, a little worried.
disclosure_profile: States only the main symptom to open; answers only what is asked.
persona: |
  You are a 34-year-old woman whose periods have become much heavier...

history_checklist:
  - {item_id: hx_onset, text: Asks when the heavier bleeding started, weight: 1.0}
  - {item_id: hx_amount, text: Asks about amount/clots/pad count, weight: 1.0}
  - {item_id: hx_anemia, text: Asks about fatigue/shortness of breath, weight: 1.0}
```

Load and validate it programmatically:

```python
from aivmt.case_schema import load_clinical_case   # full ClinicalCase
from aivmt.cases import load_case                   # flat Case for the pipeline

clinical = load_clinical_case("conf/case/obgyn_aub_zh_02.yaml")
case = load_case("conf/case/obgyn_aub_zh_02.yaml")
```

Both loaders read YAML via OmegaConf and raise a clear `source:field — why` error
on any structural/type violation.

### 2.3 The case-authoring portal (recommended for teachers)

The case-entry portal is a local FastAPI web app that lets a clinician fill in a
case in the browser, validate it, preview the compiled SP prompt, and save a
schema-correct YAML — **no command line and no LLM** required (validation and
preview are fully local and deterministic).

**Launch (exact command run by `启动病历录入.command`):**

```bash
uv run --extra portal python -m aivmt.portal --port 8765
```

- Default host: `127.0.0.1` (local only). Default port: `8765`.
- Open `http://localhost:8765` (the launcher opens the browser automatically).
- CLI flags (`python -m aivmt.portal`): `--host` (default `127.0.0.1`),
  `--port` (default `8765`), `--case-dir` (default: `$AIVMT_CASE_DIR` or
  `conf/case`). The portal **fails loud** if the case directory does not exist —
  it never silently creates or relocates the case library.

To let colleagues on the same Wi-Fi reach the portal, bind all interfaces:

```bash
uv run --extra portal python -m aivmt.portal --host 0.0.0.0 --port 8765
# then share: http://<SERVER_LAN_IP>:8765
```

**What a teacher inputs** (the page maps directly onto `ClinicalCase`):
metadata (`case_id`, `title`, `language`, `specialty`, `difficulty`),
demographics, chief complaint, the HPI dimensions, the history lists (PMH,
medications, allergies, family/social history), pertinent negatives, the
**hidden-info** rows (each with its trigger question), optional red herrings, the
optional OB/GYN block, the emotional state and disclosure profile, the free-text
persona, and the **history checklist** (the per-item scoring rubric).

Behind the form (`src/aivmt/portal/`):

- `POST /api/validate` — normalizes the draft and validates it; blank optional
  clinical fields become `TODO_COLLAB`, never invented content. Returns
  `ok`/`errors`/`warnings` with teacher-friendly messages.
- `POST /api/preview` — deterministically compiles the persona for **all**
  difficulty levels (`easy`/`standard`/`hard`) so the author can see exactly what
  the SP will be told. This never calls an LLM.
- `POST /api/cases` — atomic save. Invalid drafts return `422` and **nothing is
  written**; an existing `case_id` returns `409` unless overwrite is requested.
- `GET /api/cases` / `GET /api/cases/{case_id}` — list/inspect saved cases with
  their lint status.

---

## 3. Persona customization (`aivmt.persona`)

The persona compiler turns a `ClinicalCase` into the SP system prompt. It is the
personalization engine and is **deterministic**: identical
`(case, difficulty, language)` inputs always produce byte-identical output.

**Knobs actually present in the code:**

- **Specialty** — carried on the case (`specialty`, plus the optional `obgyn`
  block). OB/GYN is the first supported specialty-specific extension.
- **Difficulty** (compile-time, *not* stored in the case): `easy`, `standard`
  (default), `hard`. Defined in `DIFFICULTY_PROFILES`, each difficulty sets:
  - **disclosure willingness** — the number of "forthcoming" (volunteer)
    directives, strictly decreasing: `easy` = 2, `standard` = 1, `hard` = 0;
    `hard` also adds a guarded "earn trust first" directive (`requires_rapport`).
  - **verbosity** — `expansive` (easy) / `moderate` (standard) / `terse` (hard).
  - **language register** — `plain` (easy) / `colloquial` (standard) /
    `guarded-colloquial` (hard).
  - **emotional overlay intensity** — `subdued` (easy) / `as-written`
    (standard) / `heightened` (hard).
  - **red-herring activation** — off for easy/standard, **on** for hard.
- **Disclosure profile** — the case's own `disclosure_profile` text is added to
  the behavior block as the baseline disclosure tendency.
- **Emotional state** — the case's `emotional_state` is rendered into the opening
  section and modulated by the difficulty's emotional intensity.
- **Language** — `en` or `zh`; resolved from the explicit argument or the case's
  `language`. All section headers, role framing, and behavior directives have
  parallel English and Chinese forms.

Invariants the templates enforce (and the tests assert): `hidden_info` content
appears only in the conditional-disclosure section (never in the opening), higher
difficulty emits strictly fewer volunteer directives, and `TODO_COLLAB`
placeholders are skipped rather than rendered as clinical fact.

```python
from aivmt.case_schema import load_clinical_case
from aivmt.persona import compile_persona

clinical = load_clinical_case("conf/case/obgyn_ectopic_zh_01.yaml")
system_prompt = compile_persona(clinical, difficulty="hard")   # zh from the case
```

You can also compile to labeled sections (`compile_persona_sections`) — this is
exactly what the authoring portal's preview uses.

---

## 4. Linting / validating a case (`aivmt.case_lint`)

`aivmt.case_lint` validates every SP case YAML against the formal schema, with a
fail-loud separation between structural breakage and unfinished content:

- schema violations (bad/missing structural fields, wrong types) → **ERROR**,
  exit code `1`;
- required clinical fields left as the `TODO_COLLAB` placeholder → **WARNING**,
  exit code `0`.

This lets structurally-valid-but-unfinished cases ship for collaborative
authoring while hard schema breaks still fail the build.

```bash
# Lint the whole case directory (default path is conf/case):
uv run python -m aivmt.case_lint conf/case

# Lint a single file:
uv run python -m aivmt.case_lint conf/case/obgyn_ectopic_zh_01.yaml
```

The summary line reports `N file(s), E error(s), W warning(s) -> PASS|FAIL`.

---

## 5. Running a standardized-patient encounter

A standardized-patient encounter runs the SP conversation for one student and
saves the turn-by-turn transcript plus telemetry for later scoring. The patient
answers **only what is asked** and never volunteers information; after
history-taking, an out-loud **reasoning probe** is posed ("state your
differential with reasoning and the next steps").

### 5.1 On the device (single BOOT button)

The ESP32-S3 SP device drives the encounter with one physical **BOOT** button and
voice activity detection (VAD) — there is **no wake word**:

- **Short click** — start / stop the voice conversation. While active, the SP
  listens (VAD), the student speaks naturally, and the patient's reply is spoken
  back. Click again to stop.
- **1-second long-press** — export the completed encounter (transcript +
  telemetry) to the local server, where it is stored for scoring.

With the cloud blocked, a full encounter still completes and exports to the local
server (firmware goal **G5**). For the device build/flash and the server, see
`HARDWARE.md` and `SERVER.md`.

### 5.2 Rehearsal / CLI path (`aivmt.session`)

The same encounter loop runs on a laptop via `aivmt.session` — this is the
collection/rehearsal front-end and what the macOS launchers call. The student
(or an instructor role-playing one) drives one encounter; the transcript is saved
to `data/transcripts/<id>.json`.

`aivmt.session` arguments:

| Flag | Default | Meaning |
|------|---------|---------|
| `--case` | *(required)* | `case_id`, e.g. `obgyn_ectopic_zh_01` (loaded from `conf/case/`) |
| `--id` | *(required)* | encounter id, e.g. `P03_ectopic` (becomes the output filename) |
| `--model` | `gpt-oss:20b` | Ollama model id, or `mock` for an offline dry run |
| `--base-url` | `http://localhost:11434/v1` | OpenAI-compatible endpoint (local Ollama) |
| `--out` | `data/transcripts` | output directory |
| `--voice` | off | spoken encounter (local ASR + TTS) |
| `--whisper-model` | `small` | ASR size: `small` or `medium` |

**Typed (text) encounter against a local model:**

```bash
uv run --extra serve python -m aivmt.session --case obgyn_ectopic_zh_01 --id P03_ectopic
```

**Voice encounter (local ASR + spoken patient replies)** — the exact command the
launchers run:

```bash
uv run --extra serve --extra voice python -m aivmt.session --case obgyn_ectopic_zh_01 --id P01 --voice
```

In voice mode: press **Enter** to start/stop recording one utterance; the
recognized text is shown to **accept (Enter)**, **redo (`r`)**, or type a manual
correction; the patient's reply is spoken aloud.

**Offline smoke test (no model, no audio):**

```bash
uv run python -m aivmt.session --case obgyn_ectopic_zh_01 --id SMOKE --model mock
```

**During the encounter:** type history-taking questions (or speak them in voice
mode). Type `/done` (voice mode: `d`) to end history-taking and trigger the
reasoning probe; `/repeat` logs a voluntary repeat (telemetry); `Ctrl-C` aborts
without saving. When finished, the transcript is written and the console prints
the saved path, the number of questions, and the duration.

**The macOS launchers** (`开始问诊.command`, `开始采集.command`) wrap this for
non-technical operators: they check that the local AI (Ollama) is running at
`http://localhost:11434`, present the three OB/GYN cases as a numbered menu, ask
for a per-encounter id, then run the `--voice` command above in a loop.

The bundled OB/GYN cases:

| Menu | `case_id` | Case |
|------|-----------|------|
| 1 | `obgyn_ectopic_zh_01` | Abdominal pain + vaginal bleeding after missed period (complex; suspected ectopic) |
| 2 | `obgyn_aub_zh_01` | Heavier, prolonged menstrual bleeding (moderate; abnormal uterine bleeding) |
| 3 | `obgyn_vaginitis_zh_01` | Increased discharge + vulvar itching (simple; vulvovaginitis) |

---

## 6. Where encounters are stored and how scoring works

### 6.1 Storage

- **Raw encounters** captured by `aivmt.session` (or exported from the device)
  are JSON under `data/transcripts/<id>.json` — a `Transcript`: `encounter_id`,
  `case_id`, `language`, the `turns`, and `Telemetry` (`duration_s`,
  `n_student_questions`, `n_voluntary_repeats`). Serialization lives in
  `aivmt.dataio` (`save_transcript` / `load_transcript`).
- **Scored encounters** are written by the scoring step as a single JSON bundle
  (transcript + telemetry + scores + feedback) via `save_encounter`, by default
  under `outputs/`.

### 6.2 The scoring pipeline → `CompetencyScore` + `Feedback`

`aivmt.pipeline.ScoringPipeline` orchestrates three registered scorers
(`aivmt.scoring`) over a `(Case, Transcript)` and assembles the validated output.
Every scorer is **strict**: it validates the model's JSON and raises on malformed
output rather than silently defaulting to zero.

| Scorer | Produces | Rubric |
|--------|----------|--------|
| `checklist` | `history_completion` (weighted fraction of checklist items covered) + per-item `item_scores` with evidence quotes | the case's `history_checklist` |
| `segue` | `segue` dict over the five SEGUE communication domains: `set_the_stage`, `elicit_information`, `give_information`, `understand_perspective`, `end_encounter` (each `0.0–1.0`) | anchored SEGUE rubric |
| `reasoning` | `reasoning` (`0.0–1.0`) for the out-loud differential probe | `0` none / `0.5` diagnosis without justification / `1.0` structured differential + justification + next steps |

These are combined into a `CompetencyScore` (`aivmt.schemas`) — all sub-scores in
`[0, 1]` — with `overall` a weighted sum (defaults: `history` 0.4, `segue` 0.4,
`reasoning` 0.2, from `DEFAULT_WEIGHTS`; the `segue` term is the mean of its five
domains). The pipeline then asks the LLM for brief, JSON-only formative
**`Feedback`** (`summary`, `strengths`, `improvements`). The full `ScoringResult`
(`encounter_id`, `model_id`, `score`, `feedback`) is the unit later validated
against faculty ratings.

**Run scoring on a saved encounter** (Hydra entry point `aivmt.run_score`):

```bash
uv run --extra serve python -m aivmt.run_score \
  llm.name=openai_compat llm.base_url=http://localhost:11434/v1 \
  transcript_path=data/transcripts/P03_ectopic.json \
  out_path=outputs/P03_ectopic_scored.json
```

Use `llm.name=mock` to dry-run the pipeline without a model. The case is selected
through Hydra config (`conf/config.yaml`, `conf/case/`, `conf/llm/`); override
keys on the command line as above.

A separate **blinded faculty-scoring** workflow lets clinicians rate the same
encounters by hand so system-vs-faculty agreement (ICC) can be measured — see
`FACULTY_SCORING.md`.

---

## Cross-references

- [Project overview](../README.md)
- [Server setup](./SERVER.md)
- [Device hardware & firmware](./HARDWARE.md)
- [Faculty scoring (blinded rating workflow)](./FACULTY_SCORING.md)
