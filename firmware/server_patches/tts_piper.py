import os
import sys
import uuid
import asyncio
from datetime import datetime

from config.logger import setup_logging
from core.providers.tts.base import TTSProviderBase

TAG = __name__
logger = setup_logging()


class TTSProvider(TTSProviderBase):
    """Fully-local, offline neural TTS via Piper (https://github.com/rhasspy/piper).

    Piper synthesizes speech from a local ONNX voice model and makes **no network
    calls**, which is what lets the AIVMT loop run fully offline (no data leaves the
    host). It is chosen for low-resource deployment: small models, CPU-only, fast.

    Config (TTS.PiperTTS in config.yaml):
        type: piper
        piper_bin: piper                 # path to the piper executable (or "python -m piper")
        model: models/piper/zh_CN-huayan-medium.onnx   # local .onnx voice
        model_config: ""                 # optional .onnx.json (piper finds it next to the model by default)
        speaker: ""                      # optional speaker id for multi-speaker voices
        length_scale: ""                 # optional speed control (>1 slower, <1 faster)
        output_dir: tmp/
    """

    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        # Resolve how to invoke piper. A bare "piper" relies on PATH, which is not
        # guaranteed when the server is launched without the venv activated; default
        # instead to the *same* interpreter that runs the server (the venv python,
        # which has piper-tts installed) via "-m piper". A configured path/command
        # (containing a slash or extra args) is honoured verbatim.
        raw_bin = str(config.get("piper_bin", "") or "").strip()
        if not raw_bin or raw_bin == "piper":
            self.piper_bin = [sys.executable, "-m", "piper"]
        else:
            self.piper_bin = raw_bin.split()
        self.model = config.get("model")
        self.model_config = config.get("model_config") or None
        self.speaker = config.get("speaker")
        self.length_scale = config.get("length_scale")
        self.audio_file_type = "wav"  # piper emits WAV
        if not self.model or not os.path.exists(self.model):
            logger.bind(tag=TAG).warning(
                f"Piper voice model not found at '{self.model}'. Download one "
                f"(e.g. zh_CN-huayan-medium from rhasspy/piper-voices) and set "
                f"TTS.PiperTTS.model to its .onnx path."
            )

    def generate_filename(self, extension=".wav"):
        return os.path.join(
            self.output_file,
            f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}",
        )

    def _build_cmd(self, target_file):
        cmd = list(self.piper_bin) + ["--model", self.model, "--output_file", target_file]
        if self.model_config:
            cmd += ["--config", self.model_config]
        if self.speaker is not None and str(self.speaker) != "":
            cmd += ["--speaker", str(self.speaker)]
        if self.length_scale is not None and str(self.length_scale) != "":
            cmd += ["--length_scale", str(self.length_scale)]
        return cmd

    async def text_to_speak(self, text, output_file):
        # When output_file is None (delete_audio mode) synthesize to a temp file,
        # read the bytes back and clean up; otherwise write directly to output_file.
        target = output_file or self.generate_filename()
        os.makedirs(os.path.dirname(target), exist_ok=True)
        cmd = self._build_cmd(target)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate(input=text.encode("utf-8"))
            if proc.returncode != 0:
                raise Exception(
                    f"piper exited {proc.returncode}: "
                    f"{stderr.decode('utf-8', 'ignore')[:300]}"
                )
            if output_file:
                return None  # base reads the file
            with open(target, "rb") as f:
                audio_bytes = f.read()
            if os.path.exists(target):
                os.remove(target)
            return audio_bytes
        except FileNotFoundError:
            raise Exception(
                f"piper binary {self.piper_bin!r} not found. Install piper "
                f"(pip install piper-tts, or download a release binary) and set "
                f"TTS.PiperTTS.piper_bin."
            )
        except Exception as e:
            raise Exception(f"Piper TTS failed: {e}")
