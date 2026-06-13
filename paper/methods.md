# Methods

> Auto-drafted skeleton (2026-06-13). Every quantitative claim is traceable to a registered harness
> phase under `results/`; faculty-dependent quantities are explicit placeholders pending data
> collection. Citations in `[CITE: ...]` form are placeholders grounded in the prior art named in
> `plan/STORY_LOCK.md` and must be resolved before submission.

## Study design and overview

We report a measurement-validity study of an automated competency scorer for standardized-patient
(SP) clinical encounters, conducted on a fully self-hosted, open-weight platform intended for
deployment in low- and middle-income-country (LMIC) medical schools. The study has two
complementary spines. The first is a **system contribution**: a complete, deployable platform that
couples a low-cost embodied SP device, a self-hosted open-weight large-language-model (LLM) scoring
service that runs offline at approximately zero marginal cost per encounter, a teacher-facing
case-authoring portal, and a blinded faculty-scoring portal. The second is a **validation
contribution**: a pre-registered analysis of how well the automated scores agree with blinded
faculty experts, mapped across the validity–cost frontier (model size, quantization level, and a
local-versus-cloud head-to-head), together with robustness analyses against automatic-speech-
recognition (ASR) noise and prompt and seed perturbation.

The primary study question (SQ1 in `plan/STORY_LOCK.md`) is framed as a **validity–cost frontier**:
at what model size and operating cost does automated SP scoring reach faculty-level agreement, and
where does it collapse. The **primary endpoint is pre-registered** in `HYPOTHESIS.md` (lines 22–25)
as a two-way random-effects, absolute-agreement intraclass correlation coefficient,
**ICC(2,1) ≥ 0.75**, between the system score and the consensus of blinded faculty raters on Chinese
(zh) history-taking encounters; this is described as the threshold for "clinically useful absolute
agreement." Two secondary study questions are pre-specified but not the subject of the analyses
reported here: whether physical voice embodiment changes learner engagement and perceived realism
relative to a same-model screen interface (SQ2, an embodiment study; no data collected), and total
cost and offline capability relative to cloud-LLM and human-SP baselines (SQ3, a
descriptive/analytic cost study).

The analysis plan was pre-specified before data collection. **Note (governance discrepancy):**
`HYPOTHESIS.md` and `plan/TRIPOD-LLM-checklist.md` cite a preregistration file
(`plan/preregistration-v0.1.md`) and a project-plan file (`plan/PROJECT_PLAN.md`) with load-bearing
section and line anchors (e.g. prereg §4, §8, §10, §11). As of 2026-06-13 **neither file exists on
disk** (only `plan/STORY_LOCK.md` and `plan/TRIPOD-LLM-checklist.md` are present), so those
section/line citations are currently unresolvable and must be reconciled before submission; the
pre-specification that does exist on disk is `HYPOTHESIS.md` itself.

## The platform

### Device apparatus

The deployment vehicle is a low-cost embodied SP device built as a fork of an open-source ESP32-S3
voice assistant (`firmware/`). We describe the device honestly as **apparatus, not a claimed
contribution** (`plan/STORY_LOCK.md`, SCOPE LOCK). The firmware integration is real: a build report
(`firmware/G0_BUILD_REPORT.md`) documents a verified-green build under ESP-IDF v5.5.2 for the exact
ESP32-S3 target (chip id confirmed from the binary image header), with the project's `aivmt_sp`
component compiling and linking against the toolchain, an application image of 2,648,944 bytes that
fits the application slot with 36% free, and a 16 MB flash layout that matches the partition table
dumped from the physical device. **Two honest caveats apply and are stated in the source report.**
First, the SP experience hooks are **not yet wired** into the firmware application loop: `SpSession`
is dormant, so if the device were flashed as built it would behave like the upstream voice assistant
rather than running an SP encounter. Second, the device is **not flashed for a study**; the build
proves toolchain, integration, and board/flash compatibility, but no on-device data collection has
taken place. The analyses in this manuscript are therefore conducted on transcripts processed by the
software platform, independently of the device.

