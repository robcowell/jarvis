# J.A.R.V.I.S. Distributed Voice Assistant (Phase 1)

This repository started as a single Raspberry Pi Flask app. It is now being refactored into a distributed architecture:

- `Console` (Raspberry Pi): UI + audio I/O + wake word
- `Core` (Windows PC): API server + AI workloads

Current implementation still supports local fallback for resilience.

## Current capabilities

Console-side:

- Touch-friendly sci-fi web UI (Chromium kiosk)
- Microphone recording with speech endpoint detection (stops on silence)
- Wake-word listener (Porcupine)
- Speaker playback

Core-side (new):

- FastAPI server
- Speech transcription via OpenAI (`/transcribe`)
- LLM response generation via OpenAI (`/command`)
- TTS generation as WAV (`/tts`)

## Project Structure

Console modules now live under `console/` with root-level compatibility shims still present.

- `console/app.py` - Flask app and routes (`/`, `/listen`, `/ask`)
- `console/record.py` - Audio capture and speech-endpoint logic
- `console/wake_listener.py` - Always-listening wake detection (Porcupine)
- `console/wakeword.py` - Wake-word transcript parsing/gating
- `console/speak.py` - Playback and fallback local TTS path
- `console/core_client.py` - Console HTTP client for Core endpoints
- `core/server.py` - FastAPI Core API server
- `core/services.py` - Core AI service implementations
- `shared/schemas.py` - Shared API request/response models
- `docs/distributed-architecture.md` - Refactor notes
- `app.py`, `record.py`, `wake_listener.py`, `wakeword.py`, `speak.py` - compatibility shims
- `templates/index.html` - Main UI template
- `static/css/jarvis.css` - UI styles
- `static/js/jarvis-ui.js` - UI behavior

## Requirements

## System packages (Pi)

- Python 3.10+ recommended
- `aplay` (usually from ALSA utilities)
- Piper binary built/installed (for primary TTS)
- `espeak` optional (fallback only)
- PortAudio runtime/dev packages are needed for `pvrecorder` on Pi

Piper is **not** installed by `pip`. You must install/build it separately on the Pi and point `PIPER_PATH` to the executable.

## Python packages

Install from your environment:

```bash
pip install -r requirements.txt
```

## Run

### 1) Start Core (Windows PC)

From project root:

```bash
uvicorn core.server:app --host 0.0.0.0 --port 8000
```

### 2) Start Console (Raspberry Pi)

From project root:

```bash
python app.py
```

Or run the package entrypoint:

```bash
python -m console
```

Then open `http://<pi-ip>:5000` (or your local host) in Chromium kiosk mode.

If Core is reachable, the console uses it automatically when `JARVIS_CORE_URL` is set. If not, it falls back to local processing.

## Environment Variables (Complete Reference)

This section lists all environment variables used for configuration across the project.

## Required

- `OPENAI_API_KEY`
  - Used by the OpenAI Python SDK in both `transcribe.py` and `brain.py`.
  - No default.

## Distributed mode (console -> core)

- `JARVIS_CORE_URL`
  - Example: `http://192.168.1.100:8000`
  - When set, console routes transcription/command/TTS to Core over HTTP.
- `JARVIS_DEVICE_ID`
  - Default: `pi-console`
  - Included with `/command` requests for device-aware orchestration.
- `JARVIS_DEVICE_LOCATION`
  - Default: `unknown`
  - Included with `/command` requests.
- `JARVIS_CORE_TIMEOUT_SECONDS`
  - Default: `20`
  - Request timeout for Core API calls.
- `JARVIS_TTS_MODE`
  - Default: `auto_fallback`
  - `auto_fallback` = try Core TTS then fallback local.
  - `core_only` = use Core TTS only (no local TTS fallback).
  - `local_only` = use Pi local TTS only (no Core TTS).

Core-specific optional model overrides:

- `JARVIS_COMMAND_MODEL` (default: `gpt-5.3`)
- `JARVIS_TRANSCRIBE_MODEL` (default: `gpt-4o-mini-transcribe`)
- `JARVIS_TTS_MODEL` (default: `gpt-4o-mini-tts`)
- `JARVIS_TTS_VOICE` (default: `alloy`)
- `JARVIS_TTS_INSTRUCTIONS` (default: `Speak in clear British English with a consistent, natural assistant tone.`)

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
  - `PvRecorder` path currently records at 16kHz; non-16k values are coerced to `16000`
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
- `VOICE_AUDIO_DEVICE_INDEX`
  - Default: `-1`
  - Device index used by `PvRecorder` for main speech capture (`-1` = default input)

