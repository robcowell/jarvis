import os
import struct
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
PORCUPINE_ACCESS_KEY = (os.getenv("PORCUPINE_ACCESS_KEY") or "").strip()


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
        pa = None
        stream = None

        try:
            import pvporcupine
            import pyaudio

            if not PORCUPINE_KEYWORDS:
                raise RuntimeError("PORCUPINE_KEYWORDS is empty")

            create_args = {
                "keywords": PORCUPINE_KEYWORDS,
                "sensitivities": [PORCUPINE_SENSITIVITY] * len(PORCUPINE_KEYWORDS),
            }
            if PORCUPINE_ACCESS_KEY:
                create_args["access_key"] = PORCUPINE_ACCESS_KEY

            try:
                porcupine = pvporcupine.create(**create_args)
            except TypeError:
                # Compatibility for SDK variants that strictly require access_key.
                if "access_key" not in create_args:
                    raise RuntimeError(
                        "Porcupine access key may be required. Set PORCUPINE_ACCESS_KEY."
                    )
                raise

            pa = pyaudio.PyAudio()
            stream = pa.open(
                rate=porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=porcupine.frame_length,
                input_device_index=PORCUPINE_AUDIO_DEVICE_INDEX,
            )

            print(f"Wake listener active (keywords={PORCUPINE_KEYWORDS}, sensitivity={PORCUPINE_SENSITIVITY})")
            last_detected_at = 0.0

            while not self._stop_event.is_set():
                frame = stream.read(porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * porcupine.frame_length, frame)
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
            if stream is not None:
                stream.close()
            if pa is not None:
                pa.terminate()
            if porcupine is not None:
                porcupine.delete()
