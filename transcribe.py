from openai import OpenAI

client = OpenAI()

def transcribe_audio(filename="input.wav"):

    with open(filename, "rb") as audio_file:

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=audio_file
        )

    return transcript.text
