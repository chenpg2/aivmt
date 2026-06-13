# ASR-robustness ICC-degradation curve (auto-generated — do not edit by hand)

Metric: Character Error Rate (CER) — the standard zh ASR severity metric. `target_wer` is the requested level; `achieved_cer` is what the deterministic corruption actually reached.

| model | variant | target_wer | achieved_cer | icc_vs_gold | n_tx | degenerate |
|---|---|---|---|---|---|---|
| llama3.1:8b | zero_shot | 0.00 | 0.000 | 0.396 | 30 | False |
| llama3.1:8b | zero_shot | 0.05 | 0.048 | 0.398 | 30 | False |
| llama3.1:8b | zero_shot | 0.15 | 0.185 | 0.295 | 30 | False |
| llama3.1:8b | zero_shot | 0.30 | 0.342 | 0.250 | 30 | False |
