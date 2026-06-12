# TRIPOD-LLM Reporting-Guideline Compliance Checklist — AIVMT SQ1

> **Status of this document:** living compliance map maintained alongside the manuscript. It records,
> item by item, how the AIVMT SQ1 study (local open-weight LLM as automated competency scorer vs.
> blinded faculty) is reported against the TRIPOD-LLM standard. Many items are **Partial** or
> **TODO_COLLAB** on purpose: as of **2026-06-13** no real faculty ratings have been collected, so
> there is no real ICC, no fairness analysis on real subgroups, and no final sample. Do **not** read
> a row as "Done" unless it literally says Done. This file itself is documentation-only (no code), but
> it must be reconciled against the live working tree: as of this revision the tree contains concurrent
> sibling-stream code changes — a scorer-level few-shot ablation (`src/aivmt/scoring/`) and a robustness
> module (`src/aivmt/robustness/`) — so any claim here about what is or is not "in code" is grounded by
> a fresh grep of the working tree, not a prior snapshot.
>
> **Row-only STATUS tally (final cell of each of the 32 data rows; tokens may co-occur on a row, so the
> counts overlap and do not sum to 32):** 9 rows contain **Done**, 15 contain **Partial**, 11 contain
> **TODO_COLLAB** (3 rows carry two tokens: §3 participants and §8 data-availability are "Partial /
> TODO_COLLAB"; §6 model-performance is "TODO_COLLAB (real result) / Done (machinery)").

---

## 0. Header — guideline, study type, applicable variant

### 0.1 Guideline citation (VERIFY before manuscript submission)

- **Guideline:** TRIPOD-LLM — *Transparent Reporting of a multivariable prediction model for
  Individual Prognosis Or Diagnosis: Large Language Models extension.*
- **Attribution (to verify against the published article):** Gallifant J, et al. *TRIPOD-LLM:
  reporting guideline for studies using large language models in healthcare.* **Nature Medicine,
  2025.** **VERIFY** the exact author list, title wording, volume/page, and DOI against the
  published record before citing — do not paste this string into the manuscript unchecked.
- **Lineage to verify:** TRIPOD (Collins et al., 2015) → TRIPOD+AI (Collins et al., BMJ 2024) →
  TRIPOD-LLM (2025 extension). When citing the *checklist items by number*, cite the official
  TRIPOD-LLM checklist PDF / supplementary table, **not** this internal map.
- **General honesty caveat on item numbering:** TRIPOD-LLM is a recent, modular guideline whose
  exact item *numbers* and *sub-item letters* are reorganized relative to TRIPOD 2015. Wherever a
  precise item number/label appears below it is annotated **(VERIFY #)**. Treat every numbered label
  as provisional until checked against the published checklist (Gallifant et al., Nat Med 2025).

### 0.2 Study type

- **Type:** an **LLM-as-judge / automated competency-scoring validity study** — an LLM is used not as
  a clinical *predictor of patient outcome* but as an **automated rater** that assigns competency
  scores to clinical history-taking transcripts. This is **prognostic/diagnostic-adjacent**: it is a
  *measurement-validity / agreement* study (criterion = blinded faculty consensus), reported with
  inter-rater reliability statistics rather than discrimination/calibration of a disease outcome.
- **Primary estimand:** absolute agreement **ICC(2,1) ≥ 0.75** between the local-model automated
  score and the faculty consensus score on Chinese (zh) history-taking encounters
  (`HYPOTHESIS.md` "Statistical test (pre-registered)", l.22–25; `plan/STORY_LOCK.md` SQ1, l.19).
- **Task framing:** scoring **validity**, not prediction of a downstream clinical event. TRIPOD-LLM
  items written for *outcome prediction* (e.g., predicted-vs-observed calibration of a clinical
  endpoint) are mapped to their **measurement-validity analogue** here, and that re-mapping is stated
  explicitly per row so reviewers can see the analogy is deliberate, not a dodge.

### 0.3 Applicable TRIPOD-LLM variant / pathway (VERIFY against published structure)

TRIPOD-LLM is **modular**: it splits items by (a) development vs. evaluation/use, and (b) the
reporting medium (full manuscript vs. abstract). For AIVMT SQ1:

- **Pathway = EVALUATION / VALIDATION of an LLM applied off-the-shelf (no fine-tuning).** AIVMT does
  **not** train or fine-tune a model; it evaluates fixed open-weight checkpoints (`gpt-oss:20b` and
  the frontier tiers) used zero-shot with an anchored rubric prompt. So **"model development" items
  are largely N-A**, and **"evaluation / validation / human-oversight / fairness" items are the
  governing set**. **VERIFY** that the published guideline labels this the "evaluation" or
  "validation" track.
- **Full-text checklist** applies (this is a full research article), **plus the abstract checklist**
  for the structured abstract.

---

## 1. Title and Abstract

| Item (VERIFY #) | What TRIPOD-LLM requires | How AIVMT addresses it | STATUS |
|---|---|---|---|
| **Title** (VERIFY ~Item 1) | Identify the study as developing/evaluating an LLM-based method; name the target task and that an LLM is used. | Manuscript title not yet finalized. The locked headline framing ("validity–cost frontier for local-model automated standardized-patient scoring") is in `plan/STORY_LOCK.md` l.7–14 and must be reflected in the title, explicitly stating LLM-as-scorer + history-taking competency. | **TODO_COLLAB** (title not drafted) |
| **Abstract** (VERIFY ~Item 2; structured-abstract checklist) | Structured abstract: objective, data/setting, model + LLM details, outcome, sample, analysis, results, limitations. | Abstract not yet written. Inputs available: objective + estimand (`HYPOTHESIS.md`), planned design (`plan/STORY_LOCK.md`), pilot numbers (`results/phase_scoring_validity/frontier_v1_synthetic.md`, clearly synthetic). Real headline numbers do not exist yet → abstract cannot report a real ICC. | **TODO_COLLAB** |

---

## 2. Introduction

| Item (VERIFY #) | What TRIPOD-LLM requires | How AIVMT addresses it | STATUS |
|---|---|---|---|
| **Background / rationale** (VERIFY ~Item 3a) | Clinical/health context, why an LLM approach, prior art and gap. | `plan/STORY_LOCK.md` "Central claim" + "Closest prior art to beat" (l.7–14, l.23–25): AMTES (cloud ICC 0.92–0.98), Voigt 2025, Sun 2026, the 2026 "no offline/edge SP exists" review. The owned gap = local-model validity + cost frontier + embodiment. Needs transcription into Introduction prose. | **Partial** (rationale captured in repo; not yet in manuscript prose) |
| **Objectives / questions** (VERIFY ~Item 3b) | State specific objectives, including the prediction/measurement task and intended use. | Objectives are explicit: SQ1 validity–cost frontier (`plan/STORY_LOCK.md` l.16–21), formal H1/H0 in `HYPOTHESIS.md` "Hypothesis"/"Null hypothesis" (l.7–14). Intended use = offline, data-local SP practice scoring in LMIC settings. | **Partial** (objectives locked; manuscript prose pending) |

---

## 3. Methods — data, participants, setting

| Item (VERIFY #) | What TRIPOD-LLM requires | How AIVMT addresses it | STATUS |
|---|---|---|---|
| **Data source(s)** (VERIFY ~Item 4) | Describe source of data/transcripts, setting, dates of collection. | Transcripts = standardized-patient history-taking encounters generated by the AIVMT device persona engine from formal cases (`conf/case/*.yaml`; e.g. `obgyn_ectopic_zh_01.yaml`). Pilot used 30 **synthetic** English encounters (`results/.../frontier_v1_synthetic.md`, labeled synthetic floor). Real zh collection-day transcripts not yet gathered; collection setting/dates TBD by collaborator. | **Partial** (pipeline + synthetic pilot exist; real corpus not collected) |
| **Participants / units** (VERIFY ~Item 5) | Eligibility, the unit of analysis, how cases/encounters selected. | Unit = an encounter (one student × one SP case). Cases are specialty-tagged, difficulty-tagged (`conf/case/obgyn_*_zh_01.yaml`: `specialty`, `difficulty`). Faculty raters: **k = 3**, language zh (`HYPOTHESIS.md` "Sample size / power" l.40–41). Student/encounter eligibility criteria = collaborator decision. Several case fields are honestly stubbed `TODO_COLLAB` pending OB/GYN faculty sign-off (e.g. `obgyn_ectopic_zh_01.yaml` l.15, l.25–37). | **Partial / TODO_COLLAB** |
| **Outcome / target label** (VERIFY ~Item 6) | Define the outcome the model predicts/scores and how the reference standard (label) is determined, blinded. | Target = competency score in [0,1]: overall + subscores (5 SEGUE domains, history-checklist completion, out-loud reasoning) — `HYPOTHESIS.md` "Variables" l.16–20. **Reference standard = blinded faculty consensus**; faculty are blinded to the system score (design intent in `HYPOTHESIS.md`). Faculty inter-rater ICC is reported as the agreement **ceiling** (`HYPOTHESIS.md` l.33). Faculty ratings file is a declared phase input (`data/faculty_ratings.csv`) that **does not exist yet**. | **Partial** (definition + blinding designed; labels not collected) |
| **Predictors / model inputs** (VERIFY ~Item 7) | Define inputs given to the model and the prompt. | Inputs = full rendered transcript + anchored rubric, supplied via fixed prompts. SEGUE: 5 anchored domains, strict-JSON schema, bilingual en/zh system+user prompts (`src/aivmt/scoring/segue.py`). Checklist + reasoning scorers parallel (`src/aivmt/scoring/checklist.py`, `reasoning.py`). Composite weights fixed: history 0.4 / segue 0.4 / reasoning 0.2 (`conf/config.yaml` `scoring.weights`). | **Done** (inputs/prompts specified and version-controlled) |

---

## 4. Methods — LLM-specific reporting items (the core of TRIPOD-LLM)

| Item (VERIFY #) | What TRIPOD-LLM requires | How AIVMT addresses it | STATUS |
|---|---|---|---|
| **Model identity: name + version** (VERIFY ~LLM item) | Exact model name and version/checkpoint. | Anchor model `gpt-oss:20b` declared in `conf/llm/ollama_gptoss.yaml` (`model_id: gpt-oss:20b`). Frontier tiers enumerated in `results/.../frontier_v1_synthetic.md`: `qwen2.5:3b/7b/14b`, `llama3.1:8b`, `gpt-oss:20b`, with params + disk size. **Gap:** Ollama tag ≠ a frozen checkpoint hash; the exact quantization/build/digest per model must be pinned and reported (an Ollama tag can be re-pulled to a different blob). | **Partial** (names + tier params present; exact digests/quant not yet pinned in a config) |
| **Model access / availability** (VERIFY ~LLM item) | How the model is accessed (API/local), open vs closed weights, version pinning. | Open-weight, **local**, served via Ollama over an OpenAI-compatible endpoint (`conf/llm/ollama_gptoss.yaml`: `base_url: http://localhost:11434/v1`); client `src/aivmt/llm/openai_compat.py`. Offline/local access is itself a study contribution (`plan/STORY_LOCK.md` l.10–12). | **Done** (access path specified) |
| **Prompt / prompt engineering** (VERIFY ~LLM item) | Full prompt(s), prompt-construction strategy, any prompt iteration. | System + user prompts are in source and reproducible: `src/aivmt/scoring/segue.py` (`_SYS`, `_build_user`), with explicit anchors and an exact JSON output schema. Bilingual prompts (en/zh) are literal in code. For the manuscript, the verbatim prompts should be reproduced in a supplement. | **Done** (prompts versioned in code; supplement export pending) |
| **Shot strategy (zero/few-shot) + exemplars** (VERIFY ~LLM item) | State whether zero-/few-shot; if few-shot, give exemplars and their provenance. | **Current verified state (re-checked 2026-06-13 against the working tree): the few-shot/zero-shot ablation is IMPLEMENTED at the scorer level.** Default `variant="zero_shot"` reproduces the original anchored-rubric prompts **byte-for-byte**; `variant="few_shot"` prepends SYNTHETIC, explicitly-labeled exemplars via `build_exemplar_block` (`src/aivmt/scoring/base.py`: `ScorerVariant`, `Exemplar`, `build_exemplar_block`; per-scorer `_FEW_SHOT_EXEMPLARS` + a `few_shot` branch in `_build_user` in `src/aivmt/scoring/segue.py`, `checklist.py`, `reasoning.py`; re-exported from `src/aivmt/scoring/__init__.py`; covered by `tests/test_scoring_fewshot.py`, which asserts zero-shot byte-identity, few-shot prepending, and strict parsing on the mock LLM). The exemplars are labeled "WORKED EXAMPLES (SYNTHETIC … not real patient data)" and contain no real patient data, satisfying project AI4S rules. **Gap:** the few-shot variant is **NOT yet wired into `harness/registry.py` or `conf/`**, so it cannot be run/reported as an end-to-end experiment arm; a repo-wide grep confirms no `variant`/`few_shot` references in `harness/registry.py` or `conf/`. The manuscript should describe zero-shot as the primary method and report the few-shot ablation once it is harness-wired and run. | **Partial** (variant implemented + tested at scorer level; not yet harness/conf-wired or run) |
| **Decoding / temperature / determinism** (VERIFY ~LLM item) | Report temperature, sampling, and steps taken for reproducibility/determinism. | `temperature: 0.0` declared in `conf/llm/ollama_gptoss.yaml`. Analysis seed = 42 from `configs/seed.yaml` (single source of truth; never hardcoded — enforced by `harness/registry.py:load_seed`). `HYPOTHESIS.md` "Controlled" (l.20) and "Seed" (l.61–63) lock fixed model + temp 0 + fixed seed. **Caveat to report:** temp 0 reduces but does not fully guarantee bitwise determinism across Ollama builds/hardware. | **Done** (temp 0 + seed pinned; residual nondeterminism caveat to be noted) |
| **Output handling / failure mode** (VERIFY ~LLM item) | How malformed/refused outputs are handled (no silent fallback). | Fail-loud: `OpenAICompatClient` raises `LLMOutputError` on malformed JSON and tracks parse/refusal counters (`src/aivmt/llm/openai_compat.py`); scorers enforce strict schema + range checks (`segue.py` `require(...)`, numeric/[0,1] guards). Synthetic pilot: 100% parse across 450 calls (`results/.../frontier_v1_synthetic.md`). No silent fallback — aligns with AI4S "fail explicitly" rule. | **Done** |
| **Human oversight / human-in-the-loop** (VERIFY ~LLM item) | Describe role of humans, oversight of LLM outputs, intended human supervision in use. | Reference standard is human (faculty); the LLM is positioned as an *assistive automated scorer* benchmarked against faculty, **not** an autonomous grader replacing faculty. Faculty consensus is the criterion and faculty inter-rater ICC the ceiling (`HYPOTHESIS.md` l.33). Decision-consistency at a pass/fail cut-score (default 0.6) is reported to characterize high-stakes use (`HYPOTHESIS.md` l.31–32). Intended-use / oversight statement for deployment is **not yet written** as manuscript prose. | **Partial** |
| **Fairness / bias / subgroup analysis** (VERIFY ~LLM item) | Report fairness considerations and subgroup performance (e.g., by demographic/clinical strata). | Cases carry strata that *enable* subgroup analysis (specialty, difficulty, language, patient demographics in case YAML). **No subgroup/fairness analysis exists yet** because there is no real faculty-rated data. Language is a flagged risk: the pilot is English; Llama-3.1-8B is EN-centric and its zh validity must be re-checked on real zh data before any zh deployment claim (`results/.../frontier_v1_synthetic.md` "Reads" #4). Must add an explicit fairness/subgroup plan + results. | **TODO_COLLAB** |
| **Compute / cost / environment** (VERIFY ~LLM item or "Other") | Report compute, cost, and resource use where relevant. | Cost is a first-class study output (SQ3, `plan/STORY_LOCK.md` l.21): ≈$0 marginal cost per encounter, offline. Frontier table reports model params + on-disk size per tier (`results/.../frontier_v1_synthetic.md`). A full compute/runtime/energy accounting for the real run is **TODO** (the full robustness matrix is executed separately). | **Partial** |

---

## 5. Methods — sample size and analysis

| Item (VERIFY #) | What TRIPOD-LLM requires | How AIVMT addresses it | STATUS |
|---|---|---|---|
| **Sample size / power** (VERIFY ~Item 8) | Justify sample size for the evaluation. | Pre-specified and reasoned on the 95% CI half-width of ICC(2,1), k=3: primary **n = 150 encounters × 3 raters** (half-width ≈0.07 @ICC 0.70), floor **n = 100**, staged pilot ~25, contingency n≈40 (`HYPOTHESIS.md` "Sample size / power" l.39–52). **Honesty flag:** these cite `prereg §11 l.99–110` and `PROJECT_PLAN l.40/67`, but **`plan/preregistration-v0.1.md` and `plan/PROJECT_PLAN.md` are not present on disk** (see §8 below). The power *logic* is in `HYPOTHESIS.md`; the cited source files must be added/restored. | **Partial** (power logic stated; cited source files missing) |
| **Statistical / analysis methods** (VERIFY ~Item 9) | Pre-specified analysis: agreement metrics, CIs, handling of raters, missing data. | Full validity suite pre-specified in `HYPOTHESIS.md` l.22–33: ICC(2,1) primary + ICC(2,k); McGraw & Wong (1996) F-based 95% CI; seeded bootstrap 95% CI cross-check; per-rater ICC; quadratic-weighted κ; Bland–Altman (bias, LoA, proportional-bias slope+p); G-theory variance components + D-study (k=1..5); decision consistency (raw + Cohen's κ) at cut 0.6. Implemented in `src/aivmt/metrics/` (icc/agreement/bland_altman/gtheory/validity/report) and orchestrated by `PhaseScoringValidity` in `harness/registry.py`. 131 tests pass. | **Done** (methods pre-specified + implemented; runs on fixtures until real data) |
| **Multiple comparisons / multiplicity** (VERIFY ~Item) | State the primary endpoint and handle multiplicity / no fishing. | Single primary endpoint = ICC(2,1); subscores, frontier tiers, SQ2/SQ3 are secondary/exploratory and labeled so; non-inferiority is **conditional** (dropped unless pilot clears ~0.80), not a second primary (`HYPOTHESIS.md` "Multiple comparisons / correction" l.65–69; "Non-inferiority is CONDITIONAL" l.34–37). `check_science.sh` greps for a non-inferiority/correction statement. | **Done** |
| **Reproducibility / harness contract** (VERIFY ~Item) | Steps ensuring results are regenerable. | Every manuscript number must regenerate via `python -m harness.evidence_table` from `phase.benchmark()`, and `python -m harness.run_all` must exit 0 with negative controls firing (`plan/STORY_LOCK.md` "Definition of done" l.34–36). Negative controls implemented and required to FAIL when the effect is absent: shuffled-pairing collapses ICC, and the suite negative control (`harness/registry.py` `sanity()` → `harness/sanity/scoring_validity.py`). Seed centralized; `check_science.sh` gate PASS. | **Done** |

---

## 6. Results

| Item (VERIFY #) | What TRIPOD-LLM requires | How AIVMT addresses it | STATUS |
|---|---|---|---|
| **Participants / flow** (VERIFY ~Item 10) | Report numbers of encounters/raters, flow, missing data. | No real participant flow yet (no collected encounters/ratings). The synthetic floor pilot used 30 encounters × 5 models (`results/.../frontier_v1_synthetic.md`). Real flow diagram + counts are **TODO_COLLAB**. | **TODO_COLLAB** |
| **Model performance / agreement** (VERIFY ~Item 11) | Report the agreement metrics with CIs (the primary result). | Until real data exists, the harness benchmark returns `status: PENDING_REAL_DATA` with a fixture true-vs-shuffled overall-ICC cross-check (`harness/registry.py` `PhaseScoringValidity.benchmark`). The **only** model-vs-criterion numbers that currently exist are vs. a *designed quality ordering ("gold")* on synthetic data — **explicitly NOT the validity claim** (`results/.../frontier_v1_synthetic.md` header + "Reads"). Real ICC(2,1) vs faculty is **TODO_COLLAB**. | **TODO_COLLAB** (real result), **Done** (machinery + honest synthetic pilot) |
| **Subgroup / fairness results** (VERIFY ~Item) | Report subgroup performance. | None yet — see §4 fairness row. Strata are available in case configs to support this once real data arrives. | **TODO_COLLAB** |

---

## 7. Discussion

| Item (VERIFY #) | What TRIPOD-LLM requires | How AIVMT addresses it | STATUS |
|---|---|---|---|
| **Interpretation** (VERIFY ~Item 12) | Interpret results vs objectives and prior art. | Framing + comparators ready (`plan/STORY_LOCK.md`): position vs AMTES/Borg/2026 review. Interpretation prose pending real results. | **Partial** |
| **Limitations** (VERIFY ~Item 13) | State limitations: data, generalizability, LLM-specific risks. | Strong honest base already documented: synthetic-only pilot is a *floor not a claim*; n=30 CI ~±0.1 → no clean size law; family effects ≥ size effects; English-pilot language caveat for zh deployment (`results/.../frontier_v1_synthetic.md` "Reads" #1–5). Plus: Ollama-tag (non-digest) version risk; residual temp-0 nondeterminism; missing prereg source files (§8). Must be consolidated into a Limitations subsection. | **Partial** (raw material strong; not yet manuscript prose) |
| **Intended use / deployment caution** (VERIFY ~Item) | State intended clinical/educational use and cautions. | Intended use = offline LMIC SP-practice scoring assistant, faculty-benchmarked, not autonomous grading. Stated in `plan/STORY_LOCK.md` l.10–12; needs an explicit deployment-caution paragraph. | **Partial** |

---

## 8. Other information — registration, protocol, funding, data/code availability

| Item (VERIFY #) | What TRIPOD-LLM requires | How AIVMT addresses it | STATUS |
|---|---|---|---|
| **Study registration / protocol** (VERIFY ~Item 14) | State registration and where the protocol/analysis plan can be found. | A preregistration/analysis plan is **referenced throughout** `HYPOTHESIS.md` as `plan/preregistration-v0.1.md` (with cited §/line numbers, e.g. §4 l.22–24, §8 l.62–73, §10 l.85–88, §11 l.99–110) and `plan/PROJECT_PLAN.md` (l.40, l.67). **CRITICAL HONESTY FLAG: neither file currently exists on disk** (verified 2026-06-13 — `find` over the repo returns none; the only file containing the string "preregistration" is `HYPOTHESIS.md` itself). The analysis is therefore *pre-specified in spirit* (locked in `HYPOTHESIS.md`) but the cited prereg artifact and its line anchors are **not reproducible**. Must restore/author `plan/preregistration-v0.1.md` (and `PROJECT_PLAN.md`) before the manuscript cites it, or repoint citations to `HYPOTHESIS.md`. External registration (e.g., OSF) is **TODO_COLLAB**. | **TODO_COLLAB** (cited prereg files missing — top gap) |
| **Funding** (VERIFY ~Item 15) | Declare funding and role of funder. | Not present in repo. | **TODO_COLLAB** |
| **Conflicts of interest** (VERIFY ~Item) | Declare COI. | Not present in repo. | **TODO_COLLAB** |
| **Data availability** (VERIFY ~Item 16) | State where data are / are not available. | Case configs and synthetic transcripts are in-repo (`conf/case/*.yaml`, `data/transcripts/*.json` — e.g. `REHEARSAL_good.json`, `SMOKE01.json`). Real encounter transcripts + `data/faculty_ratings.csv` do not exist yet; their availability/de-identification policy is **TODO_COLLAB** (and must respect "no real patient data" rules). | **Partial / TODO_COLLAB** |
| **Code availability** (VERIFY ~Item) | State code availability and reproducibility entry points. | Code is a self-contained, version-controlled repo (uv-managed). Reproduction entry points: `python -m harness.run_all`, `python -m harness.evidence_table`, `./check_science.sh`, seed in `configs/seed.yaml`. Public-release plan (license + URL) is **TODO_COLLAB**. | **Partial** (reproducible internally; public release pending) |

---

## Top gaps to close before submission

Derived from the **TODO_COLLAB / Partial** rows above, in rough priority order:

1. **Restore or author the cited preregistration & project-plan artifacts.**
   `HYPOTHESIS.md` cites `plan/preregistration-v0.1.md` and `plan/PROJECT_PLAN.md` with specific §/line
   numbers, but **neither file exists on disk**. Either recreate them (so the cited anchors resolve and
   the analysis plan is reproducible) or repoint every citation to `HYPOTHESIS.md`. Add external
   registration (e.g., OSF) if claimed. *(§8 registration row — highest priority: a reviewer can
   trivially catch a citation to a non-existent protocol.)*
2. **Collect real faculty-rated zh data and produce the real ICC(2,1).**
   No real ICC, no participant flow, no model-vs-faculty result exists — only a synthetic floor pilot
   explicitly labeled "NOT the validity claim." This is the study's primary result (§3 outcome, §5
   sample, §6 results). Faculty k=3, blinded, with `data/faculty_ratings.csv` populated.
3. **Add the fairness / subgroup analysis** (by specialty, case difficulty, and especially **language
   zh vs en**). Strata exist in case configs; analysis does not. Resolve the EN-centric-model zh-validity
   caveat on real data. *(§4 fairness, §6 subgroup rows.)*
4. **Wire the existing few-shot variant into the harness/conf and run/report the ablation.**
   The few-shot vs zero-shot ablation is already **implemented at the scorer level** (default
   `variant="zero_shot"` is byte-identical to the original prompts; `variant="few_shot"` prepends
   SYNTHETIC, explicitly-labeled exemplars via `build_exemplar_block` in `src/aivmt/scoring/base.py`,
   with per-scorer `_FEW_SHOT_EXEMPLARS` in `segue.py`/`checklist.py`/`reasoning.py`, tested in
   `tests/test_scoring_fewshot.py`). What is **missing** is the harness/conf wiring: expose `variant`
   through `harness/registry.py` and `conf/` so the ablation runs as an end-to-end experiment arm,
   then report zero-shot as primary and the few-shot delta as the ablation. *(§4 shot-strategy row.)*
5. **Pin exact model versions, not just Ollama tags.**
   Record per-model quantization/build/digest so `gpt-oss:20b` etc. are frozen checkpoints, and note
   the residual temp-0 nondeterminism caveat. *(§4 model-identity + decoding rows.)*
6. **Write the human-oversight / intended-use / deployment-caution statements** as manuscript prose.
   *(§4 oversight, §7 intended-use rows.)*
7. **Add funding, conflicts-of-interest, and data/code public-availability statements** with license +
   URL. *(§8 rows.)*
8. **Add full compute/runtime/cost accounting for the real run** (SQ3), beyond the per-tier disk/params
   already tabulated. *(§4 compute row.)*
9. **Draft the title and structured abstract** to TRIPOD-LLM abstract checklist once real numbers exist.
   *(§1 rows.)*

> Reminder for reviewers/authors: cite item *numbers* from the **official TRIPOD-LLM checklist**
> (Gallifant et al., Nat Med 2025), not the provisional "(VERIFY #)" labels in this internal map.
