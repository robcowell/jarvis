import os
from pathlib import Path
import time

import requests


class CoreUnavailableError(RuntimeError):
    """Raised when the core cannot be reached or returns invalid data."""


def _env_float(name: str, fallback: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return float(fallback)
    try:
        return float(raw)
    except ValueError:
        return float(fallback)


JARVIS_CORE_URL = (os.getenv("JARVIS_CORE_URL") or "").strip().rstrip("/")
JARVIS_CORE_TIMEOUT_SECONDS = _env_float("JARVIS_CORE_TIMEOUT_SECONDS", 20.0)
JARVIS_CORE_TTS_TIMEOUT_SECONDS = _env_float("JARVIS_CORE_TTS_TIMEOUT_SECONDS", JARVIS_CORE_TIMEOUT_SECONDS)


def is_enabled() -> bool:
    return bool(JARVIS_CORE_URL)


def _url(path: str) -> str:
    if not JARVIS_CORE_URL:
        raise CoreUnavailableError("JARVIS_CORE_URL is not configured")
    return f"{JARVIS_CORE_URL}{path}"


def transcribe_audio_file(file_path: str) -> str:
    path = Path(file_path)
    if not path.is_file():
        raise CoreUnavailableError(f"Audio file not found: {file_path}")
    try:
        with path.open("rb") as f:
            files = {"file": (path.name, f, "audio/wav")}
            response = requests.post(_url("/transcribe"), files=files, timeout=JARVIS_CORE_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        text = (payload.get("text") or "").strip()
        if not text:
            raise CoreUnavailableError("Core /transcribe returned empty text")
        return text
    except requests.RequestException as exc:
        raise CoreUnavailableError(f"Core /transcribe unreachable: {exc}") from exc
    except ValueError as exc:
        raise CoreUnavailableError(f"Core /transcribe returned invalid JSON: {exc}") from exc


def command(text: str, device_id: str, location: str) -> str:
    try:
        response = requests.post(
            _url("/command"),
            json={
                "text": text,
                "device_id": device_id,
                "location": location,
            },
            timeout=JARVIS_CORE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        result = (payload.get("response") or "").strip()
        if not result:
            raise CoreUnavailableError("Core /command returned empty response")
        return result
    except requests.RequestException as exc:
        raise CoreUnavailableError(f"Core /command unreachable: {exc}") from exc
    except ValueError as exc:
        raise CoreUnavailableError(f"Core /command returned invalid JSON: {exc}") from exc


def tts(text: str) -> bytes:
    started_at = time.monotonic()
    text_len = len((text or "").strip())
    timeout_seconds = JARVIS_CORE_TTS_TIMEOUT_SECONDS
    print(
        f"[TTS] path=core stage=request-start endpoint=/tts "
        f"request_chars={text_len} timeout_seconds={timeout_seconds}"
    )
    try:
        response = requests.post(
            _url("/tts"),
            json={"text": text},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        audio = response.content
        if not audio:
            raise CoreUnavailableError("Core /tts returned empty audio")
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        print(
            f"[TTS] path=core stage=request-success endpoint=/tts "
            f"response_bytes={len(audio)} duration_ms={elapsed_ms}"
        )
        return audio
    except requests.Timeout as exc:
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        print(
            f"[TTS] path=core stage=request-failed endpoint=/tts reason=timeout "
            f"timeout_seconds={timeout_seconds} duration_ms={elapsed_ms}"
        )
        raise CoreUnavailableError(
            f"Core /tts timed out after {timeout_seconds}s ({elapsed_ms}ms elapsed): {exc}"
        ) from exc
    except requests.RequestException as exc:
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        print(
            f"[TTS] path=core stage=request-failed endpoint=/tts reason=request_error "
            f"duration_ms={elapsed_ms} detail={exc}"
        )
        raise CoreUnavailableError(f"Core /tts unreachable: {exc}") from exc
