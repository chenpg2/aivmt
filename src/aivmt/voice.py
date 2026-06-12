"""Local bilingual voice I/O for the collection front-end (English primary, Chinese supported).

ASR: faster-whisper (fully local; language follows Case.language).
TTS: macOS built-in `say` (en: Samantha, zh: Tingting) — zero-install, local.
Mic: sounddevice push-to-talk (Enter to start, Enter to stop).
"""

from __future__ import annotations

import subprocess
from typing import Optional

import numpy as np

from .schemas import Language
from .utils import get_logger

logger = get_logger(__name__)

SAMPLE_RATE = 16_000
_TTS_VOICE: dict[str, str] = {"en": "Samantha", "zh": "Tingting"}


def speak(text: str, language: Language, rate_wpm: int = 190) -> None:
    """Speak text aloud via macOS `say` (blocking, local)."""
    voice = _TTS_VOICE.get(language, "Samantha")
    try:
        subprocess.run(["say", "-v", voice, "-r", str(rate_wpm), text], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Voice pack missing or non-macOS: fall back to default voice, then to silence.
        try:
            subprocess.run(["say", text], check=True)
        except Exception:  # noqa: BLE001
            logger.warning("TTS unavailable; printed only")


def record_push_to_talk(prompt: str = "🎙  按回车开始说话 / Enter to talk") -> Optional[np.ndarray]:
    """Record one utterance: Enter starts, Enter stops. Returns float32 mono @16k, or None."""
    import sounddevice as sd  # noqa: PLC0415 - optional dep

    input(f"{prompt} … ")
    chunks: list[np.ndarray] = []

    def _cb(indata, frames, time_info, status) -> None:  # noqa: ANN001
        chunks.append(indata.copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=_cb):
        input("🔴 录音中…说完按回车 / recording… Enter to stop ")
    if not chunks:
        return None
    audio = np.concatenate(chunks).flatten()
    return audio if audio.size >= SAMPLE_RATE // 4 else None  # <0.25s = discard


class Transcriber:
    """Lazy faster-whisper wrapper; transcribes float32@16k or an audio file path."""

    def __init__(self, model_size: str = "small", device: str = "auto") -> None:
        self._model_size = model_size
        self._device = device
        self._model = None

    def _ensure(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # noqa: PLC0415 - optional dep

            logger.info("loading whisper '%s' (first run downloads the model)", self._model_size)
            self._model = WhisperModel(self._model_size, device=self._device, compute_type="int8")
        return self._model

    def transcribe(self, audio, language: Language) -> str:
        """Return the transcribed text (single utterance)."""
        model = self._ensure()
        segments, _info = model.transcribe(audio, language=language, beam_size=5, vad_filter=True)
        return "".join(s.text for s in segments).strip()