### Self-hosted open-weight scoring service

All scoring runs on open-weight models served **locally** over an OpenAI-compatible endpoint via
Ollama (`conf/llm/ollama_gptoss.yaml`: `base_url: http://localhost:11434/v1`), with the client
implemented in `src/aivmt/llm/openai_compat.py`. Offline, data-local operation is itself a study
contribution: no transcript leaves the host, and the marginal cost per encounter is approximately
zero. The client is **fail-loud**: malformed or refused model output raises an `LLMOutputError`
rather than triggering any silent fallback, and parse-success and refusal counters are tracked for
every call. Decoding is deterministic to the extent the backend allows — temperature is fixed at 0.0
(`conf/llm/ollama_gptoss.yaml`) — and we note in the limitations that temperature 0 reduces but does
not fully guarantee bitwise determinism across Ollama builds and hardware. We additionally flag that
an Ollama tag is not a frozen checkpoint digest; pinning exact per-model quantization build hashes is
a pre-submission task (`plan/TRIPOD-LLM-checklist.md` §4).

### Competency scorers

The scoring core is an LLM-as-judge competency rubric implemented in `src/aivmt/scoring/`. It
comprises three scorers, each emitting a strict JSON object validated against an exact schema with
numeric range guards. The **SEGUE communication scorer** (`segue.py`) rates five anchored
communication domains — *set the stage*, *elicit information*, *give information*, *understand
perspective*, and *end the encounter* — using bilingual (English/Chinese) system and user prompts.
The **history-completion checklist scorer** (`checklist.py`) rates coverage of the case-specific
history-taking checklist. The **reasoning scorer** (`reasoning.py`) rates out-loud clinical
reasoning. All scores lie in [0, 1]. The composite overall score is a fixed weighting of
history-checklist 0.4, SEGUE communication 0.4, and reasoning 0.2 (`conf/config.yaml`). Scorers are
constructed through a registry/factory (`src/aivmt/scoring/base.py`, `ScorerFactory`) and support
two prompt variants: `zero_shot` (the primary method, byte-identical to the original anchored-rubric
prompts) and `few_shot`, which prepends explicitly-labelled synthetic worked exemplars via
`build_exemplar_block`. The few-shot variant is implemented and unit-tested at the scorer level but
is **not yet wired into the harness or configuration system**, so it is currently reported only
within the robustness lane (below) and not as an end-to-end harness arm (`plan/TRIPOD-LLM-checklist.md`
§4). The verbatim prompts are version-controlled in source and should be reproduced in a supplement.

### Case-authoring portal

A teacher-facing case-authoring web portal (`src/aivmt/portal/`, a FastAPI application rooted at
`conf/case`) lets faculty author SP cases without engineering support. Cases are expressed against a
frozen-dataclass case schema (`src/aivmt/case_schema.py`: demographics, history of present illness,
and related fields), linted (`src/aivmt/case_lint.py`), and compiled into an SP persona by the
persona compiler (`src/aivmt/persona.py`). Several clinical fields are honestly stubbed as
`TODO_COLLAB` pending OB/GYN faculty sign-off.

### Blinded faculty-scoring portal

A separate faculty-scoring web portal (`src/aivmt/faculty_portal/`) serves de-identified evaluation
transcripts to faculty raters and appends their ratings to a rating sheet, by design **blinded** to
the system's automated score. This portal is the instrument for collecting the reference standard.
As of 2026-06-13 the rating sheet (`data/faculty_rating_sheet.csv`) is a blank template over the
evaluation encounters and the populated ratings file (`data/faculty_ratings.csv`) does not yet
exist, so the primary endpoint is pending (see Materials and Measures).

## Materials

