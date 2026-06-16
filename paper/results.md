# Results

> Drafted 2026-06-13; primary faculty result filled 2026-06-16. Every number below is copied from a
> registered harness phase artifact under `results/` and carries an inline source pointer. No number
> is invented. The **primary endpoint (agreement with 3 blinded faculty) is now computed** (SQ1
> below). Every absolute ICC drawn from a *synthetic-gold* run is still labelled *agreement with the
> designed synthetic gold*, which is **not** a faculty-validity number — only SQ1 is faculty-anchored.

## SQ1 (primary) — agreement with blinded faculty consensus

The primary endpoint is the absolute-agreement ICC(2,1) between the local-model automated score and
the consensus of k = 3 blinded faculty raters on Chinese OB/GYN history-taking encounters
(`HYPOTHESIS.md`, pre-registered threshold ICC(2,1) ≥ 0.75). On the frozen 33-encounter evaluation
set scored by three blinded OB/GYN faculty (system = llama3.1:8b), the **primary endpoint is met**
(`phase_scoring_validity`, `results/evidence_table.md` reports `status=REAL_DATA`; raw ratings in the
gitignored `data/faculty_ratings.csv`, n = 33, k = 3, 0% missing cells).

```
PRIMARY RESULT (phase_scoring_validity, status=REAL_DATA; n=33 encounters x k=3 blinded faculty)
  Overall ICC(2,1) = 0.903   95% CI [0.737, 0.958]  (McGraw & Wong F-based)
          ICC(2,k) = 0.949   95% CI [0.849, 0.979]
          seeded bootstrap ICC(2,1) 95% CI [0.846, 0.935]  (independent cross-check)
  Faculty inter-rater ceiling: ICC(2,1) = 0.765 [0.533, 0.884]; ICC(2,k) = 0.907 [0.774, 0.958]
  Pairwise system-vs-each-rater ICC(2,1): fac01 0.741, fac02 0.840, fac03 0.916
  PRIMARY ENDPOINT MET (ICC(2,1) >= 0.75)?  YES (point 0.903; CI lower bound 0.737)
```

**Headline.** The single local open-weight model agrees with the three-faculty consensus at
ICC(2,1) = 0.903 — *at or above* the level at which the faculty agree with one another (inter-rater
ceiling ICC(2,1) = 0.765). The automated scorer is, on the overall score, as reliable a rater as a
human expert on this set.

**Per-subscore agreement (system vs faculty consensus, ICC(2,1) with 95% CI):**

| dimension | ICC(2,1) | 95% CI | ICC(2,k) | weighted κ (quadratic) |
|---|---|---|---|---|
| **overall** | **0.903** | [0.737, 0.958] | 0.949 | — |
| set_the_stage | 0.343 | [−0.089, 0.704] | 0.510 | 0.244 |
| elicit_information | 0.165 | [−0.091, 0.461] | 0.283 | 0.073 |
| give_information | 0.667 | [−0.081, 0.897] | 0.801 | 0.485 |
| understand_perspective | 0.702 | [0.240, 0.873] | 0.825 | 0.761 |
| end_encounter | 0.889 | [0.573, 0.959] | 0.941 | 0.741 |
| history_completion | 0.931 | [0.826, 0.969] | 0.964 | — |
| reasoning | −0.016 | [−0.103, 0.124] | −0.033 | 0.022 |

**The agreement is domain-structured, and honestly so.** The model tracks faculty closely on the
countable, content-coverage domains (history_completion 0.931, end_encounter 0.889,
understand_perspective 0.702, give_information 0.667) but **collapses on the qualitative
communication and reasoning subdomains** (set_the_stage 0.343, elicit_information 0.165, reasoning
−0.016). In plain terms: the scorer reliably judges *what* the student covered, but not yet *how
well* they communicated or reasoned — the same communication-subdomain weakness reported for cloud
GPT-4o in ECOSBot. The strong overall ICC is carried by the coverage domains.

