# Results

> Auto-drafted skeleton (2026-06-13). Every number below is copied from a registered harness phase
> artifact under `results/` and carries an inline source pointer. No number is invented. The primary
> endpoint (agreement with blinded faculty) is **not yet computed** and is shown as an explicit
> placeholder. Every absolute ICC drawn from a synthetic run is labelled *agreement with the designed
> synthetic gold*, which is **not** a faculty-validity number.

## SQ1 (primary) — agreement with blinded faculty consensus: PENDING

The primary endpoint is the absolute-agreement ICC(2,1) between the local-model automated score and
the consensus of k = 3 blinded faculty raters on Chinese OB/GYN history-taking encounters
(`HYPOTHESIS.md`, pre-registered threshold ICC(2,1) ≥ 0.75). **This number does not exist yet.** No
faculty ratings have been collected: `data/faculty_ratings.csv` is absent and
`data/faculty_rating_sheet.csv` is a blank k = 3 template over the 42-encounter evaluation set
(`phase_scoring_validity`, `results/evidence_table.md` reports
`status=PENDING_REAL_DATA`). The evaluation set is prepared and already scored by the system, awaiting
faculty.

```
PRIMARY RESULT (to be filled when faculty ratings are collected)
  Design: 42 zh OB/GYN encounters (3 cases x 14 graded variants) x k=3 blinded faculty raters
          (planned scale-up to n=150 encounters x 3 raters; floor n=100; pilot ~25; contingency n~40)
  Source phase: phase_scoring_validity (PENDING_REAL_DATA)

  Overall:            [FACULTY-ICC(2,1): pending]  (95% CI [pending], McGraw & Wong F-based)
                      [FACULTY-ICC(2,k): pending]  (95% CI [pending])
                      [BOOTSTRAP 95% CI: pending]
  Per subscore (ICC(2,1) vs faculty, all pending):
    set_the_stage          [pending]
    elicit_information     [pending]
    give_information       [pending]
    understand_perspective [pending]
    end_encounter          [pending]
    history_completion     [pending]
    reasoning              [pending]
  Faculty inter-rater ICC (agreement ceiling):        [pending]
  Weighted kappa (quadratic, ordinal items):          [pending]
  Bland-Altman (bias, 95% LoA, proportional slope+p): [pending]
  G-theory variance components + D-study (k=1..5):    [pending]
  Decision consistency at pass/fail cut 0.6
    (raw agreement + Cohen's kappa):                  [pending]
  Primary endpoint met (ICC(2,1) >= 0.75)?            [pending]
```

A harness fixture cross-check confirms the validity machinery and its negative control behave
correctly (these are **sanity fixtures, not model results and not faculty validity**): on correctly
paired synthetic encounters the overall ICC is **0.957**, and under shuffled pairing it collapses to
**0.019** (`phase_scoring_validity`, `results/evidence_table.md`).

## Supporting results (computed)

The following analyses are **real computed runs** (one local model per cell unless noted, n = 30,
seed 42), but each is scored against the **designed synthetic-quality gold**, not against faculty.
None of these is the validity claim.

### Model-size frontier (agreement with the synthetic designed-quality gold)

Five open-weight models, 3B–14B, scoring the 30-encounter zh synthetic set
(`phase_model_frontier`, `results/phase_model_frontier/model_frontier.md` and `.json`). The key
finding is that the **medical-domain 8B model (HuatuoGPT-o1) outperforms the general 8B model**
(ICC(2,1) 0.554 vs 0.424) at the same on-disk footprint, and that ICC increases with size up to 14B
in this run. **Note (artifact bug):** the source markdown carries a copy-pasted title
"Quantization frontier" although its body is the 5-model frontier.

| model | size | ICC(2,1) | ICC(2,k) | parse | median (s) | p90 (s) | RAM | disk |
|---|---|---|---|---|---|---|---|---|
| qwen2.5:3b | 3B | 0.248 | 0.398 | 1.000 | 2.178 | 2.886 | 3.4 GB | 1.9 GB |
| qwen2.5:7b | 7B | 0.351 | 0.520 | 1.000 | 5.629 | 8.902 | 6.6 GB | 4.7 GB |
| llama3.1:8b | 8B (general) | 0.424 | 0.596 | 1.000 | 7.223 | 9.810 | 22 GB | 4.9 GB |
| huatuogpt-o1:8b | 8B (medical) | **0.554** | 0.713 | 1.000 | 9.284 | 11.437 | 23 GB | 4.9 GB |
| qwen2.5:14b | 14B | **0.624** | 0.769 | 1.000 | 11.687 | 16.345 | 15 GB | 9.0 GB |