## Wake word (wakeword.py)

- `WAKE_WORD_ENABLED`
  - Default: `true`
  - Enable/disable wake-word requirement on `/listen`
  - Accepted false values: `0`, `false`, `no`, `off`
- `WAKE_WORDS`
  - Default: `jarvis`
  - Comma-separated wake words (first entry is used in user-facing prompts)
  - Example: `jarvis,hey jarvis`

## Always-listening wake mode (wake_listener.py)

- `WAKE_ALWAYS_LISTEN_ENABLED`
  - Default: `false`
  - Enables background Porcupine wake-word listening as an alternative to push-to-talk
- `PORCUPINE_KEYWORDS`
  - Default: `jarvis`
  - Comma-separated built-in Porcupine keywords
  - Example: `jarvis,computer`
- `PORCUPINE_SENSITIVITY`
  - Default: `0.6`
  - Detection sensitivity (`0.0` to `1.0`)
- `WAKE_DETECTION_COOLDOWN`
  - Default: `1.5`
  - Cooldown in seconds between accepted detections
- `PORCUPINE_AUDIO_DEVICE_INDEX`
  - Default: unset
  - Optional numeric input device index for Porcupine `PvRecorder` stream
- `PICOVOICE_ACCESS_KEY`
  - Default: unset
  - Optional Picovoice access key (required on some Porcupine SDK versions)
  - Legacy fallback: `PORCUPINE_ACCESS_KEY` is still accepted
- `WAKE_RECORDER_RESTART_RETRIES`
  - Default: `8`
  - Number of attempts to restart wake recorder after handing mic back from main pipeline
- `WAKE_RECORDER_RESTART_DELAY`
  - Default: `0.15`
  - Delay in seconds between wake recorder restart attempts

## Suggested `.env` Example

```bash
# Required
OPENAI_API_KEY="sk-..."

# Distributed console mode
JARVIS_CORE_URL="http://192.168.1.100:8000"
JARVIS_DEVICE_ID="pi-console-1"
JARVIS_DEVICE_LOCATION="office"
JARVIS_CORE_TIMEOUT_SECONDS="20"
JARVIS_TTS_MODE="core_only"

# Core TTS style
JARVIS_TTS_VOICE="alloy"
JARVIS_TTS_INSTRUCTIONS="Speak in clear British English with a consistent, natural assistant tone."

# Piper TTS
PIPER_PATH="/home/robcowell/piper/build/piper"
# Use a British model path if you run local-only TTS.
PIPER_MODEL_PATH="/home/robcowell/piper/voices/en_GB-voice.onnx"
PIPER_SAMPLE_RATE="22050"
APLAY_PATH="aplay"
TTS_FALLBACK_TO_ESPEAK="0"
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
VOICE_AUDIO_DEVICE_INDEX="-1"

# Wake word
WAKE_WORD_ENABLED="1"
WAKE_WORDS="jarvis"

# Always-listening wake mode (Porcupine)
WAKE_ALWAYS_LISTEN_ENABLED="1"
PORCUPINE_KEYWORDS="jarvis"
PORCUPINE_SENSITIVITY="0.6"
WAKE_DETECTION_COOLDOWN="1.5"
# PORCUPINE_AUDIO_DEVICE_INDEX="1"
# PICOVOICE_ACCESS_KEY="YOUR_PICOVOICE_ACCESS_KEY"
WAKE_RECORDER_RESTART_RETRIES="8"
WAKE_RECORDER_RESTART_DELAY="0.15"
```

## Notes

- `/listen` performs full pipeline: record -> transcribe -> (optional wake-word gate) -> generate -> speak.
- `/ask` performs text-only pipeline: generate response (no TTS playback by default in current flow).
- UI is tuned for 800x480 kiosk operation and low-overhead rendering on Pi 3 B+.
- When `WAKE_ALWAYS_LISTEN_ENABLED=1`, a background Porcupine listener triggers the same voice pipeline hands-free.
