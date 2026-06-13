# Scorer robustness (auto-generated — do not edit by hand)

## Paraphrase sensitivity (ICC-vs-gold across system-prompt rewordings)

| model | variant | n_para | n_tx | icc_mean | icc_sd | icc_range |
|---|---|---|---|---|---|---|
| llama3.1:8b | zero_shot | 6 | 30 | 0.463 | 0.060 | 0.157 |
| llama3.1:8b | few_shot | 6 | 30 | 0.376 | 0.080 | 0.213 |

## Test-retest reliability (stochasticity across repeated scorings)

| model | variant | temp | K | n_tx | retest_icc | mean_cv | degenerate |
|---|---|---|---|---|---|---|---|
| llama3.1:8b | zero_shot | 0.0 | 3 | 30 | 1.000 | 0.000 | False |
| llama3.1:8b | zero_shot | 0.3 | 3 | 30 | 0.965 | 0.170 | False |
| llama3.1:8b | few_shot | 0.0 | 3 | 30 | 1.000 | 0.000 | False |
| llama3.1:8b | few_shot | 0.3 | 3 | 30 | 0.921 | 0.240 | False |