*Source: `phase_model_frontier`. ICC = agreement with the designed synthetic gold (NOT faculty).*

### Quantization frontier (agreement with the synthetic designed-quality gold)

One 7B model at four quantization levels (`phase_quant_frontier`,
`results/phase_quant_frontier/quant_frontier.md` and `.json`). **Q8_0 matches FP16 ICC exactly**
(0.410), at ~30% lower latency and roughly half the disk; ICC declines at Q4 and Q3.

| model | quant | ICC(2,1) | ICC(2,k) | parse | median (s) | p90 (s) | RAM | disk |
|---|---|---|---|---|---|---|---|---|
| qwen2.5:7b | FP16 | 0.410 | 0.581 | 1.000 | 9.020 | 13.092 | 16 GB | 15 GB |
| qwen2.5:7b | Q8_0 | 0.410 | 0.581 | 1.000 | 6.363 | 8.324 | 9.7 GB | 8.1 GB |
| qwen2.5:7b | Q4_K_M | 0.351 | 0.520 | 1.000 | 5.696 | 7.016 | 6.6 GB | 4.7 GB |
| qwen2.5:7b | Q3_K_M | 0.343 | 0.511 | 1.000 | 6.243 | 6.746 | 5.8 GB | 3.8 GB |

*Source: `phase_quant_frontier`. ICC = agreement with the designed synthetic gold (NOT faculty).*

### Local-versus-cloud head-to-head (agreement with the synthetic designed-quality gold)

The local 8B model against one cloud comparator (deepseek-v4-pro; the only cloud provider present in
the run) on the same synthetic set (`phase_local_vs_cloud`,
`results/phase_local_vs_cloud/local_vs_cloud.md` and `.json`). **Note (governance discrepancy):** the
working-tree copy of this artifact is deleted (git status `D`); the numbers below were recovered from
the committed HEAD version and may be mid-update by a concurrent run. `nan` denotes a degenerate cell
with no between-encounter variance (reported as an explicit `nan`, never a silent number).

| role | provider | overall | set_stage | elicit | give_info | understand | end | parse |
|---|---|---|---|---|---|---|---|---|
| local | llama3.1:8b | 0.424 | 0.483 | 0.636 | 0.114 | nan | nan | 1.000 |
| cloud | deepseek-v4-pro | 0.547 | 0.484 | 0.635 | 0.453 | nan | 0.097 | 1.000 |

On this synthetic set the local-minus-cloud overall ICC delta is **−0.123**, which **fails** the
pre-registered non-inferiority margin (δ = 0.10); the largest per-domain gap is *give information*
(delta −0.339) (`phase_local_vs_cloud`). Per `HYPOTHESIS.md` (lines 34–37), the non-inferiority test
is **conditional and is dropped unless the pilot clears ~0.80**, so this synthetic-gold delta is not
a faculty-anchored claim. A faculty-anchored non-inferiority result is `[NON-INFERIORITY vs cloud
(faculty-anchored): pending and conditional]`.

### ASR-noise robustness (agreement with the synthetic designed-quality gold)

The local 8B zero-shot scorer applied to transcripts deterministically corrupted to graded Character
Error Rate (CER), the standard zh ASR severity metric (`phase_asr_robustness`,
`results/phase_asr_robustness/asr_robustness.md` and `.json`). Agreement degrades monotonically from
**0.396 at clean (CER 0.000) to 0.250 at CER 0.342**.

| target | achieved CER | ICC vs gold | n |
|---|---|---|---|
| clean | 0.000 | 0.396 | 30 |
| 0.05 | 0.048 | 0.398 | 30 |
| 0.15 | 0.185 | 0.295 | 30 |
| 0.30 | 0.342 | 0.250 | 30 |

*Source: `phase_asr_robustness`. ICC = agreement with the designed synthetic gold (NOT faculty).*

### Prompt and seed robustness (synthetic gold; test–retest is internal stochasticity)

