# AIVMT — Faculty Scoring Guide

This guide is for the **faculty rater** (a clinician who scores recorded
encounters), and for the operator who launches the scoring portal. It is a direct
translation of the Chinese operation manual (`plan/教师评分操作手册.md`) plus the
behavior of the faculty-scoring portal code (`src/aivmt/faculty_portal/`).

> **This is the *scoring* tool, not the *collection* tool.** Collection is when a
> student wears a headset and does history-taking with the AI patient (see
> `USAGE.md`). Here, a clinician reads an **already-recorded** transcript and
> assigns scores — entirely in the browser, no command line.

**In one sentence:** the rater reads each "student vs AI standardized patient"
transcript and scores it on 8 domains from 0 to 1. The page **never shows any
system score or reference answer** (blinded). Each transcript takes roughly
8 minutes.

---

## 1. What the faculty rater does

- Reads a de-identified transcript of one student–SP encounter.
- Judges it as they would when supervising a student's history-taking.
- Scores **8 domains**, each on a continuous **0–1** scale (decimals such as
  `0.5` are allowed).
- Optionally adds a free-text note (the scoring rationale or an observation).
- Submits and moves to the next transcript, until the set is complete.

**Why this matters.** Multiple faculty score the **same** set independently. The
goal is two agreement measures:

1. **Inter-rater agreement** — do the faculty agree with each other?
2. **Human-vs-model agreement** — does the automated `CompetencyScore` agree with
   the faculty consensus?

Both are quantified with the **intraclass correlation coefficient (ICC)**. The
faculty's scores use the **same 0–1 scale** as the system's sub-scores, which is
exactly what makes the human-vs-model comparison well-defined. Faculty enter
their judgments blind, so their ratings are an independent yardstick for the
automated scorer.

**Logistics (per the manual):** plan for **3 raters** (e.g. `fac01`, `fac02`,
`fac03`), each scoring the same set independently. Every rater uses a **single,
fixed id** assigned by the project lead — **never share an id**. Budget about
5–6 hours per rater for a 42-transcript set (~8 min each); the work can be split
across sessions — **closing the page does not lose progress**, and re-entering the
same id resumes from the next unscored transcript.

---

## 2. Launching the faculty-scoring portal

The portal is a local FastAPI web app served from local assets (offline-friendly;
API docs endpoints are disabled). It is rooted at one transcript directory (the
eval set) and one ratings CSV.

### Option A — rater scores on this same computer (simplest)

Double-click **`启动评分.command`** at the repository root. (First time only: if
macOS refuses to open it, right-click → Open → Open.) A terminal window appears
and the browser opens to the scoring page automatically.

The launcher runs exactly:

```bash
uv run --extra portal python -m aivmt.faculty_portal --port 8770
```

- Default host: `127.0.0.1` (local only). Default port: `8770`.
- Open `http://localhost:8770`.

### Option B — raters score from their own laptops (same Wi-Fi; best for parallel raters)

On the host machine, bind all interfaces so peers on the same network can reach
it:

```bash
uv run --extra portal python -m aivmt.faculty_portal --host 0.0.0.0 --port 8770
```

Then send the three raters this address (they must be on the **same Wi-Fi** as
the host):

```
http://<SERVER_LAN_IP>:8770
```

Find the host's LAN IP with `ipconfig getifaddr en0` (it can change if the network
changes). Keep the host **awake and unlocked** until all raters finish — do not
let it sleep.

Either way the rater sees the identical page (§3).

**CLI flags** (`python -m aivmt.faculty_portal`):

| Flag | Default | Meaning |
|------|---------|---------|
| `--host` | `127.0.0.1` | bind host |
| `--port` | `8770` | bind port |
| `--transcript-dir` | `$AIVMT_EVAL_TRANSCRIPT_DIR` or `data/eval_transcripts` | the eval transcript set to rate |
| `--ratings-csv` | `$AIVMT_FACULTY_RATINGS_CSV` or `data/faculty_ratings.csv` | where ratings are appended |
| `--seed` | `42` | base seed (mirrors `configs/seed.yaml`) |

The portal **fails loud** if the transcript directory is missing rather than
inventing an empty set.

---

## 3. The blinded, by-case scoring packet

Blinding is a **hard, structural** requirement, not just a UI choice. The only
transcript payload the API can build is the blinded one
(`TranscriptStore.blinded_payload`): it contains the encounter id, case id,
language, and the turn-by-turn `speaker`/`text` **only**. There is no system
score, no gold label, no model id, and no condition field anywhere in the payload
to leak — the API never reads system scores.

**Fixed, by-case order.** Every rater is served encounters in one **fixed
canonical order** — grouped by case, then by encounter id — identical for all
raters. The case order is `obgyn_ectopic_zh_01` → `obgyn_aub_zh_01` →
`obgyn_vaginitis_zh_01`. This order matches the offline paper scoring packet, so
an operator entering an off-network faculty's paper scores walks the web tool in
lock-step with the PDF.

