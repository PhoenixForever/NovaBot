
from dotenv import load_dotenv
from groq import Groq
import os

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

with open("test_voice.ogg", "rb") as audio_file:
    transcription = client.audio.transcriptions.create(
        file=("test_voice.ogg", audio_file.read()),
        model="whisper-large-v3-turbo",
        response_format="text"
    )

print("Transcription:", str(transcription))
