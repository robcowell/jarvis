import os

def speak(text):
    print(f"Jarvis says: {text}")
    os.system(f'espeak "{text}"')
