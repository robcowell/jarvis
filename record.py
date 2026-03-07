import os
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
from collections import deque


def _env_float(name, fallback, minimum=None):
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        value = float(fallback)
    else:
        try:
            value = float(raw)
        except ValueError:
            value = float(fallback)

    if minimum is not None and value < minimum:
        return float(minimum)
    return value


def _env_int(name, fallback, minimum=None):
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
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
DEFAULT_MAX_DURATION = _env_float("VOICE_MAX_DURATION", 6.0, minimum=0.5)
DEFAULT_SAMPLE_RATE = _env_int("VOICE_SAMPLE_RATE", 48000, minimum=8000)
DEFAULT_CHUNK_SIZE = _env_int("VOICE_CHUNK_SIZE", 1024, minimum=128)
DEFAULT_SPEECH_THRESHOLD = _env_float("VOICE_SPEECH_THRESHOLD", 0.012, minimum=0.001)
DEFAULT_SILENCE_DURATION = _env_float("VOICE_SILENCE_DURATION", 0.75, minimum=0.1)
DEFAULT_MIN_SPEECH_DURATION = _env_float("VOICE_MIN_SPEECH_DURATION", 0.35, minimum=0.1)
DEFAULT_NO_SPEECH_TIMEOUT = _env_float("VOICE_NO_SPEECH_TIMEOUT", 2.0, minimum=0.2)
DEFAULT_PRE_ROLL_CHUNKS = _env_int("VOICE_PRE_ROLL_CHUNKS", 2, minimum=1)


def get_input_devices():
    devices = sd.query_devices()
    input_devices = []

    for i, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            input_devices.append((i, device["name"]))

    return input_devices


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

    if device is None:
        device = input_devices[0][0]

    print(f"Recording using device {device} (speech endpoint mode)...")

    max_chunks = max(1, int(max_duration * fs / chunk_size))
    silence_chunks_to_stop = max(1, int(silence_duration * fs / chunk_size))
    min_speech_chunks = max(1, int(min_speech_duration * fs / chunk_size))
    no_speech_chunks = max(1, int(no_speech_timeout * fs / chunk_size))
    pre_roll = deque(maxlen=DEFAULT_PRE_ROLL_CHUNKS)

    speech_started = False
    captured_chunks = []
    speech_chunks = 0
    silent_after_speech = 0

    with sd.InputStream(
        samplerate=fs,
        channels=1,
        dtype="float32",
        device=device,
        blocksize=chunk_size
    ) as stream:
        for chunk_index in range(max_chunks):
            chunk, overflowed = stream.read(chunk_size)

            if overflowed:
                print("Warning: audio input overflow detected")

            rms = float(np.sqrt(np.mean(np.square(chunk))))

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

    if not captured_chunks:
        raise RuntimeError("No speech captured")

    audio = np.concatenate(captured_chunks, axis=0)
    write(filename, fs, audio)
    print(f"Saved {filename}")
    return filename
