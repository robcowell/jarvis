import os
import threading
import time
from typing import Callable, Optional


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _env_float(name: str, default: float, minimum: Optional[float] = None) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        value = float(default)
    else:
        try:
            value = float(raw)
        except ValueError:
            value = float(default)
    if minimum is not None and value < minimum:
        return float(minimum)
    return value


def _env_optional_int(name: str) -> Optional[int]:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


WAKE_ALWAYS_LISTEN_ENABLED = _env_bool("WAKE_ALWAYS_LISTEN_ENABLED", False)
PORCUPINE_KEYWORDS = [part.strip() for part in os.getenv("PORCUPINE_KEYWORDS", "jarvis").split(",") if part.strip()]
PORCUPINE_SENSITIVITY = _env_float("PORCUPINE_SENSITIVITY", 0.6, minimum=0.0)
WAKE_DETECTION_COOLDOWN = _env_float("WAKE_DETECTION_COOLDOWN", 1.5, minimum=0.0)
PORCUPINE_AUDIO_DEVICE_INDEX = _env_optional_int("PORCUPINE_AUDIO_DEVICE_INDEX")
PICOVOICE_ACCESS_KEY = (
    (os.getenv("PICOVOICE_ACCESS_KEY") or "").strip()
    or (os.getenv("PORCUPINE_ACCESS_KEY") or "").strip()
)


class PorcupineWakeListener:
    def __init__(
        self,
        on_detect: Callable[[str], None],
        on_error: Optional[Callable[[str], None]] = None,
    ):
        self._on_detect = on_detect
        self._on_error = on_error
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="porcupine-wake-listener", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        porcupine = None
        recorder = None

        try:
            import pvporcupine
            from pvrecorder import PvRecorder

            if not PORCUPINE_KEYWORDS:
                raise RuntimeError("PORCUPINE_KEYWORDS is empty")

            create_args = {
                "keywords": PORCUPINE_KEYWORDS,
                "sensitivities": [PORCUPINE_SENSITIVITY] * len(PORCUPINE_KEYWORDS),
            }
            if PICOVOICE_ACCESS_KEY:
                create_args["access_key"] = PICOVOICE_ACCESS_KEY

            try:
                porcupine = pvporcupine.create(**create_args)
            except TypeError:
                # Compatibility for SDK variants that strictly require access_key.
                if "access_key" not in create_args:
                    raise RuntimeError(
                        "Porcupine access key may be required. Set PICOVOICE_ACCESS_KEY."
                    )
                raise

            recorder = PvRecorder(
                device_index=PORCUPINE_AUDIO_DEVICE_INDEX if PORCUPINE_AUDIO_DEVICE_INDEX is not None else -1,
                frame_length=porcupine.frame_length,
            )
            recorder.start()

            print(
                "Wake listener active "
                f"(keywords={PORCUPINE_KEYWORDS}, sensitivity={PORCUPINE_SENSITIVITY}, "
                f"device_index={'default' if PORCUPINE_AUDIO_DEVICE_INDEX is None else PORCUPINE_AUDIO_DEVICE_INDEX})"
            )
            last_detected_at = 0.0

            while not self._stop_event.is_set():
                pcm = recorder.read()
                result = porcupine.process(pcm)
                if result < 0:
                    continue

                now = time.time()
                if now - last_detected_at < WAKE_DETECTION_COOLDOWN:
                    continue
                last_detected_at = now

                keyword = PORCUPINE_KEYWORDS[result] if result < len(PORCUPINE_KEYWORDS) else "wake-word"
                self._on_detect(keyword)
        except Exception as exc:
            message = f"Wake listener failed: {exc}"
            print(message)
            if self._on_error:
                self._on_error(message)
        finally:
            if recorder is not None:
                try:
                    recorder.stop()
                finally:
                    recorder.delete()
            if porcupine is not None:
                porcupine.delete()


def list_wake_input_devices() -> list[str]:
    from pvrecorder import PvRecorder

    return PvRecorder.get_available_devices()
