# Quantization frontier (auto-generated — do not edit by hand)

Validity-cost surface over (model size x quant level): ICC-vs-gold against the designed synthetic gold, JSON-parse robustness, per-encounter latency, loaded RAM/VRAM, and on-disk size. `degenerate` flags a cell whose scorer produced no between-encounter variance (ICC is an explicit nan, never a silent number).

| model_tag | label | n_tx | icc2_1 | icc2_k | parse | refusal | median_s | p90_s | tok/s | mem | disk | degenerate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen2.5:7b-instruct-fp16 | FP16 | 30 | 0.410 | 0.581 | 1.000 | 0.000 | 9.020 | 13.092 | n/a | 16 GB | 15 GB | False |
| qwen2.5:7b-instruct-q8_0 | Q8_0 | 30 | 0.410 | 0.581 | 1.000 | 0.000 | 6.363 | 8.324 | n/a | 9.7 GB | 8.1 GB | False |
| qwen2.5:7b | Q4_K_M | 30 | 0.351 | 0.520 | 1.000 | 0.000 | 5.696 | 7.016 | n/a | 6.6 GB | 4.7 GB | False |
| qwen2.5:7b-instruct-q3_K_M | Q3_K_M | 30 | 0.343 | 0.511 | 1.000 | 0.000 | 6.243 | 6.746 | n/a | 5.8 GB | 3.8 GB | False |
