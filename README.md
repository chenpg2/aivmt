# AIVMT — AI Virtual Medical Teacher

Embodied, ultra–low-cost voice **standardized patient** running on a single self-hosted
**open-weight LLM** behind a sub-$20 ESP32-S3 device, with **automated competency feedback**
validated against faculty. Research vehicle for an npj Digital Medicine submission
(*Transforming Medical Education through Artificial Intelligence*).

See planning docs in `../plan/` (protocol, pre-registration, build & firmware specs).

## Packages
- `aivmt.schemas` — typed, immutable data schemas (Case / Transcript / Score / Feedback).
- `aivmt.llm` — OpenAI-compatible LLM clients via factory/registry (`mock`, `openai_compat`).
- `aivmt.scoring` — competency scorers via factory/registry: history-taking `checklist`,
  `segue` communication, out-loud `reasoning`.
- `aivmt.pipeline` — orchestrates scorers → `CompetencyScore` + `Feedback` (the H1-validated output).
- `aivmt.cases` — load a `Case` from a Hydra/OmegaConf YAML.

Bilingual: every scorer prompt switches on `Case.language` (`en` primary, `zh` supported).

## Quickstart
```bash
uv sync --extra dev            # create env
uv run --extra dev pytest      # run the mock-LLM unit test (no model needed)
# real scoring against a local model:
uv run --extra serve python -m aivmt.run_score llm.base_url=http://localhost:8000/v1
```

## Status
W2 scaffold: scoring pipeline + mock test. TODO: server (xiaozhi-esp32-server), firmware fork
(`firmware/`), model-selection benchmark, data-capture/export.
