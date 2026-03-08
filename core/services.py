import os
from io import BytesIO
from pathlib import Path
from typing import Any

from openai import OpenAI

from core.skills.router import CommandRouter
from core.skills.registry import SkillRegistry


_client: OpenAI | None = None
_CHAT_MODEL = os.getenv("JARVIS_COMMAND_MODEL", "gpt-5")
_TRANSCRIBE_MODEL = os.getenv("JARVIS_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
_TTS_MODEL = os.getenv("JARVIS_TTS_MODEL", "gpt-4o-mini-tts")
_TTS_VOICE = os.getenv("JARVIS_TTS_VOICE", "ballad")
_TTS_INSTRUCTIONS = os.getenv(
    "JARVIS_TTS_INSTRUCTIONS",
    "Speak in clear British English with a consistent, natural assistant tone.",
).strip()
_DEFAULT_SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"
_SKILLS_ROOT = Path(os.getenv("JARVIS_SKILLS_DIR", str(_DEFAULT_SKILLS_ROOT))).resolve()
_skill_registry = SkillRegistry(skills_root=_SKILLS_ROOT)
_skill_registry.load()
_command_router = CommandRouter(registry=_skill_registry)


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def list_skills() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for loaded in _skill_registry.skills:
        items.append(
            {
                "id": loaded.manifest.skill_id,
                "name": loaded.manifest.name,
                "description": loaded.manifest.description,
                "entry_class": loaded.manifest.entry_class,
                "trigger_phrases": list(loaded.manifest.trigger_phrases),
                "priority": loaded.manifest.priority,
                "enabled": loaded.manifest.enabled,
                "path": str(loaded.path),
            }
        )
    return items


def command(text: str, device_id: str = "console-unknown", location: str = "unknown") -> dict[str, Any]:
    try:
        skill_result = _command_router.execute(text=text, device_id=device_id, location=location)
    except Exception as exc:
        # Keep command path resilient if a single skill has an issue.
        print(f"Skill routing failed; falling back to LLM: {exc}")
        skill_result = None

    if skill_result is not None:
        return skill_result.to_command_payload()

    prompt = f"""
    You are Jarvis, a concise personal assistant.
    Respond clearly and helpfully.

    Device: {device_id}
    Location: {location}
    User request: {text}
    """
    client = _get_client()
    response = client.responses.create(
        model=_CHAT_MODEL,
        input=prompt,
    )
    return {
        "ok": True,
        "response": response.output_text,
        "source": "core",
        "route": "llm",
        "skill_id": None,
    }


def transcribe_file_bytes(filename: str, audio_bytes: bytes) -> str:
    client = _get_client()
    audio_stream = BytesIO(audio_bytes)
    audio_stream.name = filename or "input.wav"
    transcript = client.audio.transcriptions.create(
        model=_TRANSCRIBE_MODEL,
        file=audio_stream,
    )
    return transcript.text


def tts_wav_bytes(text: str) -> bytes:
    client = _get_client()
    print(f"[TTS] path=core model={_TTS_MODEL} voice={_TTS_VOICE} chars={len((text or '').strip())}")
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
        result = client.audio.speech.create(**create_kwargs)
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
            result = client.audio.speech.create(**legacy_kwargs)
        except TypeError:
            # Compatibility fallback for SDK variants that do not support `instructions`.
            legacy_kwargs.pop("instructions", None)
            result = client.audio.speech.create(**legacy_kwargs)

    if hasattr(result, "read"):
        wav = result.read()
        print(f"[TTS] path=core rendered_bytes={len(wav)}")
        return wav
    if hasattr(result, "content"):
        wav = result.content
        print(f"[TTS] path=core rendered_bytes={len(wav)}")
        return wav
    if isinstance(result, (bytes, bytearray)):
        wav = bytes(result)
        print(f"[TTS] path=core rendered_bytes={len(wav)}")
        return wav
    raise RuntimeError("Unsupported TTS response object from OpenAI SDK")
