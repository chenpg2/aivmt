# Local-vs-cloud scoring head-to-head (auto-generated — do not edit by hand)

Provenance: **synthetic** (off-device-safe synthetic/de-identified — NO real data was transmitted to any cloud endpoint). Seed: 42. n=30. Variant: zero_shot. Pre-registered non-inferiority margin delta = 0.10.

## ICC(2,1) vs designed-quality gold (overall + per SEGUE domain)

| role | provider | model | n | overall | set_the_stage | elicit_information | give_information | understand_perspective | end_encounter | parse | refusal |
|---|---|---|---|---|---|---|---|---|---|---|---|
| local | llama3.1:8b | llama3.1:8b | 30 | 0.424 | 0.483 | 0.636 | 0.114 | nan | nan | 1.000 | 0.000 |
| cloud | deepseek-v4-pro | deepseek-v4-pro | 30 | 0.561 | 0.484 | 0.706 | 0.323 | nan | 0.143 | 1.000 | 0.000 |
| cloud | claude-opus-4-7 | claude-opus-4-7 | 30 | 0.698 | 0.291 | 0.664 | 0.526 | nan | nan | 1.000 | 0.000 |

## Local-minus-cloud ICC delta (positive => local agrees with gold MORE than cloud)

Pre-registered non-inferiority claim: the local model is non-inferior to a cloud comparator on the overall axis iff `delta_overall >= -0.10` (the local ICC is at most the margin below the cloud ICC). Per-domain deltas are reported because cloud models are known to collapse on communication subdomains (ECOSBot).

| cloud provider | delta_overall | non-inferior? | set_the_stage | elicit_information | give_information | understand_perspective | end_encounter |
|---|---|---|---|---|---|---|---|
| deepseek-v4-pro | -0.137 | NO | -0.001 | -0.070 | -0.209 | nan | nan |
| claude-opus-4-7 | -0.274 | NO | 0.192 | -0.028 | -0.413 | nan | nan |
