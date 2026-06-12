# HYPOTHESIS — SQ1 (primary): local-model competency-scoring validity

Serves **SQ1** in `plan/STORY_LOCK.md`. (H2/H3 get their own HYPOTHESIS files when those phases start.)
Reconciled with `plan/preregistration-v0.1.md` §4/§8/§10/§11 and the locked realistic target in
`plan/PROJECT_PLAN.md` (SQ1 row, l.67). Cited prereg/plan line numbers are load-bearing.

## Hypothesis
Automated competency scores produced by a **local open-weight model** (served via Ollama,
e.g. gpt-oss:20b) agree with blinded faculty expert scores at a clinically useful level on
history-taking encounters.

## Null hypothesis
No better-than-chance agreement between the local-model automated scores and faculty scores
(ICC ≈ 0); equivalently, agreement is no different from the shuffled-pairing negative control.

## Variables
- Independent: the scorer (local-model automated vs faculty consensus).
- Dependent: overall competency score AND its subscores — the five SEGUE communication domains,
  history-taking checklist completion, and out-loud reasoning — all in [0,1].
- Controlled: identical transcripts, identical rubric/checklist, fixed model + temperature 0, fixed seed.

## Statistical test (pre-registered)
- **Primary endpoint (locked, realistic target — prereg §4 l.22–24 reframed by PROJECT_PLAN l.67):**
  two-way random-effects, absolute-agreement **ICC(2,1) ≥ 0.75** between system and faculty
  consensus is the **single primary endpoint** ("clinically useful absolute agreement").
- **Full validity suite (prereg §10 l.85–88), reported alongside:** ICC(2,1) AND ICC(2,k) with
  **McGraw & Wong (1996) F-based 95% CI** for the overall score and for every subscore (per SEGUE
  domain + checklist + reasoning); a **seeded bootstrap 95% CI** as an independent cross-check;
  pairwise system-vs-each-rater ICC; **weighted κ** (quadratic) for the ordinal-anchored items;
  **Bland–Altman** (bias, 95% limits of agreement, proportional-bias slope + p); **generalizability
  theory** variance components with a **D-study** projecting reliability for k = 1..5 raters; and
  **decision consistency** (raw agreement + Cohen's κ) at a pass/fail cut-score (default 0.6).
- **Faculty inter-rater ICC** reported as the agreement **ceiling** (prereg §10 l.88).
- **Non-inferiority is CONDITIONAL, not primary (PROJECT_PLAN l.67):** the non-inferiority-vs-cloud
  claim (AMTES-class ICC ≈ 0.92, margin **δ = 0.10**, one-sided 97.5% CI; prereg §4 l.23–24) is
  **dropped unless the pilot point estimate clears ~0.80** — it is dead on arrival at a realistic
  ICC near 0.6–0.7, so it is only carried forward if the pilot warrants it.

## Sample size / power
**Inputs locked (collaborator, prereg §11 l.99):** transcripts ample; **k = 3 faculty raters**;
language **zh**. Power is on the 95% CI half-width of **ICC(2,1), k=3** (prereg §11 l.100–108):
- **Primary target (locked): n = 150 encounters × 3 raters** → 95% CI half-width ≈ **0.07 at a
  conservative ICC ≈ 0.70** (≈ 0.05 if ICC ≈ 0.80) (prereg §11 l.108). n is rater-hour-limited,
  not transcript-limited.
- **Floor: n = 100** (CI ≈ 0.08 @0.70 / 0.06 @0.80) if the rater-burden gate binds (prereg §11 l.109).
- **Staged:** pilot **~25 transcripts** → first real ICC + measured min/rating, then scale to
  n = 100–150 and freeze final n before the main batch (prereg §11 l.110).
- **Contingency: n ≈ 40, k = 3** — the minimal AMTES-comparable validation (AMTES n = 31/93 sessions,
  prereg §6 l.44 / §11 l.106; "v0.1's n ≈ 30–40", PROJECT_PLAN l.40) if recruitment falls below the
  floor; reported as a contingency, never the locked primary.
- The earlier **n ≈ 120–150 / ICC ≈ 0.85** framing is superseded: power is recomputed at the
  realistic ICC band 0.6–0.75 with ICC(2,1) as the endpoint.

## Amendment A1 — validity–cost frontier (prereg §8 l.62–73)
The primary analysis is reframed as a **validity–cost frontier**: agreement with faculty is
estimated **per model size tier** to locate where faculty-level validity (ICC ≥ 0.75) emerges or
collapses. **gpt-oss:20b** is the upper-tier anchor (synthetic floor pilot ICC 0.904, parse 100%);
**Qwen2.5-3B-Instruct** is a lower-tier exploratory point probing the collapse region. The frontier
reports ALL tiers regardless of which model is selected for deployment.

## Seed
From `configs/seed.yaml` (currently 42). Never hardcoded in analysis code; the bootstrap CI and all
synthetic fixtures draw from it.

## Multiple comparisons / correction
**ICC(2,1) is the single primary endpoint.** Subscores (SEGUE domains, checklist, reasoning), the
validity-cost frontier tiers, and SQ2/SQ3 are secondary/exploratory and labeled as such. The
non-inferiority test is conditional (see above), not an additional primary comparison. No fishing
across thresholds.
