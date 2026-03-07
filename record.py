import sounddevice as sd
from scipy.io.wavfile import write


def get_input_devices():
    devices = sd.query_devices()
    input_devices = []

    for i, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            input_devices.append((i, device["name"]))

    return input_devices


def has_input_device():
    return len(get_input_devices()) > 0


def record_audio(filename="input.wav", duration=6, fs=48000, device=None):
    input_devices = get_input_devices()

    if not input_devices:
        raise RuntimeError("No audio input device detected")

    if device is None:
        device = input_devices[0][0]

    print(f"Recording using device {device}...")

    audio = sd.rec(
        int(duration * fs),
        samplerate=fs,
        channels=1,
        device=device
    )
    sd.wait()

    write(filename, fs, audio)
    print(f"Saved {filename}")
    return filename
