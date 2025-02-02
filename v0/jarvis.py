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
import numpy as np

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
    Record from the default microphone for record_seconds.
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

    # Combine frames and compute RMS and peak amplitude
    audio_data = b"".join(frames)
    samples = np.frombuffer(audio_data, dtype=np.int16)
    rms = np.sqrt(np.mean(samples**2))
    peak = np.max(np.abs(samples))
    print("Debug: RMS amplitude =", rms, "Peak amplitude =", peak)

    # Adjust thresholds as needed for your environment.
    rms_threshold = 20    # low but must be exceeded for voice
    peak_threshold = 500  # voice typically has higher peak values

    if rms < rms_threshold or peak < peak_threshold:
        print("Recording appears to be silent or just background noise. Skipping transcription.")
        return ""

    wf = wave.open(output_filename, 'wb')
    wf.setnchannels(channels)
    wf.setsampwidth(p.get_sample_size(audio_format))
    wf.setframerate(sample_rate)
    wf.writeframes(audio_data)
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

def voice_mode(device_index=None, use_sonos=False, speaker=None):
    try:
        keyword_paths = ["v0/Jarvis_en_mac_v3_0_0.ppn"]
        access_key = os.getenv("PORCUPINE_ACCESS_KEY")
        if not access_key:
            raise Exception("PORCUPINE_ACCESS_KEY not set in environment")
        porcupine = pvporcupine.create(access_key=access_key, keyword_paths=keyword_paths)
    except Exception as e:
        print("Error initializing Porcupine:", e)
        return

    pa = pyaudio.PyAudio()

    def open_stream():
        return pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length,
            input_device_index=device_index
        )

    try:
        stream = open_stream()
    except Exception as e:
        print("Error opening audio stream:", e)
        porcupine.delete()
        pa.terminate()
        return

    print("Voice mode activated. Say the hotword to interact with Jarvis...")
    session_id = "voice_session"  # persistent session for conversation context

    try:
        while True:
            # Poll available frames to avoid blocking on stream.read
            if stream.get_read_available() < porcupine.frame_length:
                time.sleep(0.05)
                continue

            try:
                pcm = stream.read(porcupine.frame_length, exception_on_overflow=False)
            except Exception as e:
                print("Error reading from stream:", e)
                continue

            pcm = np.frombuffer(pcm, dtype=np.int16)
            keyword_index = porcupine.process(pcm)
            if keyword_index >= 0:
                try:
                    playsound("./v0/assets/voice/yes.mp3")
                except Exception as play_err:
                    print("Error playing confirmation sound:", play_err)
                print("Hotword detected! Listening for your question...")
                try:
                    stream.stop_stream()
                    stream.close()
                    user_text = record_audio(record_seconds=5)
                except Exception as rec_e:
                    print("Error processing query audio:", rec_e)
                    user_text = ""
                try:
                    stream = open_stream()
                except Exception as stream_e:
                    print("Error reopening audio stream:", stream_e)
                    break

                if user_text.strip():
                    print("You said:", user_text)
                    answer = chat_with_jarvis_session(session_id, user_text)
                    print("Jarvis:", answer)
                    if use_sonos:
                        cli_speak(answer, speaker)
                    else:
                        cli_speak_local(answer)
                    while True:
                        print("Listening for follow-up question (5 seconds)... (remain silent to end conversation)")
                        followup = record_audio(record_seconds=5)
                        if followup.strip():
                            print("You said:", followup)
                            answer = chat_with_jarvis_session(session_id, followup)
                            print("Jarvis:", answer)
                            if use_sonos:
                                cli_speak(answer, speaker)
                            else:
                                cli_speak_local(answer)
                        else:
                            print("No follow-up detected. Returning to hotword mode...")
                            break
                else:
                    print("No speech detected.")
                print("Resuming hotword listening...")
                time.sleep(1)
    except KeyboardInterrupt:
        print("Voice mode terminating...")
    finally:
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        pa.terminate()
        porcupine.delete()

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
