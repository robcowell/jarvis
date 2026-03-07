import os
from io import BytesIO

from openai import OpenAI


_client = OpenAI()
_CHAT_MODEL = os.getenv("JARVIS_COMMAND_MODEL", "gpt-5")
_TRANSCRIBE_MODEL = os.getenv("JARVIS_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
_TTS_MODEL = os.getenv("JARVIS_TTS_MODEL", "gpt-4o-mini-tts")
_TTS_VOICE = os.getenv("JARVIS_TTS_VOICE", "alloy")
_TTS_INSTRUCTIONS = os.getenv(
    "JARVIS_TTS_INSTRUCTIONS",
    "Speak in clear British English with a consistent, natural assistant tone.",
).strip()


def command(text: str, device_id: str = "console-unknown", location: str = "unknown") -> str:
    prompt = f"""
    You are Jarvis, a concise personal assistant.
    Respond clearly and helpfully.

    Device: {device_id}
    Location: {location}
    User request: {text}
    """
    response = _client.responses.create(
        model=_CHAT_MODEL,
        input=prompt,
    )
    return response.output_text


def transcribe_file_bytes(filename: str, audio_bytes: bytes) -> str:
    audio_stream = BytesIO(audio_bytes)
    audio_stream.name = filename or "input.wav"
    transcript = _client.audio.transcriptions.create(
        model=_TRANSCRIBE_MODEL,
        file=audio_stream,
    )
    return transcript.text


def tts_wav_bytes(text: str) -> bytes:
    # OpenAI Python SDK has minor signature differences across versions.
    create_kwargs = {
        "model": _TTS_MODEL,
        "voice": _TTS_VOICE,
        "input": text,
        "format": "wav",
    }
    if _TTS_INSTRUCTIONS:
        create_kwargs["instructions"] = _TTS_INSTRUCTIONS
    try:
        result = _client.audio.speech.create(**create_kwargs)
    except TypeError:
        legacy_kwargs = {
            "model": _TTS_MODEL,
            "voice": _TTS_VOICE,
            "input": text,
            "response_format": "wav",
        }
        try:
            if _TTS_INSTRUCTIONS:
                legacy_kwargs["instructions"] = _TTS_INSTRUCTIONS
            result = _client.audio.speech.create(**legacy_kwargs)
        except TypeError:
            # Compatibility fallback for SDK variants that do not support `instructions`.
            legacy_kwargs.pop("instructions", None)
            result = _client.audio.speech.create(**legacy_kwargs)

    if hasattr(result, "read"):
        return result.read()
    if hasattr(result, "content"):
        return result.content
    if isinstance(result, (bytes, bytearray)):
        return bytes(result)
    raise RuntimeError("Unsupported TTS response object from OpenAI SDK")
