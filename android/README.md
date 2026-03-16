# J.A.R.V.I.S. Android Console (Java)

This folder contains a native Android client written in Java that connects to the existing J.A.R.V.I.S. Core API.

## Features

- Voice pipeline mirroring Pi console flow:
  - Record microphone audio with speech endpoint detection
  - `POST /transcribe` with WAV multipart upload
  - Optional transcript wake-word gating (`jarvis`)
  - `POST /command`
  - `POST /tts` and local WAV playback
- Local speech interrupt command handling (`stop`, `cancel`, `that's enough`)
- Stop button to interrupt active playback immediately
- GET `/health`
- GET `/version`
- Text-only command path (`POST /command`) with `text`, `device_id`, and `location`
- Console-style output log in-app

## Project layout

- `app/src/main/java/com/jarvis/androidconsole/VoiceRecorder.java`: speech endpointing recorder
- `app/src/main/java/com/jarvis/androidconsole/WavUtils.java`: WAV encode/decode helpers
- `app/src/main/java/com/jarvis/androidconsole/SpeechPlayer.java`: interruptible TTS playback
- `app/src/main/java/com/jarvis/androidconsole/WakeWordUtils.java`: wake-word and interrupt phrase logic
- `app/src/main/java/com/jarvis/androidconsole/AndroidConsoleConfig.java`: defaults matching Python console
- `app/src/main/java/com/jarvis/androidconsole/CoreClient.java`: HTTP client for Core endpoints
- `app/src/main/java/com/jarvis/androidconsole/MainActivity.java`: Android UI + request orchestration
- `app/src/main/res/layout/activity_main.xml`: Console-like screen

## Run in Android Studio

1. Open the `android/` folder as an Android Studio project.
2. Sync Gradle.
3. Start core from repo root:
   - `uvicorn core.server:app --host 0.0.0.0 --port 8000`
4. Run the app on:
   - Android Emulator: use `http://10.0.2.2:8000`
   - Physical device: use your host machine IP (for example `http://192.168.1.100:8000`)

## Notes

- `INTERNET` permission is enabled.
- `RECORD_AUDIO` permission is requested at runtime for voice capture.
- `usesCleartextTraffic=true` is enabled because local development commonly uses `http://`.
- Default timeout is 20 seconds, matching current console behavior.
