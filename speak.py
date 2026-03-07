import os
import shutil
import subprocess
from pathlib import Path

# TTS runtime configuration (override with environment variables on the Pi).
PIPER_PATH = os.getenv("PIPER_PATH", "/home/robcowell/piper/build/piper").strip()
PIPER_MODEL_PATH = os.getenv("PIPER_MODEL_PATH", "/home/robcowell/piper/voices/en_US-lessac-medium.onnx").strip()
PIPER_SAMPLE_RATE = int(os.getenv("PIPER_SAMPLE_RATE", "22050"))
APLAY_PATH = os.getenv("APLAY_PATH", "aplay").strip()
ESPEAK_PATH = os.getenv("ESPEAK_PATH", "espeak").strip()
TTS_FALLBACK_TO_ESPEAK = os.getenv("TTS_FALLBACK_TO_ESPEAK", "1").strip().lower() not in {"0", "false", "no"}


def _expand_path(path: str) -> str:
    return str(Path(path).expanduser()) if path else ""


def _command_exists(command: str) -> bool:
    if not command:
        return False
    expanded = _expand_path(command)
    return Path(expanded).is_file() or shutil.which(expanded) is not None or shutil.which(command) is not None


def _run_piper(text: str) -> None:
    piper_path = _expand_path(PIPER_PATH)
    model_path = _expand_path(PIPER_MODEL_PATH)

    if not _command_exists(piper_path):
        raise RuntimeError(f"Piper executable not found: {piper_path}")
    if not model_path:
        raise RuntimeError("PIPER_MODEL_PATH is not set")
    if not Path(model_path).is_file():
        raise RuntimeError(f"Piper model file not found: {model_path}")
    if not _command_exists(APLAY_PATH):
        raise RuntimeError(f"Audio playback command not found: {APLAY_PATH}")

    piper_cmd = [piper_path, "--model", model_path, "--output-raw"]
    aplay_cmd = [APLAY_PATH, "-r", str(PIPER_SAMPLE_RATE), "-f", "S16_LE", "-t", "raw", "-"]

    piper_process = subprocess.Popen(
        piper_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    aplay_process = subprocess.Popen(
        aplay_cmd,
        stdin=piper_process.stdout,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE
    )

    # Allow piper stdout to receive SIGPIPE if aplay exits unexpectedly.
    if piper_process.stdout is not None:
        piper_process.stdout.close()

    _, piper_stderr = piper_process.communicate(input=f"{text}\n".encode("utf-8"))
    aplay_stderr = b""
    if aplay_process.stderr is not None:
        aplay_stderr = aplay_process.stderr.read()
    aplay_return_code = aplay_process.wait()

    if piper_process.returncode != 0:
        err = piper_stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Piper failed with code {piper_process.returncode}: {err}")
    if aplay_return_code != 0:
        err = aplay_stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Audio playback failed with code {aplay_return_code}: {err}")


def _run_espeak(text: str) -> None:
    if not _command_exists(ESPEAK_PATH):
        raise RuntimeError(f"eSpeak executable not found: {ESPEAK_PATH}")

    result = subprocess.run(
        [ESPEAK_PATH, text],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        err = (result.stderr or "").strip()
        raise RuntimeError(f"eSpeak failed with code {result.returncode}: {err}")


def speak(text):
    message = (text or "").strip()
    if not message:
        return

    print(f"Jarvis says: {message}")

    try:
        _run_piper(message)
    except Exception as exc:
        if not TTS_FALLBACK_TO_ESPEAK:
            raise RuntimeError(f"Piper TTS failed: {exc}") from exc

        print(f"Piper TTS failed ({exc}). Falling back to eSpeak.")
        _run_espeak(message)