**Resume safety.** Progress is keyed on `(rater_id, encounter_id)` in the ratings
CSV. The session/progress endpoints report `scored / total / remaining` and the
next unscored encounter, so re-entering the same id always resumes correctly. The
ratings CSV is appended atomically (temp file + replace), and a duplicate rating
for the same `(rater, encounter)` is refused unless an explicit re-score is
requested.

---

## 4. How a rater scores (step by step)

### Step 1 — Enter your rater id
Type the id assigned to you by the project (e.g. `fac01`) and click to enter.
Transcripts you have already scored under this id will not reappear — **so always
use the same id.**

### Step 2 — Read one transcript
The page shows one student-vs-SP transcript. Read it through and form your
judgment as you would when assessing a student's history-taking. **No reference
answer or machine score is shown — your judgment is the standard.**

### Step 3 — Score the 8 domains (each 0–1, decimals allowed)

| # | Domain | 0 (poor) → 1 (excellent) |
|---|--------|--------------------------|
| 1 | **Set the stage** | no self-introduction / no stated purpose → introduces self, states purpose, builds rapport |
| 2 | **Elicit information** | barely asks / closed questions only → systematic, open-ended history-taking |
| 3 | **Give information** | no explanation / feedback → explains clearly in lay terms the patient understands |
| 4 | **Understand perspective** | ignores the patient's concerns and feelings → actively explores ideas, concerns, expectations |
| 5 | **End the encounter** | abrupt ending → summarizes, answers questions, closes properly |
| 6 | **History completion** | key history almost entirely missed → the points that should be asked are essentially all covered |
| 7 | **Clinical reasoning** | aimless questions, no differential → organized, differential-driven questioning |
| 8 | **Overall** | well below standard → excellent overall performance |

Enter a decimal in `[0, 1]` for each (e.g. `0`, `0.3`, `0.5`, `0.7`, `1`). A
**notes** box is optional but valuable for later analysis.

These domains map onto the rating CSV columns
(`aivmt.dataio.FACULTY_SHEET_FIELDS`): the five SEGUE domains
(`set_the_stage`, `elicit_information`, `give_information`,
`understand_perspective`, `end_encounter`) plus `history_completion`,
`reasoning`, and `overall` — the same axes the automated scorer produces, which
is what enables the per-domain and overall ICC comparisons.

> **Server-side validation is strict.** Every numeric domain must be a finite
> number in `[0, 1]`; a single missing, non-numeric, or out-of-range value makes
> the whole submission invalid and **nothing is written** (the API returns 422).
> There is no silent clamping or default — a bad value is treated as a
> data-quality signal.

### Step 4 — Submit and continue
Click submit. The progress counter at the top (e.g. `12 / 42`) advances. Repeat
Steps 2–4 until you see **"all transcripts complete."**

### Breaks / switching raters
You can close the page at any time — progress is saved; re-open, enter the **same
id**, and continue from the next unscored transcript. To hand off to another
clinician, switch the rater at the top and have them enter **their own id**
(**never reuse an id**).

---

## 5. After all raters finish (operator)

1. Confirm every rater reached **"all transcripts complete."**
2. All ratings are aggregated automatically into one file:
   **`data/faculty_ratings.csv`** (columns in `FACULTY_SHEET_FIELDS` order).
3. Tell the project lead that scoring is done. The system then scores the same
   transcripts and computes agreement with the faculty (ICC), producing the first
   real validity numbers.

---

## 6. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `启动评分.command` says it "can't be opened" | Right-click → Open → Open (first time only). |
| A rater's laptop can't open the URL | Confirm it is on the **same Wi-Fi** as the host; confirm the host command is still running and its window is open; if the IP changed, re-check with `ipconfig getifaddr en0`. |
| Page shows "no transcripts to rate" | The eval set is not loaded — confirm the transcript directory (default `data/eval_transcripts/`) contains the transcripts, or pass `--transcript-dir`. |
| Wrong rater id used by mistake | Switch back to the correct id and continue; rows entered under the wrong id are attributed to that id — tell the project lead to clean them up. |
| Host about to sleep | Set it to never sleep during scoring; do not close the lid. |

---

*This guide corresponds to the faculty-scoring portal (`aivmt.faculty_portal`).
The eval set is a collection of de-identified OB/GYN encounter transcripts; the
Chinese manual references a 42-transcript set.*

---

## Cross-references

- [Project overview](../README.md)
- [End-to-end usage (install, authoring, encounters, scoring)](./USAGE.md)
- [Server setup](./SERVER.md)
- [Device hardware & firmware](./HARDWARE.md)
