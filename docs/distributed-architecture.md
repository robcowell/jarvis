# J.A.R.V.I.S. Distributed Architecture (Phase 1)

## Components

- Console (Raspberry Pi): UI, wake-word detection, microphone capture, speaker playback.
- Core (Windows PC): API server, transcription, command reasoning, TTS generation.

## Current phase

Phase 1 introduced network boundaries without removing local fallback.

Phase 2 moves console runtime modules into `console/` while preserving root-level compatibility imports.

- Console calls Core HTTP endpoints when `JARVIS_CORE_URL` is configured.
- If Core is unavailable, console automatically falls back to local behavior.
- Core server is implemented with FastAPI.
- Console package entrypoint is available via `python -m console`.

## Core endpoints

- `GET /health`
- `POST /transcribe` (multipart/form-data with `file`)
- `POST /command` (json)
- `POST /tts` (json -> `audio/wav`)

## Console configuration

Set these on Raspberry Pi:

```bash
JARVIS_CORE_URL="http://192.168.1.100:8000"
JARVIS_DEVICE_ID="pi-console-1"
JARVIS_DEVICE_LOCATION="office"
JARVIS_CORE_TIMEOUT_SECONDS="20"
```
