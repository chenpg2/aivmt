# Pre-Registration v0.1 — Tier B (validity-anchored)

> Study for a Research Article → **npj Digital Medicine**, collection *"Transforming Medical
> Education through Artificial Intelligence"* (deadline 2026-07-24). Lock BEFORE data collection;
> log any deviation. Companion design doc: `plan/protocol-v0.1.md`.
> Legend: **[LOCKED]** decided · **[PENDING-COLLAB]** needs the 3 collaborator numbers · **[TODO]** to compute.

## 1. Title (working)
*The first standardized patient on a local open-weight LLM behind a sub-$20 voice device: validity
of automated competency scoring against faculty, and a same-brain test of voice embodiment.*

## 2. Authors / roles
CS lead (you) — system, analysis. **Clinical collaborator (co-author)** — cases, validated
checklists, faculty raters, clinical framing. [PENDING-COLLAB confirm]

## 3. Study type [LOCKED]
Prospective **validation study** (primary) with an **embedded same-brain embodiment ablation**
(secondary) and a **cost/equity analysis** (descriptive). Pre-registered, single-site.

## 4. Hypotheses [LOCKED]
- **H1 — PRIMARY (validity).** Automated competency scores produced by the **local open-weight
  model** agree with blinded faculty expert scores at a clinically useful level. The **single
  primary endpoint is ICC(2,1) ≥ 0.75** (absolute agreement, two-way random) between system and
  faculty consensus — matching this prereg's own power basis (§11 l.108, l.116: ICC(2,1), k=3)
  and the locked realistic target in `plan/PROJECT_PLAN.md` l.67. **ICC(2,k) ≥ 0.75** is reported
  as a **secondary** agreement summary, not the primary. **Non-inferiority is CONDITIONAL, not
  co-primary:** the non-inferior-to-cloud claim (AMTES-class ICC≈0.92, pre-specified
  **non-inferiority margin δ = 0.10**, one-sided 97.5% CI) is carried forward **only if the pilot
  point estimate clears ~0.80** (per `plan/PROJECT_PLAN.md` l.67). See deviation **D1** (§15).
- **H2 — SECONDARY (embodiment).** Compared with an on-screen chatbot driven by the **identical
  local model**, the embodied voice device differs in engagement, perceived realism (MaSP), and
  usability (SUS). Direction pre-specified as **device ≥ screen** for engagement/realism; analysis
  two-sided. ⚠️ A null is informative ("is a faceless voice puck enough vs an expressive robot?").
- **H3 — cost (descriptive).** Per-encounter marginal cost of the edge deployment is ≈ $0 vs
  ~$3/10-min for cloud voice and ≫ for human SP; offline operation demonstrated.

## 5. Design [LOCKED]
- **Validity (H1):** every recorded encounter is scored by BOTH the system and ≥2 blinded faculty.
- **Embodiment (H2):** within-subjects, **counterbalanced** — each student does difficulty-matched
  but DIFFERENT cases under each condition (embodied / screen) via a **Latin-square** case×condition
  ×order assignment (controls carryover + case confound).
- Optional anchors (resource-permitting): a cloud-model and/or human-SP reference for H1 ceiling.

