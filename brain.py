from openai import OpenAI

client = OpenAI()

def ask_jarvis(text):

    prompt = f"""
    You are Jarvis, a concise personal assistant.
    Respond clearly and helpfully.

    User request: {text}
    """

    response = client.responses.create(
        model="gpt-5.3",
        input=prompt
    )

    return response.output_text
