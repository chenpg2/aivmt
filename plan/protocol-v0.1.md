# Study Protocol v0.1 — Low-Cost Embodied Voice "AI Standardized Patient"

> Working draft for a Research Article targeting **npj Digital Medicine**, collection
> *"Transforming Medical Education through Artificial Intelligence"* (deadline **2026-07-24**).
> Language: English (the eventual paper is English). Status: **DRAFT** — Related Work and
> Instruments sections are pending the background literature scan (`a6ef…`).
> 中文沟通照旧;本文档用英文是因为投稿是英文,需要可改。

---

## 1. Working title
*Democratizing clinical-communication training: validity and embodiment of a sub-$20 voice
"AI standardized patient" running on a local open-weight model.*

## 2. One-paragraph thesis
LLM-based virtual standardized patients (SPs) can already train history-taking and
communication, but every validated system depends on **expensive cloud models (GPT-4o /
DeepSeek) on phones/PCs/VR** — pricing out the low-resource and LMIC schools that most lack
human SPs. We build an **ultra-low-cost embodied voice SP**: a ~$15 ESP32-S3 device as the
hands-free voice front-end, driven by a **single local, self-hosted open-weight LLM server**
(no per-query cloud cost, offline-capable, data stays on-premises). We test two questions the
prior literature leaves open: **(A) does automated competency feedback retain validity — i.e.,
agreement with faculty experts — under this low-cost/edge constraint?** and **(B) does physical
voice embodiment change engagement, perceived realism, and communication outcomes versus an
on-screen chatbot with the same model brain?**

## 3. Novelty axes (LOCKED by literature scan — verdict: REAL gap, partial per-axis → defend the COMBINATION + two controlled tests)
**Positioning (1 sentence):** Prior LLM-SPs establish faculty-level automated scoring only on *cloud*
models (AMTES ICC≈0.92–0.98; Holderried κ=0.832) and show embodiment benefits only with a costly
cloud-driven social robot (Borg — which itself leaves *"physical robot vs LLM-alone"* unanswered);
we present the first SP running entirely on a single self-hosted **open-weight** LLM behind a
**sub-$20 ESP32-S3 voice device** — removing the ~$0.30/min cloud-voice cost, keeping data
local/offline, with a **same-brain controlled design** to isolate embodiment while validating
**local-model** competency scoring against faculty.
- **Axis A — local-open-weight scoring validity (SHARPEST gap).** No published LLM-SP has shown
  faculty-level scoring validity on a small/local/open model; benchmark against cloud ICC≈0.92 /
  κ≈0.83. **Pre-register the agreement target.**
- **Axis B — same-brain embodiment ablation.** Physical voice device vs on-screen chatbot, identical
  local model — answers Borg's open question. ⚠️ Borg's gains came partly from an expressive animated
  FACE; a faceless voice puck may not reproduce them — **test, don't assume** (a null is still
  informative: *"is cheap faceless voice enough?"*).
- Each component alone has prior art → **lead with the combination + the two tests, never a single component.**

## 4. Research questions & hypotheses
- **RQ1 (validity).** Agreement between the system's automated competency scores and blinded
  faculty expert scores. *H1: substantial agreement (e.g., ICC(2,k) ≥ 0.75 / weighted κ ≥ 0.6),
  non-inferior to a cloud-model reference.*
- **RQ2 (embodiment).** Difference between embodied-device vs same-model screen condition on
  engagement (behavioral + self-report), perceived realism, usability, and communication score.
  *H2: embodied condition ≥ screen on engagement/realism (direction to be pre-registered).*
- **RQ3 (cost/equity).** Classroom total-cost-of-ownership and offline capability of the
  local-model deployment vs cloud-LLM and human-SP baselines. *Descriptive/analytic.*

## 5. System architecture
- **Front-end (embodied):** ESP32-S3 (16MB/8MB, confirmed) running xiaozhi firmware; mic →
  wake → streaming ASR → LLM → TTS → speaker; small display for state/persona.
- **Backend (the "brain", local):** self-hosted `xiaozhi-esp32-server` on a modest local box
  (mini-PC / single GPU) running an **open-weight model** (e.g., Qwen/DeepSeek-distill class) +
  local/edge ASR (FunASR/Sherpa) + TTS. **No per-query cloud calls.**
- **Patient simulation:** per-case persona + medical history injected via system prompt + RAG
  over the case file; refuses to volunteer info the student must elicit.
- **Automated competency scoring:** maps the transcript to (a) case-specific **history-taking
  checklist** completion, (b) **communication** scale items, (c) an **out-loud reasoning** probe
  ("state your differential and why") scored for structure — produces a score + structured
  feedback. Scoring rubric mirrors the validated instruments in §8.
- **Screen comparator:** identical backend/model, delivered via a phone/laptop voice/text client
  (isolates embodiment, holds the "brain" constant).

