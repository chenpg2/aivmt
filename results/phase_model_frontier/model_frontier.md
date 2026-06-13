# Quantization frontier (auto-generated — do not edit by hand)

Validity-cost surface over (model size x quant level): ICC-vs-gold against the designed synthetic gold, JSON-parse robustness, per-encounter latency, loaded RAM/VRAM, and on-disk size. `degenerate` flags a cell whose scorer produced no between-encounter variance (ICC is an explicit nan, never a silent number).

| model_tag | label | n_tx | icc2_1 | icc2_k | parse | refusal | median_s | p90_s | tok/s | mem | disk | degenerate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen2.5:3b | 3B-Qwen | 30 | 0.248 | 0.398 | 1.000 | 0.000 | 2.178 | 2.886 | n/a | 3.4 GB | 1.9 GB | False |
| qwen2.5:7b | 7B-Qwen | 30 | 0.351 | 0.520 | 1.000 | 0.000 | 5.629 | 8.902 | n/a | 6.6 GB | 4.7 GB | False |
| llama3.1:8b | 8B-Llama | 30 | 0.424 | 0.596 | 1.000 | 0.000 | 7.223 | 9.810 | n/a | 22 GB | 4.9 GB | False |
| huatuogpt-o1:8b | 8B-Huatuo-Med | 30 | 0.554 | 0.713 | 1.000 | 0.000 | 9.284 | 11.437 | n/a | 23 GB | 4.9 GB | False |
| qwen2.5:14b | 14B-Qwen | 30 | 0.624 | 0.769 | 1.000 | 0.000 | 11.687 | 16.345 | n/a | 15 GB | 9.0 GB | False |
