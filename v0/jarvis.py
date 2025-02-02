import os
import time
import wave
import requests
import openai
import pvporcupine
import pyaudio
from dotenv import load_dotenv
import uuid
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import argparse
import json

import soco
import netifaces
from tts import synthesize_speech_elevenlabs
from sonos import play_on_sonos
from playsound import playsound
from utilities import logger

# ========== CONFIGURATIONS ==========

# 1) Your keys (store securely in env variables or a vault)
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
DEFAULT_SONOS_SPEAKER_IP = os.getenv("SONOS_SPEAKER_IP")

porcupine_keyword_paths = ["jarvis_windows.ppn"]  # Example; depends on OS / custom training

CACHE_FILE = "sonos_cache.json"

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
    for _ in range(int(sample_rate / chunk_size * record_seconds)):
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

    with open(output_filename, "rb") as audio_file:
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

def chat_with_o3mini_jarvis(user_text: str) -> str:
    """
    Send user_text to the o3-mini API (using OpenAI API) and get a response styled in the voice of Jarvis.
    """
    system_prompt = (
        "You are Jarvis, a witty, calm, and helpful AI assistant with a dry British accent, "
        "inspired by the AI in the Iron Man movies. Your responses are clever, polite, and always concise."
    )
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    )
    return response.choices[0].message.content.strip()

def cli_speak(text: str, speaker: str = None):
    filename = synthesize_speech_elevenlabs(text)
    play_on_sonos(filename, room_name=speaker)
    logger.info(f"CLI speak: '{text}' on speaker: '{speaker}'")

def cli_speak_local(text: str):
    filename = synthesize_speech_elevenlabs(text)
    audio_dir = os.path.join(os.path.dirname(__file__), "audio_cache")
    filepath = os.path.join(audio_dir, filename)
    print("Playing audio through local speakers:", filepath)
    playsound(filepath)
    logger.info(f"CLI speak local: '{text}'")

def main():
    parser = argparse.ArgumentParser(description="Jarvis Assistant")
    subparsers = parser.add_subparsers(dest="mode")

    # CLI mode: speak
    speak_parser = subparsers.add_parser("speak", help="Make Jarvis speak a text")
    speak_parser.add_argument("text", type=str, help="Text for Jarvis to speak")
    speak_parser.add_argument("--speaker", type=str, help="Target speaker room name", default=None)
    speak_parser.add_argument("--local", action="store_true", help="Play through local audio system instead of Sonos")
    
    # CLI mode: ask
    ask_parser = subparsers.add_parser("ask", help="Ask Jarvis a question and get a witty response")
    ask_parser.add_argument("question", type=str, help="The question to ask Jarvis")
    ask_parser.add_argument("--speaker", type=str, help="Target speaker room name for TTS output", default=None)
    ask_parser.add_argument("--local", action="store_true", help="Play through local audio system instead of Sonos")

    args = parser.parse_args()

    if args.mode == "speak":
        if args.local:
            cli_speak_local(args.text)
        else:
            cli_speak(args.text, args.speaker)
    elif args.mode == "ask":
        response_text = chat_with_o3mini_jarvis(args.question)
        print("Jarvis:", response_text)
        logger.info(f"CLI ask: Question: '{args.question}' answered with: '{response_text}' on speaker: '{args.speaker}' (local: {args.local})")
        if args.local:
            cli_speak_local(response_text)
        else:
            cli_speak(response_text, args.speaker)
    else:
        try:
            test_text = "Hi Nalu, I am Jarvis... I am your new AI assistant."
            filename = synthesize_speech_elevenlabs(test_text)
            play_on_sonos(filename, room_name="Bedroom")
            logger.info(f"Default CLI speak: '{test_text}' on speaker: 'Bedroom'")
        except Exception as e:
            print(f"Error: {e}")
            logger.error(f"Error in default CLI speak: {e}")

if __name__ == "__main__":
    main()
