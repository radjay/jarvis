import os
import uuid
import requests
from dotenv import load_dotenv
from config import BASE_DIR

load_dotenv()
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

def synthesize_speech_elevenlabs(text: str, output_filename=None):
    if not output_filename:
        output_filename = f"{uuid.uuid4()}.mp3"
        
    audio_dir = os.path.join(BASE_DIR, "audio_cache")
    os.makedirs(audio_dir, exist_ok=True)

    filepath = os.path.join(audio_dir, output_filename)

    url = "https://api.elevenlabs.io/v1/text-to-speech/ulWtRlgyOsbPRpjVAuGP"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "text": text,
        "voice_settings": {
            "stability": 0.3,
            "similarity_boost": 0.8
        }
    }
    print("Generating TTS with ElevenLabs...")
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        with open(filepath, "wb") as f:
            f.write(response.content)
        print("TTS audio saved to:", filepath)
        return output_filename
    else:
        raise Exception(f"ElevenLabs TTS failed with status code {response.status_code}: {response.text}")
