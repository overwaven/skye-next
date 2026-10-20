"""Speech in and out on the machine itself.

Transcription is Whisper large-v3-turbo through faster-whisper, the
CTranslate2 build of ``openai/whisper-large-v3-turbo``. Speech is Supertonic 3
on ONNX Runtime. Both run on the CPU: nothing leaves the host for a voice note.
The heavy runtimes are imported only when a model is first used, and the model
files are downloaded once into ``SKYE_MODELS_DIR`` and reused across restarts.

Inference runs in a worker thread and is serialized through one lock, so a
small host never has Whisper and Supertonic competing for the same cores.
"""

from __future__ import annotations

import asyncio
import io
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from .config import Settings

if TYPE_CHECKING:
    from faster_whisper import WhisperModel  # type: ignore[import-untyped]
    from supertonic import TTS  # type: ignore[import-untyped]

log = structlog.get_logger()


class LocalAudio:
    """On-device speech services used when ``SKYE_AUDIO_PROVIDER=local``.

    ``transcribe`` returns text; ``speak_wav`` returns a 44.1 kHz WAV that the
    caller transcodes to a Telegram voice note. The TTS delivery instructions
    are accepted for interface parity with the hosted backends but ignored:
    Supertonic has no style prompt, only fixed voices and speed.
    """

    def __init__(self, config: Settings) -> None:
        self.models_dir = Path(config.skye_models_dir)
        self.transcription_model = config.skye_local_transcription_model
        self.voice = config.skye_local_speech_voice
        self.lang = config.skye_local_speech_lang
        self.steps = config.skye_local_speech_steps
        self.speed = config.skye_local_speech_speed
        self.cpu_threads = config.skye_local_cpu_threads
        self._run = asyncio.Lock()
        self._whisper: WhisperModel | None = None
        self._tts: TTS | None = None
        self._style: Any = None

    async def transcribe(self, filename: str, data: bytes, mime: str = "") -> str:
        async with self._run:
            if self._whisper is None:
                self._whisper = await asyncio.to_thread(self._load_whisper)
            return await asyncio.to_thread(self._transcribe, data)

    async def speak_wav(self, text: str, instructions: str = "") -> bytes:
        async with self._run:
            if self._tts is None:
                self._tts, self._style = await asyncio.to_thread(self._load_tts)
            return await asyncio.to_thread(self._synthesize, text)

    def _load_whisper(self) -> WhisperModel:
        from faster_whisper import WhisperModel

        started = time.monotonic()
        self.models_dir.mkdir(parents=True, exist_ok=True)
        model = WhisperModel(
            self.transcription_model,
            device="cpu",
            compute_type="int8",
            cpu_threads=self.cpu_threads,
            num_workers=1,
            download_root=str(self.models_dir / "whisper"),
        )
        log.info(
            "local_speech_model_loaded",
            kind="transcription",
            model=self.transcription_model,
            duration_ms=_elapsed(started),
        )
        return model

    def _load_tts(self) -> tuple[TTS, Any]:
        from supertonic import TTS

        started = time.monotonic()
        self.models_dir.mkdir(parents=True, exist_ok=True)
        tts = TTS(
            model="supertonic-3",
            model_dir=self.models_dir / "supertonic-3",
            auto_download=True,
            intra_op_num_threads=self.cpu_threads,
            inter_op_num_threads=1,
        )
        style = tts.get_voice_style(voice_name=self.voice)
        log.info(
            "local_speech_model_loaded",
            kind="speech",
            model="supertonic-3",
            voice=self.voice,
            duration_ms=_elapsed(started),
        )
        return tts, style

    def _transcribe(self, data: bytes) -> str:
        assert self._whisper is not None
        started = time.monotonic()
        segments, info = self._whisper.transcribe(
            io.BytesIO(data),
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
            without_timestamps=True,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        log.info(
            "local_transcription",
            duration_ms=_elapsed(started),
            chars=len(text),
            language=info.language,
            language_probability=round(info.language_probability, 3),
        )
        return text

    def _synthesize(self, text: str) -> bytes:
        import soundfile as sf  # type: ignore[import-untyped]

        assert self._tts is not None
        started = time.monotonic()
        speakable = self._speakable(text)
        wav, _ = self._tts.synthesize(
            speakable,
            voice_style=self._style,
            total_steps=self.steps,
            speed=self.speed,
            lang=self.lang,
        )
        buffer = io.BytesIO()
        sf.write(buffer, wav.squeeze(), self._tts.sample_rate, format="WAV")
        log.info(
            "local_speech",
            duration_ms=_elapsed(started),
            chars=len(speakable),
            audio_ms=int(wav.shape[1] * 1000 / self._tts.sample_rate),
            voice=self.voice,
        )
        return buffer.getvalue()

    def _speakable(self, text: str) -> str:
        """Drop glyphs the text processor cannot pronounce, such as emoji."""
        assert self._tts is not None
        cleaned = re.sub(r"\s+", " ", text).strip()
        if not cleaned:
            raise ValueError("There is no text to speak.")
        _, unsupported = self._tts.model.text_processor.validate_text(cleaned)
        for char in unsupported:
            cleaned = cleaned.replace(char, " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            raise ValueError("The text has no characters the local voice can pronounce.")
        return cleaned


def _elapsed(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
