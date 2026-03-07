# J.A.R.V.I.S. Raspberry Pi Voice Assistant

Flask-based touchscreen voice assistant designed for Raspberry Pi kiosk use (800x480), with:

- Touch-friendly sci-fi web UI (Chromium kiosk)
- Microphone recording with speech endpoint detection (stops on silence)
- Speech transcription via OpenAI
- LLM response generation via OpenAI
- Spoken output via Piper TTS (with optional eSpeak fallback)

## Project Structure

- `app.py` - Flask app and routes (`/`, `/listen`, `/ask`)
- `record.py` - Audio capture and speech-endpoint logic
- `transcribe.py` - Speech-to-text call
- `brain.py` - Prompting + response generation
- `speak.py` - Piper/eSpeak text-to-speech
- `templates/index.html` - Main UI template
- `static/css/jarvis.css` - UI styles
- `static/js/jarvis-ui.js` - UI behavior

## Requirements

## System packages (Pi)

- Python 3.10+ recommended
- `aplay` (usually from ALSA utilities)
- Piper binary built/installed (for primary TTS)
- `espeak` optional (fallback only)

Piper is **not** installed by `pip`. You must install/build it separately on the Pi and point `PIPER_PATH` to the executable.

## Python packages

Install from your environment:

```bash
pip install flask openai sounddevice scipy numpy
```

## Run

From project root:

```bash
python app.py
```

Then open `http://<pi-ip>:5000` (or your local host) in Chromium kiosk mode.

## Environment Variables (Complete Reference)

This section lists all environment variables used for configuration across the project.

## Required

- `OPENAI_API_KEY`
  - Used by the OpenAI Python SDK in both `transcribe.py` and `brain.py`.
  - No default.

## OpenAI (optional SDK-level)

These are supported by the OpenAI SDK if needed for custom deployments:

- `OPENAI_BASE_URL` - custom API base URL
- `OPENAI_ORG_ID` - optional organization ID
- `OPENAI_PROJECT_ID` - optional project ID

If unset, the SDK uses its built-in defaults.

## TTS (speak.py)

- `PIPER_PATH`
  - Default: `/home/robcowell/piper/build/piper`
  - Path to Piper executable
- `PIPER_MODEL_PATH`
  - Default: `/home/robcowell/piper/voices/en_US-lessac-medium.onnx`
  - Path to Piper `.onnx` voice model
- `PIPER_SAMPLE_RATE`
  - Default: `22050`
  - Raw audio sample rate sent to `aplay`
- `APLAY_PATH`
  - Default: `aplay`
  - Playback command path/name
- `TTS_FALLBACK_TO_ESPEAK`
  - Default: `1`
  - If Piper fails, fallback to eSpeak (`1`, `true`, `yes` enable; `0`, `false`, `no` disable)
- `ESPEAK_PATH`
  - Default: `espeak`
  - eSpeak command path/name used only when fallback is enabled

## Voice capture / endpointing (record.py)

- `VOICE_MAX_DURATION`
  - Default: `6.0`
  - Max recording duration in seconds (hard cap)
  - Minimum clamp: `0.5`
- `VOICE_SAMPLE_RATE`
  - Default: `16000`
  - Input sample rate (Hz)
  - Minimum clamp: `8000`
- `VOICE_CHUNK_SIZE`
  - Default: `1024`
  - Audio block size per read
  - Minimum clamp: `128`
- `VOICE_SPEECH_THRESHOLD`
  - Default: `0.012`
  - RMS threshold for speech detection
  - Minimum clamp: `0.001`
- `VOICE_SILENCE_DURATION`
  - Default: `0.75`
  - Silence (seconds) after speech to stop recording
  - Minimum clamp: `0.1`
- `VOICE_MIN_SPEECH_DURATION`
  - Default: `0.35`
  - Minimum voiced duration before silence can end capture
  - Minimum clamp: `0.1`
- `VOICE_NO_SPEECH_TIMEOUT`
  - Default: `2.0`
  - If no speech starts within this time, recording aborts
  - Minimum clamp: `0.2`
- `VOICE_PRE_ROLL_CHUNKS`
  - Default: `2`
  - Number of chunks buffered before trigger and prepended to capture
  - Minimum clamp: `1`

## Suggested `.env` Example

```bash
# Required
OPENAI_API_KEY="sk-..."

# Piper TTS
PIPER_PATH="/home/robcowell/piper/build/piper"
PIPER_MODEL_PATH="/home/robcowell/piper/voices/en_US-lessac-medium.onnx"
PIPER_SAMPLE_RATE="22050"
APLAY_PATH="aplay"
TTS_FALLBACK_TO_ESPEAK="1"
ESPEAK_PATH="espeak"

# Voice endpoint detection
VOICE_MAX_DURATION="6.0"
VOICE_SAMPLE_RATE="16000"
VOICE_CHUNK_SIZE="1024"
VOICE_SPEECH_THRESHOLD="0.012"
VOICE_SILENCE_DURATION="0.65"
VOICE_MIN_SPEECH_DURATION="0.30"
VOICE_NO_SPEECH_TIMEOUT="1.6"
VOICE_PRE_ROLL_CHUNKS="2"
```

## Notes

- `/listen` performs full pipeline: record -> transcribe -> generate -> speak.
- `/ask` performs text-only pipeline: generate response (no TTS playback by default in current flow).
- UI is tuned for 800x480 kiosk operation and low-overhead rendering on Pi 3 B+.
