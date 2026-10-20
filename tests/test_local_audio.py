from __future__ import annotations

import io
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import av
import numpy as np
import pytest

from skye.audio import AudioService
from skye.config import Settings
from skye.local_audio import LocalAudio


def settings(**overrides: object) -> Settings:
    return Settings.model_construct(**overrides)


def wav_bytes() -> bytes:
    output = io.BytesIO()
    with av.open(output, mode="w", format="wav") as container:
        stream = container.add_stream("pcm_s16le", rate=24_000)
        stream.layout = "mono"
        frame = av.AudioFrame(format="s16", layout="mono", samples=2_400)
        frame.sample_rate = 24_000
        frame.planes[0].update(b"\x00\x10" * 2_400)
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return output.getvalue()


def test_local_audio_does_not_fall_back_to_fal() -> None:
    config = settings(skye_audio_provider="local", skye_fal_key="fal-key")

    assert config.audio_on_local is True
    assert config.audio_on_fal is False


def test_from_settings_selects_the_local_models() -> None:
    local = cast(Any, SimpleNamespace())
    service = AudioService.from_settings(
        settings(
            skye_local_transcription_model="large-v3-turbo",
            skye_local_speech_voice="F1",
        ),
        local=local,
    )

    assert service.local is local
    assert service.transcription_model == "large-v3-turbo"
    assert service.speech_model == "supertonic-3"
    assert service.speech_voice == "F1"


def test_audio_service_rejects_more_than_one_backend() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        AudioService(
            transcription_model="m",
            speech_model="m",
            speech_voice="v",
            fal=cast(Any, SimpleNamespace()),
            local=cast(Any, SimpleNamespace()),
        )


async def test_local_transcribe_delegates_to_the_engine() -> None:
    local = SimpleNamespace(transcribe=AsyncMock(return_value="Hello there."))
    service = AudioService(
        transcription_model="large-v3-turbo",
        speech_model="supertonic-3",
        speech_voice="F1",
        local=cast(Any, local),
    )

    assert await service.transcribe("voice.ogg", b"audio", "audio/ogg") == "Hello there."
    local.transcribe.assert_awaited_once_with("voice.ogg", b"audio", "audio/ogg")


async def test_local_speak_transcodes_supertonic_wav_to_mp3() -> None:
    local = SimpleNamespace(speak_wav=AsyncMock(return_value=wav_bytes()))
    service = AudioService(
        transcription_model="large-v3-turbo",
        speech_model="supertonic-3",
        speech_voice="F1",
        local=cast(Any, local),
    )

    result = await service.speak("Hello.", "Warm and calm.")

    assert result.startswith(b"ID3")
    local.speak_wav.assert_awaited_once_with("Hello.", "Warm and calm.")


async def test_local_engine_joins_whisper_segments() -> None:
    engine = LocalAudio(settings(skye_local_cpu_threads=2))
    captured: dict[str, Any] = {}

    class FakeWhisper:
        def transcribe(self, audio: Any, **kwargs: Any) -> tuple[list[Any], Any]:
            captured.update(kwargs)
            captured["audio"] = audio
            segments = [
                SimpleNamespace(text=" Hello"),
                SimpleNamespace(text=" world. "),
            ]
            info = SimpleNamespace(language="en", language_probability=0.99)
            return segments, info

    engine._whisper = cast(Any, FakeWhisper())

    assert await engine.transcribe("voice.ogg", b"ogg-data") == "Hello world."
    assert captured["vad_filter"] is True
    assert captured["beam_size"] == 1
    assert isinstance(captured["audio"], io.BytesIO)


async def test_local_engine_synthesizes_a_wav_with_the_configured_voice() -> None:
    engine = LocalAudio(
        settings(skye_local_speech_voice="F1", skye_local_speech_lang="na")
    )
    captured: dict[str, Any] = {}

    class FakeTTS:
        sample_rate = 44_100
        model = SimpleNamespace(
            text_processor=SimpleNamespace(validate_text=lambda text: (True, []))
        )

        def synthesize(self, text: str, **kwargs: Any) -> tuple[np.ndarray, np.ndarray]:
            captured.update({"text": text, **kwargs})
            return np.zeros((1, 4_410), dtype=np.float32), np.array([0.1])

    style = object()
    engine._tts = cast(Any, FakeTTS())
    engine._style = style

    audio = await engine.speak_wav("Hello there.", "Warm.")

    assert audio.startswith(b"RIFF")
    assert b"WAVE" in audio[:16]
    assert captured["text"] == "Hello there."
    assert captured["voice_style"] is style
    assert captured["lang"] == "na"
    assert captured["speed"] == 1.0


def test_local_engine_drops_glyphs_the_voice_cannot_pronounce() -> None:
    engine = LocalAudio(settings())
    engine._tts = cast(
        Any,
        SimpleNamespace(
            model=SimpleNamespace(
                text_processor=SimpleNamespace(
                    validate_text=lambda text: (False, ["✦", "🙂"])
                )
            )
        ),
    )

    assert engine._speakable("Hi ✦ there 🙂 friend") == "Hi there friend"


def test_local_engine_rejects_text_without_speakable_characters() -> None:
    engine = LocalAudio(settings())
    engine._tts = cast(
        Any,
        SimpleNamespace(
            model=SimpleNamespace(
                text_processor=SimpleNamespace(validate_text=lambda text: (False, ["✦"]))
            )
        ),
    )

    with pytest.raises(ValueError, match="no characters"):
        engine._speakable("✦")
