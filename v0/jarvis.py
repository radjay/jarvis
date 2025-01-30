import os
import time
import wave
import requests
import openai
import pvporcupine
import pyaudio

import soco
from http_server import audio_server

# ========== CONFIGURATIONS ==========

# 1) Your keys (store securely in env variables or a vault)
openai.api_key = os.environ.get("OPENAI_API_KEY", "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")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "sk_08d27e17b5a3ce7e0afacc7efecc73f9f5e5a14b384edc96")

# 2) Sonos Speaker IP or Name
SONOS_SPEAKER_IP = "192.168.50.19"  # IP of your Sonos Arc
# Alternatively, if you know the speaker by name, you can discover with SoCo.discovery

# 3) Porcupine configuration (hotword model for "Hey Jarvis")
# Download or train a custom Porcupine wake word for "Hey Jarvis".
# For demonstration, we'll reference a built-in keyword, but you'd need a custom model for the exact phrase "Hey Jarvis".
porcupine_keyword_paths = ["jarvis_windows.ppn"]  # Example; depends on OS / custom training

# ========== HELPER FUNCTIONS ==========

def record_audio(output_filename="input.wav", record_seconds=5, sample_rate=16000, channels=1):
    """
    Record from the default microphone for record_seconds or until you stop.
    """
    audio_format = pyaudio.paInt16
    chunk_size = 1024

    p = pyaudio.PyAudio()
    stream = p.open(format=audio_format,
                    channels=channels,
                    rate=sample_rate,
                    input=True,
                    frames_per_buffer=chunk_size)

    print("Recording...")
    frames = []
    for i in range(0, int(sample_rate / chunk_size * record_seconds)):
        data = stream.read(chunk_size)
        frames.append(data)

    print("Finished recording.")

    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open(output_filename, 'wb')
    wf.setnchannels(channels)
    wf.setsampwidth(p.get_sample_size(audio_format))
    wf.setframerate(sample_rate)
    wf.writeframes(b''.join(frames))
    wf.close()

def transcribe_audio_with_whisper(audio_file_path: str) -> str:
    """
    Use OpenAI Whisper API to transcribe the audio.
    Alternatively, you could run whisper.cpp locally.
    """
    audio_file = open(audio_file_path, "rb")
    print("Transcribing audio via OpenAI Whisper API...")
    transcript = openai.Audio.transcribe("whisper-1", audio_file)
    return transcript["text"]

def chat_with_gpt(user_text: str) -> str:
    """
    Send user_text to OpenAI ChatGPT (gpt-3.5-turbo or gpt-4) and get a response.
    """
    print("Sending text to ChatGPT:", user_text)
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful home assistant named Jarvis."},
            {"role": "user", "content": user_text},
        ]
    )
    reply = response['choices'][0]['message']['content']
    return reply.strip()

def synthesize_speech_elevenlabs(text: str, output_filename="response.mp3", voice_id="IKne3meq5aSn9XLyUdCD"):
    """Use ElevenLabs TTS to generate an audio file."""
    import uuid
    
    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join(audio_server.audio_dir, filename)
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
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
        return filename
    else:
        raise Exception(f"ElevenLabs TTS failed with status code {response.status_code}: {response.text}")

def play_on_sonos(audio_file_path: str, room_name: str = None):
    """Play an audio file on Sonos speaker"""
    sonos_url = audio_server.get_url_for_file(audio_file_path)
    print(f"Serving audio at: {sonos_url}")
    
    try:
        if room_name:
            print("Discovering Sonos speakers...")
            speakers = list(soco.discover())
            print(f"Found speakers: {[s.player_name for s in speakers]}")
            speaker = next((s for s in speakers if s.player_name == room_name), None)
            if not speaker:
                raise ValueError(f"No Sonos speaker found with room name: {room_name}")
        else:
            speaker = soco.SoCo(SONOS_SPEAKER_IP)
        
        print(f"Selected speaker: {speaker.player_name} ({speaker.ip_address})")
        
        # Test URL accessibility
        test_response = requests.get(sonos_url)
        print(f"URL test status: {test_response.status_code}")
        if test_response.status_code != 200:
            raise Exception(f"Audio URL not accessible: {sonos_url}")

        was_playing = (speaker.get_current_transport_info()['current_transport_state'] == 'PLAYING')
        print(f"Speaker was playing: {was_playing}")

        if was_playing:
            speaker.pause()

        print(f"Sending TTS to Sonos {speaker.player_name}")
        speaker.play_uri(sonos_url, title="Jarvis TTS")
        
        time.sleep(10)
        
        if was_playing:
            speaker.play()
    except Exception as e:
        print(f"Error playing on Sonos: {e}")
        raise

# ========== MAIN LOOP ==========

def main():
    test_text = "Hi Zoey, I am Jarvis... I am your new AI assistant."
    filename = synthesize_speech_elevenlabs(test_text)
    play_on_sonos(filename, room_name="Living Room")

if __name__ == "__main__":
    main()
