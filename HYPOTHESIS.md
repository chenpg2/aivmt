# HYPOTHESIS — SQ1 (primary): local-model competency-scoring validity

Serves **SQ1** in `plan/STORY_LOCK.md`. (H2/H3 get their own HYPOTHESIS files when those phases start.)

## Hypothesis
Automated competency scores produced by a **local open-weight model** (served via Ollama,
e.g. gpt-oss:20b) agree with blinded faculty expert scores at a clinically useful level on
history-taking encounters.

## Null hypothesis
No better-than-chance agreement between the local-model automated scores and faculty scores
(ICC ≈ 0); equivalently, agreement is no different from the shuffled-pairing negative control.

## Variables
- Independent: the scorer (local-model automated vs faculty consensus).
- Dependent: overall competency score (and sub-scores: history-completion, SEGUE, reasoning) in [0,1].
- Controlled: identical transcripts, identical rubric/checklist, fixed model + temperature 0, fixed seed.

## Statistical test (pre-registered)
Two-way random-effects, absolute-agreement **ICC** — ICC(2,1) single and ICC(2,k) average — between
system and faculty over n encounters. Weighted kappa for ordinal checklist items. **Non-inferiority**
to the cloud benchmark (AMTES-class ICC ≈ 0.92) within margin **δ = 0.10** (one-sided 97.5% CI).
Decision threshold: ICC(2,1) ≥ 0.75 = clinically useful.

## Sample size / power
Powered by **encounters × raters**, not student n: target **~120–150 scored encounters**
(~40–50 students × ~3 cases) × ≥2–3 faculty raters → 95% CI half-width on ICC ≤ 0.07 at expected
ICC ≈ 0.85. (Pending collaborator recruitment numbers; see preregistration.)

## Seed
From `configs/seed.yaml` (currently 42). Never hardcoded in analysis code.

## Multiple comparisons / correction
SQ1 ICC is the single primary endpoint. Sub-scores and SQ2/SQ3 are secondary/exploratory and
labeled as such; non-inferiority uses the pre-specified δ. No fishing across thresholds.