The evaluation corpus is a set of **42 Chinese (zh) OB/GYN history-taking encounters**
(`data/eval_transcripts/`, 42 files; matched designed-quality answer keys in `data/eval_keys/`, 42
files). The 42 encounters are constructed as **three OB/GYN cases** — abnormal uterine bleeding
(`obgyn_aub_zh_01`), ectopic pregnancy (`obgyn_ectopic_zh_01`), and vaginitis
(`obgyn_vaginitis_zh_01`) — each instantiated at **14 graded-quality variants**, so that the corpus
spans a designed range of competency levels. Each transcript is generated by the platform's SP
persona engine from a collaborator-reviewed formal case (`conf/case/*.yaml`) and is therefore of
**synthetic provenance**: these are not real student–SP encounters, and no real patient data is
present. The corpus has already been scored by the platform (`data/encounters/`); a **30-encounter
re-scoring set** has additionally been scored by a medical-domain model for the medical-model
comparison (`data/encounters_huatuo/`), and this set is the basis for the HuatuoGPT frontier row
(matching `n_tx = 30` in `results/phase_model_frontier/model_frontier.md`). The corresponding **collection-day real zh transcripts have not been
gathered** — all current transcripts are synthetic, and the real-data collection setting and dates
are a collaborator decision (`plan/TRIPOD-LLM-checklist.md` §3).

The reference standard is **blinded faculty consensus** with **k = 3 raters**, in Chinese
(`HYPOTHESIS.md` lines 40–41). The faculty study is **designed and locked but not yet run**. The
unit of analysis is one encounter (one learner × one SP case). The pre-registered sample-size plan
(`HYPOTHESIS.md` lines 39–52) is reasoned on the 95% confidence-interval half-width of ICC(2,1) at
k = 3: a primary target of **n = 150 encounters × 3 raters** (half-width ≈ 0.07 at a conservative
ICC ≈ 0.70), a floor of n = 100, a staged pilot of ~25 transcripts to obtain the first real ICC and
a measured rater-minutes-per-rating before freezing the final n, and a contingency of n ≈ 40 if
recruitment falls below the floor. The final n is rater-hour-limited, not transcript-limited, and is
not frozen until the pilot measures rating burden.

## Measures