**Supporting agreement statistics (overall, vs faculty consensus):**
- Bland–Altman: bias = −0.054 (system scores marginally below faculty), 95% limits of agreement
  [−0.228, 0.120], proportional-bias slope = −0.334 (p < 0.001) — the system is relatively
  *harsher* on high-scoring encounters.
- G-theory (person × rater): variance components person 0.066 / rater 0.007 / residual 0.013;
  G = 0.936, Φ = 0.907 — rater variance is small, i.e. the rubric generalizes well across raters.
- Decision consistency at the 0.6 pass/fail cut: raw agreement 0.758, Cohen's κ = 0.000 — degenerate
  at this cut on this set (almost all 33 encounters fall on the same side of 0.6 for both system and
  faculty), so κ is uninformative here; the continuous ICC, not the dichotomized cut, is the endpoint.

**Caveats (load-bearing — these scope the claim).** (1) The transcripts are **synthetic**, grounded
in the collaborator-reviewed OB/GYN cases; the faculty ratings are real. This validates **the scorer**
(does the model agree with faculty on the same encounters?), not full ecological/prospective validity
on live student encounters. (2) **n = 33** — the CI is real but not narrow; a scale-up (pre-registered
floor n = 100) would tighten it. (3) One fac02 entry was recorded as `03` on the 0–1 scale and
interpreted as 0.3. (4) The reasoning subdomain ICC ≈ 0 is a genuine scorer limitation, reported, not
smoothed over.

A harness negative-control cross-check confirms the validity machinery behaves correctly: shuffling
the encounter–rating pairing collapses the overall ICC toward zero (`phase_scoring_validity` sanity).

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

The embodied device is **flashed and the full device↔server↔local-model loop is demonstrated
end-to-end on the physical ESP32-S3** (ESP-IDF v5.5.2; ~2.67 MB image, ~35% slot free). A complete
standardized-patient encounter was run on hardware: the student speaks (BOOT-button conversation,
WebRTC-VAD turn segmentation), the self-hosted server transcribes with local FunASR, a local
open-weight LLM (Ollama) answers **in the patient's persona and grounded in the case**, the reply is
voiced back, the live transcript is accumulated on the device, and a BOOT long-press exports the
encounter via `POST /aivmt/encounter`, which the server archives locally as scoreable JSON
(`firmware/demo_encounter_device.json`: a 12-turn zh OB/GYN ectopic-pregnancy history-take —
6-week amenorrhea, unprotected intercourse, vaginal bleeding, RLQ pain, dizziness — `HTTP 200`,
`participant_code=device01`). The host state-machine test and the server endpoint unit tests pass.
**Honest gaps remaining (refinements, not blockers):** TTS is currently cloud EdgeTTS — a local TTS
is needed for a *fully* offline LMIC deployment (ASR and LLM are already local); the SP phase-machine
telemetry (encounter duration, per-phase timing) is not yet captured in this button-minimal flow; the
OLED persona panel and a formal real-speech WER measurement are not yet run; and ASR shows the
expected zh homophone slips (e.g. 末次→末世) that the ASR-robustness lane quantifies. The embodiment
study (SQ2) is therefore `[SQ2 embodiment result: device operational + loop demonstrated; controlled
device-vs-screen study pending]`.

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

The SQ1 primary faculty ICC and its supporting statistics (per-subscore ICC, inter-rater ceiling,
bootstrap CI, weighted kappa, Bland–Altman, G-theory, decision consistency) are now **computed**
(see SQ1 above). The following remain pre-specified but not yet computed, and stay placeholders until
the corresponding data exist: `[faculty-anchored non-inferiority vs cloud]` (re-run the local-vs-cloud
head-to-head against faculty consensus rather than synthetic gold), `[fairness/subgroup analysis by
specialty and difficulty]`, `[prospective live-student zh transcripts]` (current SQ1 is on synthetic
transcripts), `[scale-up to the pre-registered floor n = 100]`, `[few-shot ablation as an end-to-end
harness arm]`, `[pinned per-model quant digests]`, `[SQ2 embodiment — device not flashed]`, and
`[SQ3 total-cost vs cloud and human-SP baselines]`.
