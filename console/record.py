import os
import wave
from collections import deque

import numpy as np
from pvrecorder import PvRecorder
from shared.memory import get_memory_service

_memory = get_memory_service()


def _env_float(name, config_key, fallback, minimum=None):
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        raw = _memory.configuration.get(config_key, fallback)
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        value = float(fallback)
    else:
        try:
            value = float(raw)
        except ValueError:
            value = float(fallback)

    if minimum is not None and value < minimum:
        return float(minimum)
    return value


def _env_int(name, config_key, fallback, minimum=None):
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        raw = _memory.configuration.get(config_key, fallback)
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        value = int(fallback)
    else:
        try:
            value = int(raw)
        except ValueError:
            value = int(fallback)

    if minimum is not None and value < minimum:
        return int(minimum)
    return value


# Speech endpoint defaults (overridable via environment variables).
DEFAULT_MAX_DURATION = _env_float("VOICE_MAX_DURATION", "voice.max_duration", 6.0, minimum=0.5)
DEFAULT_SAMPLE_RATE = _env_int("VOICE_SAMPLE_RATE", "voice.sample_rate", 16000, minimum=8000)
DEFAULT_CHUNK_SIZE = _env_int("VOICE_CHUNK_SIZE", "voice.chunk_size", 1024, minimum=128)
DEFAULT_SPEECH_THRESHOLD = _env_float("VOICE_SPEECH_THRESHOLD", "voice.speech_threshold", 0.012, minimum=0.001)
DEFAULT_SILENCE_DURATION = _env_float("VOICE_SILENCE_DURATION", "voice.silence_duration", 0.75, minimum=0.1)
DEFAULT_MIN_SPEECH_DURATION = _env_float("VOICE_MIN_SPEECH_DURATION", "voice.min_speech_duration", 0.35, minimum=0.1)
DEFAULT_NO_SPEECH_TIMEOUT = _env_float("VOICE_NO_SPEECH_TIMEOUT", "voice.no_speech_timeout", 2.0, minimum=0.2)
DEFAULT_PRE_ROLL_CHUNKS = _env_int("VOICE_PRE_ROLL_CHUNKS", "voice.pre_roll_chunks", 2, minimum=1)
DEFAULT_DEVICE_INDEX = _env_int("VOICE_AUDIO_DEVICE_INDEX", "voice.audio_device_index", -1, minimum=-1)


def get_input_devices():
    devices = PvRecorder.get_available_devices()
    return [(i, name) for i, name in enumerate(devices)]


def has_input_device():
    return len(get_input_devices()) > 0


def record_audio(
    filename="input.wav",
    max_duration=DEFAULT_MAX_DURATION,
    fs=DEFAULT_SAMPLE_RATE,
    device=None,
    chunk_size=DEFAULT_CHUNK_SIZE,
    speech_threshold=DEFAULT_SPEECH_THRESHOLD,
    silence_duration=DEFAULT_SILENCE_DURATION,
    min_speech_duration=DEFAULT_MIN_SPEECH_DURATION,
    no_speech_timeout=DEFAULT_NO_SPEECH_TIMEOUT,
):
    input_devices = get_input_devices()

    if not input_devices:
        raise RuntimeError("No audio input device detected")

    device_index = device if device is not None else DEFAULT_DEVICE_INDEX
    if device_index == -1:
        # -1 means default input device for PvRecorder.
        selected_label = "default"
    elif device_index < 0 or device_index >= len(input_devices):
        raise RuntimeError(f"Invalid VOICE_AUDIO_DEVICE_INDEX/device value: {device_index}")
    else:
        selected_label = f"{device_index} ({input_devices[device_index][1]})"

    print(f"Recording using device {selected_label} (PvRecorder speech endpoint mode)...")

    # PvRecorder captures mono 16-bit PCM at 16kHz for speech workflows.
    if fs != 16000:
        print(f"VOICE_SAMPLE_RATE={fs} requested; using 16000 for PvRecorder compatibility.")
        fs = 16000

    max_chunks = max(1, int(max_duration * fs / chunk_size))
    silence_chunks_to_stop = max(1, int(silence_duration * fs / chunk_size))
    min_speech_chunks = max(1, int(min_speech_duration * fs / chunk_size))
    no_speech_chunks = max(1, int(no_speech_timeout * fs / chunk_size))
    pre_roll = deque(maxlen=DEFAULT_PRE_ROLL_CHUNKS)

    speech_started = False
    captured_chunks = []
    speech_chunks = 0
    silent_after_speech = 0

    recorder = None
    try:
        recorder = PvRecorder(
            device_index=device_index,
            frame_length=chunk_size,
        )
        recorder.start()

        for chunk_index in range(max_chunks):
            pcm = recorder.read()
            chunk = np.asarray(pcm, dtype=np.int16)
            chunk_f = chunk.astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(np.square(chunk_f))))

            if not speech_started:
                pre_roll.append(chunk.copy())

                if rms >= speech_threshold:
                    speech_started = True
                    captured_chunks.extend(list(pre_roll))
                    speech_chunks += 1
                    silent_after_speech = 0
                elif chunk_index >= no_speech_chunks:
                    raise RuntimeError("No speech detected")
                continue

            captured_chunks.append(chunk.copy())

            if rms >= speech_threshold:
                speech_chunks += 1
                silent_after_speech = 0
            else:
                silent_after_speech += 1

            # Stop shortly after the user finishes speaking.
            if speech_chunks >= min_speech_chunks and silent_after_speech >= silence_chunks_to_stop:
                break
    finally:
        if recorder is not None:
            try:
                recorder.stop()
            finally:
                recorder.delete()

    if not captured_chunks:
        raise RuntimeError("No speech captured")

    audio = np.concatenate(captured_chunks, axis=0).astype(np.int16)
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(fs)
        wf.writeframes(audio.tobytes())
    print(f"Saved {filename}")
    return filename