## 6. Design
- **Within-subjects, counterbalanced crossover.** Each student completes encounters in **both**
  conditions (embodied / screen) using **difficulty-matched but different cases** (Latin-square
  case×condition assignment to control carryover and case confound).
- **Reference anchors (optional, resource-permitting):** a human-SP and/or cloud-GPT-4o ceiling
  for the validity comparison.
- **Blinding:** faculty raters score de-identified transcripts/recordings blind to condition and
  to the system's score.

## 7. Participants
- Medical students in clinical years (collaborator-provided cohort; **umbrella IRB available**).
- Target **n ≈ 80–120 medical students** to match the venue's empirical bar (recent npj DM med-ed
  RCTs run **n≈88–111** — see §14 Benchmark; an n=40 RCT lands in Frontiers, not npj DM). Final n
  from a power calc; **pending collaborator recruitment capacity within the 6.5-wk window (key decision).**
- Faculty expert raters: ≥2 clinician-educators (for inter-rater reliability + gold standard).

## 8. Measures & instruments  *(LOCKED from scan — adopt NAMED validated instruments, outclassing the field's custom-rubric norm)*
- **Communication:** **Calgary-Cambridge Guides** (field standard) or **SEGUE** (25 items; used by Sun 2026 AI-VSP).
- **History-taking:** named structured checklist keyed to a licensing syllabus (collaborator-validated), not ad-hoc.
- **SP realism/fidelity:** **MaSP** (Maastricht Assessment of Simulated Patients).
- **Usability:** **SUS** (target ≥80) and/or **CUQ** (Chatbot Usability Questionnaire).
- **Engagement:** behavioral (time-on-task, # questions, voluntary practice reps) + self-report scale.
- **Learning/confidence:** brief pre/post self-efficacy (secondary).
- **System telemetry:** ASR word-error-rate, end-to-end latency, technical reliability.

## 9. Analysis plan
- **RQ1:** ICC(2,k) for continuous scores; weighted κ for ordinal checklist items;
  Bland–Altman for system-vs-faculty agreement; non-inferiority margin pre-specified.
- **RQ2:** mixed-effects models (fixed: condition, case-difficulty; random: student, case) for
  each outcome; report standardized effect sizes + 95% CIs; SUS compared with t-test/Wilcoxon.
- **RQ3:** TCO model. Cloud reference: GPT-4o realtime voice ≈ $0.06/min in + $0.24/min out ≈
  **~$0.30/min → ~$3 per 10-min encounter, recurring per student/attempt**; human-SP ≈ hourly wage.
  Ours: **~$0 marginal** after ~$15–20/device + one shared local server (open model). Demonstrate
  offline capability empirically.
- Pre-register hypotheses/analysis before data collection.

## 10. Timeline (reverse-planned from 2026-07-24; ~6.5 weeks, near-zero slack)
| Week | Dates | Goal |
|------|-------|------|
| W1 | Jun 9–15 | Lock novelty (scan), finalize cases+checklists w/ collaborator, freeze design, IRB amendment if needed |
| W2 | Jun 16–22 | Build: firmware + local-model server + scoring pipeline + screen client; internal pilot (2–3 testers) |
| W3 | Jun 23–29 | Run student sessions (both conditions); record encounters |
| W4 | Jun 30–Jul 6 | Blinded faculty scoring; finish cost analysis |
| W5 | Jul 7–13 | Analysis + figures |
| W6 | Jul 14–20 | Write Research Article; internal review |
| Buffer | Jul 21–24 | Revise + submit |
- **De-scope lever:** if the embodiment arm under-recruits, the validity+cost paper stands alone.

## 11. Risks & mitigations
| Risk | Mitigation |
|------|------------|
| Novelty already taken | Background scan FIRST; reposition before building |
| 6.5-week window too tight | Within-subjects single-collection covers both axes; embodiment is the de-scope lever |
| Local/open model too weak for scoring validity | Benchmark a few open models in W2; fall back to a stronger local model; report the validity–cost frontier honestly |
| Faculty rater availability | ≥2 raters, retrospective transcript scoring (async, fits umbrella IRB) |
| Toddler/student-speech ASR errors | Report WER; constrain cases; human-checked transcripts for scoring |
| MCU cannot run an LLM (architecture honesty) | Frame cost claim as "device + one shared local server", not on-MCU inference |
| **Borg face-confound** — faceless voice puck may NOT beat screen (Borg's gain partly from animated face) | Design embodiment arm to TEST not assume; pre-register; a null = "is cheap faceless voice enough?" is still publishable |
| **AMTES validity bar** (cloud ICC≈0.98) — local model may fall short | Benchmark several open models in W2; pre-register agreement target; report the validity–cost frontier honestly |
| **Field moving fast** (many 2026 LLM-SP papers; a local/edge SP could appear pre-submission) | Monitor arXiv/JMIR + Awesome-LLM-Patient-Simulators repo through 2026-07-24 |

## 12. Authorship / credibility
- Clinical collaborator as co-author (provides cases, validated checklists, faculty raters, and
  clinical framing). npj DM editors are MDs — clinical co-authorship materially strengthens the
  submission. Consider alignment with the guest editors' areas.

## 14. Venue benchmark — what the collection/journal actually publishes (evidence)
Assembled from search indexing (collection TOC is SSO-locked; ✅ = confirmed in-collection, 🟡 = same-journal peer used to calibrate the bar):
- ✅ *What the AI-era doctor should know* — scoping review, PRISMA-ScR, 4071 screened → 54 studies/22 countries (s41746-026-02761-9).
- ✅ *AI-PACE* — conceptual framework, 12pp, 2 fig/2 tbl, **no empirical data** (s41746-026-02768-2).
- ✅ *Bridging the mentorship divide* — predictive-LLM equity analysis of student writing (s41746-025-02167-z).
- 🟡 *AI misinformation & diagnostic accuracy* — **RCT, n=111** (s41746-026-02547-z).
- 🟡 *Immersive competence / VR assessment bias* — **3-arm RCT, n=88**, reports d=0.67, p=0.010 (s41746-026-02482-z). ← methodological template for our embodied-vs-screen arm.
- 🟡 *Generative AI teaching assistant (RAG)* — empirical deployment across two cohorts (s41746-025-02022-1).
- Contrast: an AI-learning **RCT n=40 → Frontiers in Medicine**, not npj DM.

**Bar read:** collection accepts reviews + conceptual frameworks + empirical studies; the empirical bar = randomized/prospective design with **n≈88–111 students**, validated instruments, effect sizes + CIs, frequently multi-arm, with a fairness/bias lens. **Implication:** our study must scale to ~n80–120, multi-arm, validated instruments, blinded validity sub-study, and an equity/bias framing — materially heavier than v0.1's n≈30–40.

## 13. Open TODOs
- [ ] Ingest literature-scan report → finalize §3 novelty, §8 instruments, Related Work
- [ ] Power calculation → fix n (§7)
- [ ] Confirm with collaborator: cases, checklists, rater availability, IRB scope
- [ ] Pick open model(s) to benchmark for scoring validity
- [ ] Pre-registration draft

## 15. Workload tiers (DECISION — gated on collaborator recruitment capacity)
Note: venue empirical bar = intervention RCTs **n≈88–111** (judged by participant n); a **validity study**
is judged differently — by # encounters × # raters × ICC precision (cf. AMTES n=31/93 sessions).

- **Tier A — match the intervention-RCT bar (highest acceptance, highest risk).** 2-arm RCT
  (embodied vs same-model screen), **n≈90–120 students**, validated instruments, blinded validity
  sub-study, cost/equity. Needs ~100 students recruited + run + scored in 6.5 wk — aggressive.
- **Tier B — validity-anchored (RECOMMENDED).** Headline = **first local-open-weight scoring
  validity vs faculty** (power by ENCOUNTERS: ~40–50 students × ~3 cases × ≥2–3 raters → ~120–150
  scored encounters → tight ICC CI) + **embodiment ablation as powered-if-possible secondary** +
  cost/equity analysis. Strongest novelty, least recruitment-bound, fits 6.5 wk.
- **Tier C — fallback.** Strong **Perspective** now (positioning + working prototype + cost
  argument) → empirical paper to a later npj DM window.

**Recommendation:** start on **Tier B**; upgrade to Tier A if collaborator can recruit ~100 students.
**Gating inputs needed from collaborator:** (1) # students recruitable in 6.5 wk; (2) # faculty raters; (3) # cases available.

## 16. Key prior art to cite (from scan)
- Validity (cloud): AMTES — Liu 2025 JMIR Med Educ e73419 (ICC 0.92–0.98); Holderried 2024 e59213 (κ=0.832); AMTES real-world 2026 e89367.
- Embodiment (RED FLAG): Borg 2025 JMIR 10.2196/63312 + 2026 Front AI 10.3389/frai.2026.1795842 (Furhat robot + cloud GPT-3.5; "robot vs LLM-alone" left open).
- Low-cost/feedback rhetoric: Voigt 2025 arXiv 2508.13943. Voice SP: SEGUE AI-VSP Sun 2026; ChatGPT-4o voice Cureus 2025 (PMC12175028).
- Reviews: 2026 systematic review JMIR Med Inform e79039 (39 studies, "cloud/API-dependent, no edge"); scoping review JMIR e79091.
- Watchlist: github.com/FreedomIntelligence/Awesome-LLM-Patient-Simulators.