## 6. Participants & units
- **Students:** clinical-year medical students. Target **n = 40–50**. [PENDING-COLLAB #1]
- **Faculty raters:** **≥2–3** clinician-educators (gold standard + inter-rater reliability). [PENDING-COLLAB #2]
- **Cases:** **≥3** difficulty-graded (e.g., simple/moderate/complex), collaborator-validated, with
  named history-taking checklists. [PENDING-COLLAB #3]
- **Primary statistical unit = the scored ENCOUNTER.** Target **~120–150 encounters**
  (≈ n students × 3 cases) — this, not student n, powers the validity claim (cf. AMTES n=31/93 sessions).
- Inclusion: enrolled clinical-phase students who consent. Exclusion: incomplete encounters, audio
  failure precluding transcription, prior exposure to the system.

## 7. System / materials [LOCKED design, model TBD by pre-specified rule]
- **Embodied:** ESP32-S3 (16MB/8MB) xiaozhi front-end → wake → streaming ASR → LLM → TTS → speaker.
- **Brain (local):** self-hosted server, **open-weight LLM** + local ASR (FunASR/Sherpa) + TTS.
- **Screen comparator:** same backend/model via laptop/phone voice client (isolates embodiment).
- **Patient sim:** per-case persona + history via system prompt + RAG over the case file; withholds
  info the student must elicit.
- **Automated scoring:** transcript → (a) history-taking checklist completion, (b) communication
  scale items, (c) out-loud reasoning probe; outputs score + structured feedback.

## 8. Open-model selection — pre-specified rule (anti-cherry-pick) [LOCKED procedure]
- Candidate models (frozen now): **Qwen2.5-14B-Instruct, Qwen2.5-7B-Instruct, Llama-3.1-8B-Instruct,
  and one medical-tuned open model (HuatuoGPT-o1-8B; fallback MMed-Llama-3-8B)** — all open-weight,
  edge-servable. ASR (FunASR/Sherpa) + TTS components also frozen.
- **AMENDMENT A1 (2026-06-10, BEFORE any real data; user-approved headline change):** the primary
  analysis is reframed as a **validity–cost frontier** — agreement with faculty is estimated per
  model **size tier** to locate where faculty-level validity (ICC≥0.75) emerges/collapses.
  (a) **gpt-oss:20b is ADDED** as the upper-tier anchor (rationale: largest locally-servable
  candidate; passed the synthetic floor pilot ICC 0.904, parse 100%). (b) **Qwen2.5-3B-Instruct is
  ADDED** as a lower-tier exploratory point to probe the collapse region. (c) The model-SELECTION
  rule for the deployed system is unchanged (highest pilot ICC, all candidates reported); the
  frontier reports ALL tiers regardless of selection. (d) Per-model **cost descriptors** (params,
  quantized size, VRAM/RAM, $/encounter at measured latency) are locked as the frontier's x-axis.
- Selection on a **held-out W2 pilot set** of expert-scored transcripts; criterion = **highest
  ICC vs pilot expert scores**, decided BEFORE the main study; the chosen model is then frozen.
- Report all candidates' pilot ICCs (no post-hoc swapping).

## 9. Measures / instruments [LOCKED]
- **Communication:** **SEGUE** (25 items, 5 domains; concise → minimizes faculty scoring time;
  already used by Sun 2026 AI-VSP). Calgary-Cambridge held as alternative if collaborator prefers.
- **History-taking:** named validated checklist (collaborator).
- **Realism/fidelity:** MaSP. **Usability:** SUS (+ optional CUQ).
- **Engagement:** behavioral (time-on-task, #questions, voluntary reps) + self-report.
- **Learning/confidence:** brief pre/post self-efficacy (secondary).
- **Telemetry:** ASR WER, end-to-end latency, technical reliability.

## 10. Analysis plan [LOCKED]
- **H1 (primary):** the **single primary endpoint is ICC(2,1)** (agreement, two-way random,
  absolute) with 95% CI between system and faculty consensus — the metric §11 (l.108, l.116) powers,
  per `plan/PROJECT_PLAN.md` l.67. **ICC(2,k)** with 95% CI is reported as a **secondary** agreement
  summary. **Weighted κ** for ordinal checklist items; **Bland–Altman** (bias + LoA). Non-inferiority
  vs cloud benchmark using margin δ (one-sided 97.5% CI) is **CONDITIONAL** — carried only if the
  pilot ICC clears ~0.80 (`plan/PROJECT_PLAN.md` l.67), not a co-primary test. Report faculty
  **inter-rater ICC** as ceiling. See deviation **D1** (§15).
- **H2 (secondary):** **linear mixed-effects** models — fixed: condition, case-difficulty; random:
  student, case (and rater where applicable). Report standardized effect sizes + 95% CI. SUS via
  paired test. Pre-specified primary embodiment outcome = **engagement composite** = z-scored mean
  of {time-on-task, # relevant questions asked, # voluntary practice repetitions}.
- **H3:** TCO model (device BOM + shared server + open-model inference) vs cloud $/min × encounter
  length × cohort × attempts, and human-SP hourly cost; empirical offline demo.
- **Multiplicity:** H1 primary; H2/H3 secondary/exploratory — control or label as exploratory.
- **Missing data:** report rates; complete-case for primary; sensitivity analysis if >10% missing.

## 11. Sample-size / precision justification
**Inputs known (collaborator, 2026-06-09):** transcripts ample; **k = 3 faculty raters**; language zh.
Monte-Carlo 95% CI half-width of ICC(2,1), k=3 (power simulation):

| expected ICC | n=80 | n=100 | n=150 | n=200 |
|---|---|---|---|---|
| 0.6 | 0.112 | 0.099 | 0.082 | 0.069 |
| 0.7 | 0.092 | 0.081 | 0.069 | 0.058 |
| 0.8 | 0.068 | 0.060 | 0.049 | 0.044 |

- **Primary target (locked): n = 150 encounters × 3 raters** → 95% CI half-width ≈ **0.07 at a conservative ICC≈0.70** (≈0.05 if ICC≈0.80). Transcripts are ample → n is rater-hour-limited, not transcript-limited.
- **Rater-burden gate:** 150×3 = 450 ratings ≈ **15–20 h/rater** at ~6–8 min/rating. Confirm against committable hours; if limited, **n=100 is the floor** (CI≈0.08 @0.70 / 0.06 @0.80).
- **Staged:** pilot ~25 transcripts → first REAL ICC + measured min/rating; then scale to n=100–150 and freeze the final n here before the main batch.
- Embodiment (SQ2 stretch): powered separately if that lane runs.

## 12. Blinding & integrity [LOCKED]
- Faculty raters blinded to condition AND to the system's score; score de-identified transcripts/recordings.
- Randomization/counterbalancing pre-generated. Analyst blinded to condition labels where feasible.
- Pre-registration timestamped before any main-study data; deviations logged with rationale.

## 13. Ethics [LOCKED]
- Conducted under collaborator's **umbrella IRB**; confirm scope covers "student interaction +
  faculty retrospective transcript scoring." [PENDING-COLLAB confirm]

## 14. What's locked vs what unblocks the rest
- **Unblocks final n, power, timeline:** the 3 collaborator numbers (students / raters / cases) + δ + ICC-CI target.
- Everything else (design, hypotheses, instruments, analysis, model-selection rule, blinding) is locked here.

## 15. Deviation log [per §12 l.124]
- **D1 (2026-06-12, documentation reconciliation; BEFORE any real data).** §4 (H1) and §10 (H1
  analysis) are reconciled to name **ICC(2,1) ≥ 0.75 as the single primary endpoint**, with
  **ICC(2,k) demoted to a secondary** agreement summary and the **non-inferiority-vs-cloud test
  demoted from co-primary to CONDITIONAL** (carried only if the pilot point estimate clears ~0.80).
  **Rationale:** §4/§10 previously named ICC(2,k) ≥ 0.75 primary with non-inferiority (δ=0.10) as
  co-primary, which disagreed with (a) this prereg's own power basis — §11 l.108/l.116 power on the
  95% CI half-width of **ICC(2,1), k=3**; (b) the locked realistic target in `plan/PROJECT_PLAN.md`
  l.67; and (c) the downstream `AIVMT/HYPOTHESIS.md`, already reconciled to ICC(2,1) primary. **No
  numbers, margins, or sample sizes changed** — wording reconciliation only: ICC(2,k) and the
  non-inferiority margin δ = 0.10 are still reported, now at their correct tier (secondary /
  conditional).
