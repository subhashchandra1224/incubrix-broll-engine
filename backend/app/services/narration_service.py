"""Build narration from the job request.

- audio_url  -> STT (transcript + word timings)
- script     -> TTS (duration + word timings; transcript is the script itself)
- scenes     -> TTS each scene's text, laid out sequentially (timings + transcript)

All timings are TEST DATA from mock adapters until real adapters are wired.
"""
from __future__ import annotations

import logging

from app.api.errors import InvalidInputError
from app.providers.factory import get_stt_provider, get_tts_provider
from app.schemas.providers import Transcript, WordTiming

log = logging.getLogger(__name__)


def build_narration(request: dict) -> tuple[Transcript, float, str]:
    """Return (transcript, duration_seconds, input_type)."""
    if request.get("script"):
        return _from_script(request)
    if request.get("audio_url"):
        return _from_audio(request)
    if request.get("scenes"):
        return _from_scenes(request)
    raise InvalidInputError("No narration input provided.")


def _from_script(request: dict) -> tuple[Transcript, float, str]:
    tts = get_tts_provider()
    text = request["script"]
    synth = tts.synthesize(text, request.get("voice"))
    return (
        Transcript(text=text, words=synth.words, duration=synth.duration,
                   provider=tts.name, test_data=synth.test_data),
        synth.duration,
        "script",
    )


def _from_audio(request: dict) -> tuple[Transcript, float, str]:
    stt = get_stt_provider()
    transcript = stt.transcribe(request["audio_url"], language=request.get("language"))
    return transcript, transcript.duration, "audio"


def _from_scenes(request: dict) -> tuple[Transcript, float, str]:
    tts = get_tts_provider()
    texts = [s["text"] for s in request["scenes"]]
    full_text = " ".join(texts)
    words: list[WordTiming] = []
    offset = 0.0
    for s_text in texts:
        synth = tts.synthesize(s_text, request.get("voice"))
        for w in synth.words:
            words.append(WordTiming(text=w.text, start=round(w.start + offset, 3),
                                    end=round(w.end + offset, 3), test_data=w.test_data))
        offset += synth.duration
    return (
        Transcript(text=full_text, words=words, duration=round(offset, 3),
                   provider=tts.name, test_data=True),
        round(offset, 3),
        "scenes",
    )
