import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
from collections import deque


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
    max_duration=6.0,
    fs=16000,
    device=None,
    chunk_size=1024,
    speech_threshold=0.012,
    silence_duration=0.75,
    min_speech_duration=0.35,
    no_speech_timeout=2.0,
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
    pre_roll = deque(maxlen=2)

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
