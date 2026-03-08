from collections import deque
import os
from pathlib import Path
import re
import threading

from flask import Flask, render_template, request, jsonify
from console import core_client
from console import record
from console import speak
from console import wakeword
from console import wake_listener
import transcribe
import brain

BASE_DIR = Path(__file__).resolve().parent.parent
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)

_voice_lock = threading.Lock()
_event_lock = threading.Lock()
_event_id = 0
_events = deque(maxlen=80)
_wake_service = None
_wake_status = "Off"
_console_device_id = os.getenv("JARVIS_DEVICE_ID", "pi-console")
_console_location = os.getenv("JARVIS_DEVICE_LOCATION", "unknown")


def _parse_tts_mode(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized == "auto_fallback":
        print("[TTS] mode=auto_fallback is deprecated; forcing mode=core_only")
        return "core_only"
    if normalized in {"core_only", "local_only"}:
        return normalized
    return "core_only"


_tts_mode = _parse_tts_mode(os.getenv("JARVIS_TTS_MODE", "core_only"))
_LOCAL_INTERRUPT_PHRASES = {
    "stop",
    "cancel",
    "thats enough",
}


def _log_tts(path: str, **details) -> None:
    suffix = " ".join(f"{key}={value}" for key, value in details.items())
    if suffix:
        print(f"[TTS] path={path} {suffix}")
        return
    print(f"[TTS] path={path}")


def _normalize_phrase(text: str) -> str:
    lowered = (text or "").strip().lower().replace("'", "")
    cleaned = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def _is_local_interrupt_command(text: str) -> bool:
    normalized = _normalize_phrase(text)
    if not normalized:
        return False

    candidates = {normalized}
    # Accept phrases like "jarvis stop" in wake-listener transcripts.
    for word in wakeword.WAKE_WORDS:
        wake_normalized = _normalize_phrase(word)
        if not wake_normalized:
            continue
        prefix = f"{wake_normalized} "
        if normalized.startswith(prefix):
            candidates.add(normalized[len(prefix):].strip())

    for phrase in list(candidates):
        if phrase in _LOCAL_INTERRUPT_PHRASES:
            return True
        if phrase.startswith("stop ") or phrase.startswith("cancel "):
            return True
        if phrase.startswith("thats enough "):
            return True
    return False


def _emit_event(event_type, payload):
    global _event_id
    with _event_lock:
        _event_id += 1
        _events.append({
            "id": _event_id,
            "type": event_type,
            "payload": payload
        })


def _get_events_since(since_id):
    with _event_lock:
        return [event for event in _events if event["id"] > since_id]


def _set_wake_status(status, detail=""):
    global _wake_status
    _wake_status = status
    _emit_event("wake_status", {
        "status": status,
        "detail": detail
    })


def _voice_pipeline(source="touch", emit_events=False):
    if source == "wake_word" and speak.is_speaking():
        print("[SpeechInterrupt] wake-word-shortcut-triggered while speaking")
        stop_stats = speak.stop_speech()
        if emit_events:
            _emit_event("voice_state", {
                "state": "Idle",
                "subtext": "Speech interrupted",
                "source": source,
            })
        return {
            "ok": True,
            "response": "Stopping speech.",
            "processing": "local-interrupt",
            "interrupted": True,
            "stop": stop_stats,
        }

    if not _voice_lock.acquire(blocking=False):
        return {
            "ok": False,
            "busy": True,
            "error": "Voice pipeline is already running"
        }

    try:
        if emit_events:
            _emit_event("voice_state", {
                "state": "Listening...",
                "subtext": "Wake word detected. Recording request",
                "source": source
            })

        record.record_audio()

        if emit_events:
            _emit_event("voice_state", {
                "state": "Thinking...",
                "subtext": "Transcribing request",
                "source": source
            })

        using_core = core_client.is_enabled()
        if using_core:
            try:
                text = core_client.transcribe_audio_file("input.wav")
            except core_client.CoreUnavailableError as exc:
                print(f"Core transcribe failed ({exc}). Falling back to local transcribe.")
                _emit_event("core_status", {
                    "ok": False,
                    "error": str(exc),
                    "stage": "transcribe"
                })
                text = transcribe.transcribe_audio()
        else:
            text = transcribe.transcribe_audio()
        prompt_text = text

        # Skip transcript wake-word gating when wake mode already triggered by Porcupine.
        should_require_wake_word = wakeword.WAKE_WORD_ENABLED and source != "wake_word"
        if should_require_wake_word:
            if not wakeword.contains_wake_word(text):
                return {
                    "ok": False,
                    "wake_word_missing": True,
                    "text": text,
                    "error": f'Say "{wakeword.WAKE_WORD_DISPLAY}" to activate.'
                }

            prompt_text = wakeword.strip_wake_word(text)
            if not prompt_text:
                return {
                    "ok": False,
                    "wake_word_only": True,
                    "text": text,
                    "error": "Wake word heard. Say your command after it."
                }

        if _is_local_interrupt_command(prompt_text):
            print(f"[SpeechInterrupt] local-stop-triggered source={source} text='{prompt_text}'")
            stop_stats = speak.stop_speech()
            if emit_events:
                _emit_event("voice_state", {
                    "state": "Idle",
                    "subtext": "Speech interrupted",
                    "source": source,
                })
            return {
                "ok": True,
                "text": text,
                "prompt_text": prompt_text,
                "response": "Stopping speech.",
                "processing": "local-interrupt",
                "interrupted": True,
                "stop": stop_stats,
            }

        if using_core:
            try:
                response = core_client.command(
                    prompt_text,
                    device_id=_console_device_id,
                    location=_console_location
                )
            except core_client.CoreUnavailableError as exc:
                print(f"Core command failed ({exc}). Falling back to local brain.")
                _emit_event("core_status", {
                    "ok": False,
                    "error": str(exc),
                    "stage": "command"
                })
                response = brain.ask_jarvis(prompt_text)
        else:
            response = brain.ask_jarvis(prompt_text)

        if emit_events:
            _emit_event("voice_state", {
                "state": "Speaking...",
                "subtext": "Response ready",
                "source": source
            })

        if _tts_mode == "local_only":
            _log_tts("local-piper", mode=_tts_mode, chars=len(response))
            speak.speak(response)
        else:
            if not using_core:
                _log_tts("none", mode=_tts_mode, error="core_not_configured")
                return {
                    "ok": False,
                    "text": text,
                    "prompt_text": prompt_text,
                    "response": response,
                    "error": "JARVIS_TTS_MODE=core_only but JARVIS_CORE_URL is not configured"
                }
            try:
                _log_tts("core", mode=_tts_mode, chars=len(response))
                wav = core_client.tts(response)
                speak.play_wav_bytes(wav)
            except core_client.CoreUnavailableError as exc:
                _emit_event("core_status", {
                    "ok": False,
                    "error": str(exc),
                    "stage": "tts"
                })
                _log_tts("core", mode=_tts_mode, error="unavailable", fallback_used="none")
                return {
                    "ok": False,
                    "text": text,
                    "prompt_text": prompt_text,
                    "response": response,
                    "error": f"Core TTS unavailable in core_only mode: {exc}"
                }
        return {
            "ok": True,
            "text": text,
            "prompt_text": prompt_text,
            "response": response,
            "processing": "core" if using_core else "local",
            "tts_mode": _tts_mode
        }
    finally:
        _voice_lock.release()


def _start_wake_listener():
    global _wake_service

    if not wake_listener.WAKE_ALWAYS_LISTEN_ENABLED:
        _set_wake_status("Off", "Always-listening wake mode disabled")
        return

    if _wake_service is not None:
        return

    def on_detect(keyword):
        try:
            _emit_event("wake_detected", {
                "keyword": keyword
            })
            result = _voice_pipeline(source="wake_word", emit_events=True)
            _emit_event("voice_result", {
                **result,
                "source": "wake_word"
            })
        except Exception as exc:
            _emit_event("voice_result", {
                "ok": False,
                "source": "wake_word",
                "error": str(exc)
            })

    def on_error(message):
        _set_wake_status("Error", message)
        _emit_event("voice_result", {
            "ok": False,
            "source": "wake_word",
            "error": message
        })

    _wake_service = wake_listener.PorcupineWakeListener(on_detect=on_detect, on_error=on_error)
    _wake_service.start()
    _set_wake_status("Armed", "Listening for wake word")


@app.route("/")
def home():
    audio_available = record.has_input_device()
    input_devices = record.get_input_devices()
    return render_template(
        "index.html",
        audio_available=audio_available,
        input_devices=input_devices
    )


@app.route("/listen")
def listen():
    try:
        return jsonify(_voice_pipeline(source="touch", emit_events=False)), 200
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 200


@app.route("/events")
def events():
    since = request.args.get("since", "0").strip()
    try:
        since_id = int(since)
    except ValueError:
        since_id = 0
    return jsonify({
        "ok": True,
        "events": _get_events_since(since_id)
    }), 200


@app.route("/ask", methods=["POST"])
def ask():
    try:
        text = request.form.get("text", "").strip()

        if not text:
            return jsonify({
                "ok": False,
                "error": "No text provided"
            })

        if core_client.is_enabled():
            try:
                response = core_client.command(
                    text,
                    device_id=_console_device_id,
                    location=_console_location
                )
            except core_client.CoreUnavailableError as exc:
                print(f"Core command failed ({exc}). Falling back to local brain.")
                response = brain.ask_jarvis(text)
        else:
            response = brain.ask_jarvis(text)

        return jsonify({
            "ok": True,
            "text": text,
            "response": response
        })
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 200


def main() -> None:
    debug_mode = True
    if (not debug_mode) or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        _start_wake_listener()
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)


if __name__ == "__main__":
    main()