Two analyses on the local 8B model (`phase_robustness`,
`results/phase_robustness/robustness.md` and `.json`). **Test–retest** reliability across K = 3
repeated scorings is essentially perfect at temperature 0 (ICC 1.000 in both variants) and high at
temperature 0.3 (0.965 zero-shot, 0.921 few-shot). **Paraphrase sensitivity** — mean ICC-vs-gold
across six system-prompt rewordings — is **0.463 (SD 0.060)** zero-shot and **0.376 (SD 0.080)**
few-shot, i.e. few-shot lowers paraphrase agreement here.

| analysis | variant | temp | ICC | spread |
|---|---|---|---|---|
| test–retest (K=3) | zero_shot | 0.0 | 1.000 | mean CV 0.000 |
| test–retest (K=3) | zero_shot | 0.3 | 0.965 | mean CV 0.170 |
| test–retest (K=3) | few_shot | 0.0 | 1.000 | mean CV 0.000 |
| test–retest (K=3) | few_shot | 0.3 | 0.921 | mean CV 0.240 |
| paraphrase (6 rewordings, vs gold) | zero_shot | 0.0 | 0.463 mean | SD 0.060, range 0.157 |
| paraphrase (6 rewordings, vs gold) | few_shot | 0.0 | 0.376 mean | SD 0.080, range 0.213 |

*Source: `phase_robustness`. Paraphrase ICC = agreement with the designed synthetic gold (NOT faculty);
test–retest ICC measures internal stochasticity, not validity.*

### Reliability of the scoring machinery

Across every computed phase the strict-JSON scorer achieved a **100% parse-success rate and a 0%
refusal rate** (`phase_quant_frontier`, `phase_model_frontier`, `phase_local_vs_cloud`); the
fail-loud client never silently fell back. This is a reliability-of-machinery property, not a
validity claim.

## Apparatus status (not a study result)

The firmware build is verified green for the exact ESP32-S3 board: ESP-IDF v5.5.2, target confirmed
from the binary chip id, the `aivmt_sp` component compiles and links, the 2,648,944-byte application
image fits with 36% slot free, and the 16 MB flash layout matches the physical device
(`firmware/G0_BUILD_REPORT.md`). The device is **not flashed for a study** and the SP hooks are **not
wired** (`SpSession` dormant), so as built it behaves like the stock upstream voice assistant and
cannot run an encounter; the embodiment study (SQ2) is therefore `[SQ2 embodiment result: pending —
device not flashed]`.

## An earlier English synthetic pilot (superseded; reported for transparency)

A 2026-06-10 pilot scored 30 **English** synthetic encounters with an earlier scorer build, yielding
much higher ICCs against the designed gold (`results/phase_scoring_validity/frontier_v1_synthetic.md`:
llama3.1:8b 0.915, qwen2.5:3b 0.737, qwen2.5:7b 0.678, qwen2.5:14b 0.905, gpt-oss:20b 0.888; all
parse 100%). (Governance note: `HYPOTHESIS.md` Amendment A1 (line 57) quotes the gpt-oss:20b pilot ICC
as 0.904, but the artifact `frontier_v1_synthetic.md` records **0.888**; the artifact value is
authoritative and is the one cited here.) These are **not comparable** to the 2026-06-13 zh runs above
— different scorers and transcript language — and the authors' own notes label this an "optimistic floor — NOT the validity
claim" and warn against reading a clean size law from n = 30 (CI ~±0.1). We present the **newer zh
run as the current-scorer result** and report the English pilot only to document provenance.

## Outstanding pending quantities

Beyond the primary faculty ICC, the following are pre-specified but not yet computed and must remain
placeholders until real data exist: `[per-subscore faculty ICC]`, `[faculty inter-rater ICC ceiling]`,
`[bootstrap 95% CI on faculty ICC]`, `[weighted kappa vs faculty]`, `[Bland-Altman vs faculty]`,
`[G-theory + D-study vs faculty]`, `[decision consistency at cut 0.6 vs faculty]`,
`[faculty-anchored non-inferiority vs cloud]`, `[fairness/subgroup analysis by specialty, difficulty,
and zh-vs-en]`, `[real collection-day zh transcripts]`, `[final frozen sample size n]`, `[few-shot
ablation as an end-to-end harness arm]`, `[pinned per-model quant digests]`, `[full
compute/energy/cost accounting for SQ3]`, and `[SQ3 total-cost vs cloud and human-SP baselines]`.
