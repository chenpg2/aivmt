# AIVMT manuscript skeleton (auto-drafted)

This folder (`methods.md`, `results.md`) is an **auto-drafted IMRAD skeleton** for the AIVMT
submission to the *npj Digital Medicine* collection *"Transforming Medical Education through
Artificial Intelligence"* (submission deadline 2026-07-24). It was generated on 2026-06-13 by
reading every artifact under `results/`, `HYPOTHESIS.md`, `plan/STORY_LOCK.md`, and
`plan/TRIPOD-LLM-checklist.md`. The project's governance invariant holds here: **every numeric value
that appears in these files is traceable to a registered harness phase artifact under `results/`**,
and each number carries an inline source pointer (e.g. `(phase_quant_frontier)`). No number was
invented. The single most important caveat is that **the study's primary endpoint — agreement
(ICC(2,1)) between the local-model automated score and blinded faculty consensus — has not yet been
computed**: no faculty ratings exist on disk (`data/faculty_ratings.csv` is absent and
`data/faculty_rating_sheet.csv` is a blank template), so every faculty-dependent quantity is written
as an explicit bracketed `[... pending ...]` placeholder, and every absolute ICC currently on disk is
labelled as *agreement with the designed synthetic gold*, never as faculty validity. Citations to
prior art are placeholders in `[CITE: ...]` form grounded in the real comparators named in
`plan/STORY_LOCK.md`; they must be resolved against the published record before submission. Two
referenced governance files (`plan/preregistration-v0.1.md`, `plan/PROJECT_PLAN.md`) are cited
throughout `HYPOTHESIS.md` and the TRIPOD checklist but **do not exist on disk** as of 2026-06-13;
their §/line anchors are currently unresolvable and are flagged inline.
