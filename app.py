from collections import deque
import os
import threading

from flask import Flask, render_template, request, jsonify
import record
import transcribe
import brain
import speak
import wakeword
import wake_listener

app = Flask(__name__)

_voice_lock = threading.Lock()
_event_lock = threading.Lock()
_event_id = 0
_events = deque(maxlen=80)
_wake_service = None


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


def _voice_pipeline(source="touch", emit_events=False):
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

        response = brain.ask_jarvis(prompt_text)

        if emit_events:
            _emit_event("voice_state", {
                "state": "Speaking...",
                "subtext": "Response ready",
                "source": source
            })

        speak.speak(response)
        return {
            "ok": True,
            "text": text,
            "prompt_text": prompt_text,
            "response": response
        }
    finally:
        _voice_lock.release()


def _start_wake_listener():
    global _wake_service

    if not wake_listener.WAKE_ALWAYS_LISTEN_ENABLED:
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
        _emit_event("voice_result", {
            "ok": False,
            "source": "wake_word",
            "error": message
        })

    _wake_service = wake_listener.PorcupineWakeListener(on_detect=on_detect, on_error=on_error)
    _wake_service.start()


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


if __name__ == "__main__":
    debug_mode = True
    if (not debug_mode) or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        _start_wake_listener()
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
