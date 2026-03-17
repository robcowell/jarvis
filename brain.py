from openai import OpenAI

client = OpenAI()

def ask_jarvis(text):

    prompt = f"""
    You are Jarvis, a concise personal assistant, modelled on the fictional J.A.R.V.I.S. from the Iron Man series on movies.
    Respond clearly and helpfully, but with a British sense of humour, familiarity, and informality.

    User request: {text}
    """

    response = client.responses.create(
        model="gpt-5",
        input=prompt
    )

    return response.output_text
