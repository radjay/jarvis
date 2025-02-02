import os
import time
import traceback
import pyaudio
import pvporcupine
from playsound import playsound
from jarvis import cli_speak_local, cli_speak
from llm.chat import chat_with_jarvis_session
from dotenv import load_dotenv
import numpy as np
import argparse
import random
import openai
import wave
import threading
from concurrent.futures import ThreadPoolExecutor
import uuid
import aiohttp
import asyncio

load_dotenv()

# New helper to process the query asynchronously.
def process_user_query(session_id, user_text, use_sonos, speaker):
    # Get response from chat_api
    answer = chat_with_jarvis_session(session_id, user_text)
    # Immediately initiate TTS conversion.
    tts_filename = synthesize_speech_elevenlabs(answer)
    # Return both the answer and the TTS filename.
    return answer, tts_filename

def play_processing_sound():
    # Pre-generated sound file indicating processing (e.g. "Hold on, please…")
    try:
        playsound("v0/assets/voice/processing.mp3")
    except Exception as e:
        print("Error playing processing sound:", e)

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

    # Record conversation using the same PyAudio instance.
    def record_conversation(record_seconds=5):
        stream_conv = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length,
            input_device_index=device_index
        )
        print("Recording conversation...")
        frames = []
        num_chunks = int(porcupine.sample_rate / porcupine.frame_length * record_seconds)
        for _ in range(num_chunks):
            try:
                data = stream_conv.read(porcupine.frame_length, exception_on_overflow=False)
            except Exception as e:
                print("Error during conversation recording:", e)
                break
            frames.append(data)
        stream_conv.stop_stream()
        stream_conv.close()
        print("Finished conversation recording.")
        audio_data = b"".join(frames)
        samples = np.frombuffer(audio_data, dtype=np.int16)
        rms = np.sqrt(np.mean(samples**2)) if samples.size > 0 else 0
        peak = np.max(np.abs(samples)) if samples.size > 0 else 0
        print("Debug: Conversation RMS amplitude =", rms, "Peak amplitude =", peak)
        if rms < 20 or peak < 500:
            print("Recording appears to be silent or just background noise. Skipping transcription.")
            return ""
        tmp_filename = "conversation.wav"
        wf = wave.open(tmp_filename, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
        wf.setframerate(porcupine.sample_rate)
        wf.writeframes(audio_data)
        wf.close()
        try:
            print("Transcribing conversation audio via OpenAI Whisper API...")
            with open(tmp_filename, "rb") as audio_file:
                transcript = openai.Audio.transcribe("whisper-1", audio_file)
            os.remove(tmp_filename)
            return transcript["text"]
        except Exception as e:
            print("Transcription error:", e)
            os.remove(tmp_filename)
            return ""

    try:
        stream = open_stream()
    except Exception as e:
        print("Error opening audio stream:", e)
        porcupine.delete()
        pa.terminate()
        return

    print("Voice mode activated. Say the hotword to interact with Jarvis...")
    executor = ThreadPoolExecutor()
    session_id = "voice_session"  # persistent conversation context

    try:
        while True:
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
                    assets = ["yes.mp3", "eh-huh.mp3", "yes-sir.mp3", "hi-there.mp3"]
                    selected_asset = random.choice(assets)
                    playsound("v0/assets/voice/" + selected_asset)
                except Exception as play_err:
                    print("Error playing confirmation sound:", play_err)
                print("Hotword detected! Listening for your question...")
                try:
                    stream.stop_stream()
                    stream.close()
                    user_text = record_conversation(record_seconds=5)
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
                    # Offload the chat API call into a background thread
                    future = executor.submit(chat_with_jarvis_session, session_id, user_text)
                    try:
                        answer = future.result(timeout=30)
                    except Exception as e:
                        print("Error during processing:", e)
                        answer = "Sorry, an error occurred processing your request."
                    print("Jarvis:", answer)
                    if use_sonos:
                        cli_speak(answer, speaker)
                    else:
                        cli_speak_local(answer)
                    followup_attempts = 0
                    while followup_attempts < 10:
                        print(f"Listening for follow-up question (5 seconds)... (attempt {followup_attempts+1} of 10)")
                        followup = record_conversation(record_seconds=5)
                        if followup.strip():
                            followup_attempts = 0
                            print("You said:", followup)
                            future = executor.submit(chat_with_jarvis_session, session_id, followup)
                            try:
                                answer = future.result(timeout=30)
                            except Exception as e:
                                print("Error during processing follow-up:", e)
                                answer = "Sorry, something went wrong."
                            print("Jarvis:", answer)
                            if use_sonos:
                                cli_speak(answer, speaker)
                            else:
                                cli_speak_local(answer)
                        else:
                            followup_attempts += 1
                    print("No further follow-up detected. Returning to hotword mode...")
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
        executor.shutdown(wait=False)

async def transcribe(audio_filepath: str) -> str:
    # Read audio file (assuming Whisper API supports async calls)
    with open(audio_filepath, "rb") as f:
        audio_data = f.read()
    endpoint = "https://api.openai.com/v1/audio/transcribe"
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
    }
    async with aiohttp.ClientSession() as session:
        # You might need to adjust how the file is sent (multipart/form-data, etc.)
        data = {"file": audio_data, "model": "whisper-1"}
        async with session.post(endpoint, headers=headers, data=data) as resp:
            result = await resp.json()
            return result.get("text", "")

async def query_llm(user_text: str) -> str:
    endpoint = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
        "Content-Type": "application/json"
    }
    json_data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": ("You are Jarvis, a witty, calm, and helpful AI assistant. "
                                            "Respond in one or two concise sentences.")},
            {"role": "user", "content": user_text}
        ]
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(endpoint, json=json_data, headers=headers) as resp:
            result = await resp.json()
            return result['choices'][0]['message']['content'].strip()

async def synthesize_tts(text: str) -> str:
    endpoint = "https://api.elevenlabs.io/v1/text-to-speech/ulWtRlgyOsbPRpjVAuGP"
    headers = {
        "xi-api-key": os.getenv("ELEVENLABS_API_KEY"),
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "voice_settings": {
            "stability": 0.3,
            "similarity_boost": 0.8
        }
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(endpoint, json=payload, headers=headers) as resp:
            if resp.status == 200:
                audio_content = await resp.read()
                filename = f"{uuid.uuid4()}.mp3"
                audio_dir = os.path.join("audio_cache")
                os.makedirs(audio_dir, exist_ok=True)
                filepath = os.path.join(audio_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(audio_content)
                return filename
            else:
                raise Exception(f"TTS failed with status code {resp.status}")

async def process_pipeline(audio_filepath: str):
    transcribed_text = await transcribe(audio_filepath)
    response_text = await query_llm(transcribed_text)
    audio_filename = await synthesize_tts(response_text)
    return response_text, audio_filename

async def main():
    audio_filepath = "input.wav"  # Replace with your recorded file
    response_text, tts_file = await process_pipeline(audio_filepath)
    print("Response text:", response_text)
    print("Generated TTS file:", tts_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jarvis Voice Mode")
    parser.add_argument("--sonos", action="store_true", help="Output audio on Sonos speaker instead of local speakers")
    parser.add_argument("--speaker", type=str, default=None, help="Target Sonos speaker room name")
    args = parser.parse_args()

    voice_mode(use_sonos=args.sonos, speaker=args.speaker)