For the primary validity analysis we pre-specify a **full validity suite** (`HYPOTHESIS.md` lines
22–33), implemented in `src/aivmt/metrics/` and orchestrated by the scoring-validity phase in
`harness/registry.py`. The primary estimand is the absolute-agreement **ICC(2,1)** between system and
faculty consensus on the overall score, reported alongside **ICC(2,k)**, both with **McGraw & Wong
(1996) F-based 95% confidence intervals** (`src/aivmt/metrics/icc.py`) and an independent **seeded
bootstrap 95% CI** cross-check. The same agreement statistics are reported for every subscore (each
of the five SEGUE domains, the history-completion checklist, and reasoning). Ordinal-anchored items
are additionally summarized with **quadratic-weighted κ** (`src/aivmt/metrics/agreement.py`).
**Bland–Altman** analysis (`src/aivmt/metrics/bland_altman.py`) reports bias, 95% limits of
agreement, and a proportional-bias slope with its p-value. A **generalizability-theory** analysis
(`src/aivmt/metrics/gtheory.py`) decomposes variance components and runs a **D-study** projecting
reliability for k = 1..5 raters. **Decision consistency** (raw agreement plus Cohen's κ) is reported
at a pass/fail cut-score (default 0.6). The **faculty inter-rater ICC** is reported as the agreement
**ceiling** that bounds achievable system–faculty agreement (`HYPOTHESIS.md` line 33). The metrics
machinery is exercised on fixtures and runs end-to-end; it produces real numbers as soon as faculty
ratings are supplied, but until then **all faculty-anchored measures above are pending** and are
reported as explicit placeholders.

## Comparators and robustness analyses

Around the primary frontier we run five supporting analyses, four of them registered harness phases
(`phase_robustness`, `phase_asr_robustness`, `phase_quant_frontier`, `phase_local_vs_cloud` in
`harness/registry.py`); the model-size frontier is produced by the same quant-frontier runner and
written to `results/phase_model_frontier/` without a separate phase registration. All five are scored
against the **designed synthetic-quality gold** (an internal quality ordering of the graded
encounters), not against faculty — a distinction we preserve everywhere these numbers appear.

- **Model-size frontier** (`results/phase_model_frontier/`): five open-weight models from 3B to 14B
  parameters, each scoring the 30-encounter zh synthetic set, reporting ICC against the synthetic
  gold together with median and p90 latency, loaded memory, and on-disk footprint. The set includes
  general-purpose and medical-domain 8B models to test whether medical pre-training helps at fixed
  footprint.
- **Quantization frontier** (`results/phase_quant_frontier/`): one 7B model at FP16, Q8_0, Q4_K_M,
  and Q3_K_M, reporting the same validity-cost surface, to locate where quantization degrades
  agreement versus footprint.
- **Local-versus-cloud head-to-head** (`results/phase_local_vs_cloud/`): the local 8B model against
  a cloud comparator on the same synthetic set, reporting overall and per-SEGUE-domain ICC and a
  pre-registered **non-inferiority** test at margin δ = 0.10. A provenance guard
  (`src/aivmt/cloud/provenance.py`) hard-refuses transmitting any non-off-device-safe data to a
  cloud endpoint; only synthetic/de-identified material is ever sent. The non-inferiority claim is
  **conditional** per `HYPOTHESIS.md` (lines 34–37): it is dropped unless the pilot point estimate
  clears ~0.80.
- **ASR-noise robustness** (`results/phase_asr_robustness/`): the scorer applied to transcripts
  deterministically corrupted to graded Character-Error-Rate (CER) levels, tracing the
  ICC-versus-CER degradation curve (`src/aivmt/asr/`).
- **Prompt and seed robustness** (`results/phase_robustness/`): paraphrase sensitivity across six
  system-prompt rewordings, and test–retest reliability across repeated scorings at temperatures 0.0
  and 0.3, in both zero-shot and few-shot variants (`src/aivmt/robustness/`).

## Governance and reproducibility

The project operates under a hard reproducibility invariant (`plan/STORY_LOCK.md`, "Definition of
done"): **every number in the manuscript must regenerate** from `phase.benchmark()` outputs via
`python -m harness.evidence_table`, and `python -m harness.run_all` must exit 0 with negative
controls firing. A single seed (42) is the sole source of truth (`configs/seed.yaml`,
`harness/registry.py:load_seed`) and is never hardcoded in analysis code. **Negative controls** are
required to fire: on a synthetic fixture, true encounter–gold pairing yields a high overall ICC
(0.957) while a shuffled pairing collapses it to ~0 (0.019), and degenerate inputs produce an
explicit `nan` rather than a silent number (`harness/sanity/`). The primary scoring-validity phase
returns `status: PENDING_REAL_DATA` until faculty ratings exist. Reporting follows the **TRIPOD-LLM**
guideline for studies using LLMs in healthcare [CITE: Gallifant J, et al. TRIPOD-LLM reporting
guideline, Nature Medicine 2025 — VERIFY author list/title/DOI], tracked item-by-item in
`plan/TRIPOD-LLM-checklist.md` (32 rows; 9 Done, 15 Partial, 11 TODO_COLLAB as of 2026-06-13). The
closest prior art we position against — cloud AI-SP scoring systems reporting high faculty agreement,
hardware-heavy embodied SPs, and a recent review noting the absence of any offline/edge SP — is named
in `plan/STORY_LOCK.md` [CITE: AMTES / Liu 2025 JMIR Med Educ e73419; Voigt 2025; Borg robot SP; Sun
2026; 2026 SP review — resolve all against the published record].
