from flask import Flask, render_template, request, jsonify
import record
import transcribe
import brain
import speak

app = Flask(__name__)


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
        record.record_audio()
        text = transcribe.transcribe_audio()
        response = brain.ask_jarvis(text)
        speak.speak(response)

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
    app.run(host="0.0.0.0", port=5000, debug=True)
