import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from console.speech_manager import SpeechInterrupted, get_speech_manager

# TTS runtime configuration (override with environment variables on the Pi).
PIPER_PATH = os.getenv("PIPER_PATH", "/home/robcowell/piper/build/piper").strip()
PIPER_MODEL_PATH = os.getenv("PIPER_MODEL_PATH", "/home/robcowell/piper/voices/en_US-lessac-medium.onnx").strip()
PIPER_SAMPLE_RATE = int(os.getenv("PIPER_SAMPLE_RATE", "22050"))
APLAY_PATH = os.getenv("APLAY_PATH", "aplay").strip()
ESPEAK_PATH = os.getenv("ESPEAK_PATH", "espeak").strip()
TTS_FALLBACK_TO_ESPEAK = os.getenv("TTS_FALLBACK_TO_ESPEAK", "0").strip().lower() not in {"0", "false", "no"}


def _expand_path(path: str) -> str:
    return str(Path(path).expanduser()) if path else ""


def _command_exists(command: str) -> bool:
    if not command:
        return False
    expanded = _expand_path(command)
    return Path(expanded).is_file() or shutil.which(expanded) is not None or shutil.which(command) is not None


def _wait_process_interruptible(
    proc: subprocess.Popen,
    generation: int,
    manager,
    poll_interval_seconds: float = 0.02,
) -> int:
    while True:
        manager.assert_not_interrupted(generation)
        code = proc.poll()
        if code is not None:
            return code
        time.sleep(poll_interval_seconds)


def _run_piper(text: str, generation: int, manager) -> None:
    piper_path = _expand_path(PIPER_PATH)
    model_path = _expand_path(PIPER_MODEL_PATH)

    if piper_path and Path(piper_path).is_dir():
        raise RuntimeError(f"PIPER_PATH must point to executable, not directory: {piper_path}")
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

    manager.register_process(piper_process, generation)
    manager.register_process(aplay_process, generation)

    # Allow piper stdout to receive SIGPIPE if aplay exits unexpectedly.
    if piper_process.stdout is not None:
        piper_process.stdout.close()

    piper_stderr = b""
    aplay_stderr = b""
    try:
        if piper_process.stdin is not None:
            piper_process.stdin.write(f"{text}\n".encode("utf-8"))
            piper_process.stdin.close()

        piper_return_code = _wait_process_interruptible(piper_process, generation, manager)
        aplay_return_code = _wait_process_interruptible(aplay_process, generation, manager)

        if piper_process.stderr is not None:
            piper_stderr = piper_process.stderr.read()
        if aplay_process.stderr is not None:
            aplay_stderr = aplay_process.stderr.read()

        if piper_return_code != 0:
            err = piper_stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Piper failed with code {piper_return_code}: {err}")
        if aplay_return_code != 0:
            err = aplay_stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Audio playback failed with code {aplay_return_code}: {err}")
    except SpeechInterrupted:
        _terminate_process(piper_process)
        _terminate_process(aplay_process)
        raise
    finally:
        manager.unregister_process(piper_process)
        manager.unregister_process(aplay_process)


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


def play_wav_file(path: str) -> None:
    if not _command_exists(APLAY_PATH):
        raise RuntimeError(f"Audio playback command not found: {APLAY_PATH}")
    file_path = _expand_path(path)
    if not Path(file_path).is_file():
        raise RuntimeError(f"WAV file not found: {file_path}")

    manager = get_speech_manager()

    def runner(generation: int) -> None:
        _play_wav_file_blocking(file_path, generation, manager)

    manager.start_speech(runner, label="wav-file")


def play_wav_bytes(audio: bytes) -> None:
    if not audio:
        raise RuntimeError("No audio bytes provided")
    print(f"[TTS] playback=wav-bytes bytes={len(audio)}")
    manager = get_speech_manager()

    def runner(generation: int) -> None:
        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_file.write(audio)
                temp_file.flush()
                temp_path = temp_file.name
            _play_wav_file_blocking(temp_path, generation, manager)
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    manager.start_speech(runner, label="wav-bytes")


def speak(text, allow_espeak_fallback=None):
    message = (text or "").strip()
    if not message:
        return

    fallback_enabled = TTS_FALLBACK_TO_ESPEAK if allow_espeak_fallback is None else bool(allow_espeak_fallback)
    print(f"[TTS] path=local-piper chars={len(message)} fallback_espeak={int(fallback_enabled)}")
    print(f"Jarvis says: {message}")

    manager = get_speech_manager()

    def runner(generation: int) -> None:
        try:
            _run_piper(message, generation, manager)
        except SpeechInterrupted:
            raise
        except Exception as exc:
            if not fallback_enabled:
                raise RuntimeError(f"Piper TTS failed: {exc}") from exc

            # eSpeak playback is blocking and not process-tracked; use only as optional fallback.
            print(f"[TTS] fallback=espeak reason=piper_error detail={exc}")
            _run_espeak(message)

    manager.start_speech(runner, label="local-piper")


def stop_speech() -> dict[str, int]:
    return get_speech_manager().stop_speech()


def is_speaking() -> bool:
    return get_speech_manager().is_speaking()


def _play_wav_file_blocking(file_path: str, generation: int, manager) -> None:
    process = subprocess.Popen(
        [APLAY_PATH, file_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    manager.register_process(process, generation)
    stderr_bytes = b""
    try:
        return_code = _wait_process_interruptible(process, generation, manager)
        if process.stderr is not None:
            stderr_bytes = process.stderr.read()
        if return_code != 0:
            err = stderr_bytes.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Audio playback failed with code {return_code}: {err}")
    except SpeechInterrupted:
        _terminate_process(process)
        raise
    finally:
        manager.unregister_process(process)


def _terminate_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        try:
            proc.wait(timeout=0.15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=0.15)
    except Exception:
        pass
