# Local offline TTS provider (Piper)

`tts_piper.py` is a drop-in text-to-speech provider for the self-hosted
`xiaozhi-esp32-server` that synthesizes the AI patient's voice **entirely on the
host** via [Piper](https://github.com/rhasspy/piper). It makes **no network
calls**, which is what lets the AIVMT loop run fully offline (no learner speech or
transcript ever leaves the host). It replaces the previous cloud TTS (EdgeTTS),
which was the one component that reached an external service.

## Install

1. Place the provider:
   ```
   cp tts_piper.py <server>/core/providers/tts/piper.py
   ```
2. Install piper and a voice (one-time; not a runtime egress):
   ```
   uv pip install piper-tts          # or: pip install piper-tts
   python -m piper.download_voices zh_CN-huayan-medium --download-dir <server>/models/piper
   ```
3. Register the provider in `config.yaml` under `TTS:`:
   ```yaml
   PiperTTS:
     type: piper
     piper_bin: piper            # defaults to `sys.executable -m piper` if left as "piper"
     model: models/piper/zh_CN-huayan-medium.onnx
     model_config: ""
     speaker: ""
     length_scale: ""
     output_dir: tmp/
   ```
4. Select it (e.g. in `data/.config.yaml`):
   ```yaml
   selected_module:
     TTS: PiperTTS
   ```

## Notes

- The provider defaults `piper_bin` to the running interpreter (`sys.executable -m
  piper`), so it works whether or not the server is launched with the venv
  activated — no PATH dependency.
- Piper emits 22 kHz WAV; the server's audio pipeline resamples and Opus-encodes
  for the device, so no firmware change is needed.
- With this provider active, the full loop is local: FunASR (ASR) → Ollama
  (patient LLM) → Piper (TTS). Verified end-to-end on the ESP32 device with a
  zero-external-egress check.
