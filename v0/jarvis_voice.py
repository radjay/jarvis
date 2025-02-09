import os
import time
import traceback
import pyaudio
import pvporcupine
from playsound import playsound
from tts.speaker import cli_speak_local, cli_speak
from llm.chat import chat_with_jarvis_session, chat_with_jarvis_function_call
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
from config import BASE_DIR
import platform
import subprocess
import socket
import scipy.signal
from collections import deque

load_dotenv()

def voice_mode(use_sonos=False, speaker=None, device_index=None, stream_addr=None):
    """
    Unified voice mode.
    • If stream_addr is provided (format "ip:port"), then network (stream) mode is used.
    • Otherwise the local microphone is used.
    """
    # Initialize Porcupine
    keyword_file = "v0/Jarvis_en_mac_v3_0_0.ppn"
    print(f"Keyword file exists: {os.path.exists(keyword_file)}")
    keyword_paths = [keyword_file]
    access_key = os.getenv("PORCUPINE_ACCESS_KEY")
    if not access_key:
        print("PORCUPINE_ACCESS_KEY not set")
        return
    try:
        porcupine = pvporcupine.create(access_key=access_key, keyword_paths=keyword_paths)
    except Exception as e:
        print("Error initializing Porcupine:", e)
        return

    # Determine mode: "stream" vs "mic"
    if stream_addr:
        mode = "stream"
        publisher_rate = 44100  # stream audio is assumed to be at 44100 Hz
        record_rate = publisher_rate
        # For hotword detection, calculate the number of samples to read so that after downsampling we obtain porcupine.frame_length samples.
        num_samples_needed = int(round(porcupine.frame_length * (publisher_rate / porcupine.sample_rate)))
        hotword_frame_bytes = num_samples_needed * 2  # 2 bytes per 16-bit sample
        # Connect to the stream server and indicate subscriber role.
        ip, port_str = stream_addr.split(":")
        port = int(port_str)
        audio_source = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            audio_source.connect((ip, port))
            audio_source.sendall(b"SUB")
        except Exception as e:
            print("Failed to connect to stream server:", e)
            porcupine.delete()
            return
        is_socket = True
    else:
        mode = "mic"
        record_rate = porcupine.sample_rate
        hotword_frame_bytes = porcupine.frame_length * 2
        pa = pyaudio.PyAudio()
        try:
            audio_source = pa.open(
                rate=porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=porcupine.frame_length,
                input_device_index=device_index
            )
        except Exception as e:
            print("Error opening audio stream:", e)
            porcupine.delete()
            pa.terminate()
            return
        is_socket = False

    # Helper to read an exact number of bytes from the audio source.
    def read_exact(source, n):
        data = b""
        while len(data) < n:
            if is_socket:
                chunk = source.recv(n - len(data))
            else:
                chunk = source.read(n - len(data))
            if not chunk:
                break
            data += chunk
        return data

    # Generic conversation recording; operates on the same source, using smart silence detection.
    def record_conversation_generic(max_duration=30, silence_duration=1.0, silence_threshold=20, silence_ratio=0.4, min_input_duration=0.5):
        if mode == "mic":
            try:
                rec_stream = pa.open(
                    rate=record_rate,
                    channels=1,
                    format=pyaudio.paInt16,
                    input=True,
                    frames_per_buffer=porcupine.frame_length,
                    input_device_index=device_index
                )
            except Exception as e:
                print("Error opening recording stream:", e)
                return ""
        else:
            # In stream mode we keep using the socket.
            rec_stream = None

        print("Recording conversation...")
        frames = []
        start_time = time.time()
        frame_interval = porcupine.frame_length / porcupine.sample_rate
        conv_samples = int(round(porcupine.frame_length * (record_rate / porcupine.sample_rate)))
        conv_frame_bytes = conv_samples * 2

        if mode == "stream":
            adjusted_threshold = silence_threshold * (record_rate / porcupine.sample_rate)
        else:
            adjusted_threshold = silence_threshold

        speech_started = False
        speech_start_time = None
        max_amp = 0.0
        window_size = int(silence_duration / frame_interval) or 1
        rms_window = deque(maxlen=window_size)

        while True:
            if time.time() - start_time > max_duration:
                print("Reached maximum recording duration.")
                break
            if mode == "mic":
                try:
                    data = rec_stream.read(porcupine.frame_length, exception_on_overflow=False)
                except Exception as e:
                    print("Error during conversation recording:", e)
                    break
            else:
                data = read_exact(audio_source, conv_frame_bytes)
                if len(data) != conv_frame_bytes:
                    print("Incomplete conversation frame, ending recording.")
                    break
            frames.append(data)
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            current_rms = np.sqrt(np.mean(samples ** 2)) if samples.size > 0 else 0.0

            if not speech_started and current_rms >= adjusted_threshold:
                speech_started = True
                speech_start_time = time.time()
                max_amp = current_rms

            if speech_started:
                max_amp = max(max_amp, current_rms)
                if time.time() - speech_start_time >= min_input_duration:
                    rms_window.append(current_rms)
                    if len(rms_window) == window_size:
                        if np.mean(rms_window) < max_amp * silence_ratio:
                            print("Silence detected. Ending recording.")
                            break

        if mode == "mic":
            rec_stream.stop_stream()
            rec_stream.close()
        print("Finished conversation recording.")
        audio_data = b"".join(frames)
        tmp_filename = "conversation.wav"
        wf = wave.open(tmp_filename, 'wb')
        wf.setnchannels(1)
        if mode == "mic":
            wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
        else:
            wf.setsampwidth(2)
        wf.setframerate(record_rate)
        wf.writeframes(audio_data)
        wf.close()
        try:
            print("Transcribing conversation audio via OpenAI Whisper API...")
            with open(tmp_filename, "rb") as audio_file:
                transcript = openai.Audio.transcribe("whisper-1", audio_file)
            os.remove(tmp_filename)
            return transcript.get("text", "")
        except Exception as e:
            print("Transcription error:", e)
            os.remove(tmp_filename)
            return ""

    # Add a helper to flush residual microphone input.
    def flush_mic(duration=1.0):
        try:
            flush_stream = pa.open(
                rate=porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=porcupine.frame_length,
                input_device_index=device_index
            )
            end_time = time.time() + duration
            # Read and discard audio for 'duration' seconds.
            while time.time() < end_time:
                flush_stream.read(porcupine.frame_length, exception_on_overflow=False)
            flush_stream.stop_stream()
            flush_stream.close()
        except Exception as e:
            print("Error flushing microphone:", e)

    # Add this helper near flush_mic (e.g. just before the "Voice mode activated" print)
    def remove_echo(transcript, last_tts):
        if not last_tts:
            return transcript
        # Attempt to remove fragments of the prior TTS reply from the transcript.
        for part in last_tts.split(". "):
            part = part.strip()
            if len(part) > 5 and part in transcript:
                transcript = transcript.replace(part, "")
        return transcript.strip()

    def flush_until_silence(silence_threshold=20, silence_required=1.0, max_flush=5.0):
        try:
            flush_stream = pa.open(
                rate=porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=porcupine.frame_length,
                input_device_index=device_index
            )
            start_time = time.time()
            silent_time = 0.0
            while time.time() - start_time < max_flush:
                data = flush_stream.read(porcupine.frame_length, exception_on_overflow=False)
                samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                current_rms = np.sqrt(np.mean(samples ** 2)) if samples.size > 0 else 0.0
                if current_rms < silence_threshold:
                    silent_time += porcupine.frame_length / porcupine.sample_rate
                    if silent_time >= silence_required:
                        break
                else:
                    silent_time = 0.0
            flush_stream.stop_stream()
            flush_stream.close()
        except Exception as e:
            print("Error flushing microphone until silence:", e)

    def flush_stream_socket(duration=2.0):
        try:
            # For stream mode, read and discard data from the socket for a fixed duration.
            orig_timeout = audio_source.gettimeout() if hasattr(audio_source, "gettimeout") else None
            audio_source.settimeout(0.1)
            end_time = time.time() + duration
            while time.time() < end_time:
                try:
                    _ = audio_source.recv(1024)
                except socket.timeout:
                    continue
                except Exception as e:
                    print("Error flushing stream socket:", e)
                    break
            if orig_timeout is not None:
                audio_source.settimeout(orig_timeout)
            else:
                audio_source.settimeout(None)
        except Exception as e:
            print("Error flushing stream socket:", e)

    def is_echo(user_text, reference_text, threshold=0.8):
        # Simple heuristic: if most words in user_text appear in reference_text.
        user_words = set(user_text.lower().split())
        ref_words = set(reference_text.lower().split())
        if not user_words:
            return False
        common = user_words.intersection(ref_words)
        ratio = len(common) / len(user_words)
        return ratio >= threshold

    print(f"Voice mode activated ({mode} mode). Say the hotword to interact with Jarvis...")
    executor = ThreadPoolExecutor()
    session_id = "voice_session"
    last_tts = ""

    try:
        while True:
            # For hotword detection, read a full frame.
            if mode == "mic":
                try:
                    pcm_data = audio_source.read(porcupine.frame_length, exception_on_overflow=False)
                except Exception as e:
                    print("Error reading from microphone:", e)
                    continue
                pcm = np.frombuffer(pcm_data, dtype=np.int16)
            else:
                data = read_exact(audio_source, hotword_frame_bytes)
                if len(data) != hotword_frame_bytes:
                    print("Incomplete frame received, reconnecting...")
                    try:
                        audio_source.close()
                    except Exception:
                        pass
                    try:
                        audio_source = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        ip, port_str = stream_addr.split(":")
                        port = int(port_str)
                        audio_source.connect((ip, port))
                        audio_source.sendall(b"SUB")
                    except Exception as e:
                        print("Reconnection failed:", e)
                        break
                    continue
                raw_pcm = np.frombuffer(data, dtype=np.int16)
                # Downsample from publisher_rate to porcupine.sample_rate.
                pcm = scipy.signal.resample(raw_pcm, porcupine.frame_length).astype(np.int16)
            keyword_index = porcupine.process(pcm)
            if keyword_index >= 0:
                try:
                    assets = ["welcome-back.mp3", "goodday.mp3", "greetings.mp3", "listening.mp3", "right-here.mp3", "yes-sir.mp3"]
                    activation_texts = {
                        "welcome-back.mp3": "Welcome back, sir.",
                        "goodday.mp3": "Good day, sir.",
                        "greetings.mp3": "Greetings, sir.",
                        "listening.mp3": "Listening, sir.",
                        "right-here.mp3": "Right here, sir.",
                        "yes-sir.mp3": "Yes, sir."
                    }
                    selected_asset = random.choice(assets)
                    last_activation_text = activation_texts.get(selected_asset, "")
                    if speaker:
                        import shutil
                        from sonos import play_on_sonos
                        assets_dir = os.path.join(BASE_DIR, "v0", "assets", "voice", "activate")
                        audio_cache_dir = os.path.join(BASE_DIR, "audio_cache")
                        os.makedirs(audio_cache_dir, exist_ok=True)
                        asset_path = os.path.join(assets_dir, selected_asset)
                        cache_path = os.path.join(audio_cache_dir, selected_asset)
                        if not os.path.exists(cache_path):
                            shutil.copy(asset_path, cache_path)
                        play_on_sonos(selected_asset, room_name=speaker)
                    else:
                        sound_filepath = os.path.join(BASE_DIR, "v0", "assets", "voice", "activate", selected_asset)
                        if platform.system() == "Darwin":
                            subprocess.call(["afplay", sound_filepath])
                        else:
                            playsound(sound_filepath)
                except Exception as play_err:
                    print("Error playing confirmation sound:", play_err)
                print("Hotword detected! Listening for your questions...")
                if mode == "mic":
                    audio_source.stop_stream()
                    audio_source.close()
                interaction_count = 0
                while interaction_count < 10:
                    if mode == "mic":
                        flush_until_silence(silence_threshold=20, silence_required=0.5, max_flush=2.0)
                    else:
                        flush_stream_socket(duration=1.0)
                    user_text = record_conversation_generic(
                        max_duration=30,
                        silence_duration=1.0,
                        silence_threshold=20,
                        silence_ratio=0.4,
                        min_input_duration=0.5
                    )
                    user_text = remove_echo(user_text, last_tts)
                    # Ignore if the recording exactly matches the activation phrase.
                    if last_activation_text and user_text.strip().lower() == last_activation_text.lower():
                        print("Detected activation phrase, ignoring input.")
                        break
                    # Also ignore if the input echoes the assistant's prior reply.
                    if last_tts and is_echo(user_text, last_tts):
                        print("Detected echo of assistant output, ignoring input.")
                        break
                    if len(''.join(filter(str.isalnum, user_text))) < 3:
                        print("Insufficient speech detected, ending conversation mode.")
                        break
                    print("You said:", user_text)
                    future = executor.submit(chat_with_jarvis_function_call, session_id, user_text)
                    try:
                        answer = future.result(timeout=30)
                    except Exception as process_err:
                        print("Error processing query:", process_err)
                        answer = "Sorry, an error occurred processing your request."
                    print("Jarvis:", answer)
                    last_tts = answer
                    if use_sonos:
                        cli_speak(answer, speaker)
                    else:
                        cli_speak_local(answer)
                    interaction_count += 1
                if mode == "mic":
                    try:
                        audio_source = pa.open(
                            rate=porcupine.sample_rate,
                            channels=1,
                            format=pyaudio.paInt16,
                            input=True,
                            frames_per_buffer=porcupine.frame_length,
                            input_device_index=device_index
                        )
                    except Exception as stream_e:
                        print("Error reopening audio stream:", stream_e)
                        break
                print("Resuming hotword listening...")
    except KeyboardInterrupt:
        print("Voice mode terminating...")
    finally:
        try:
            if mode == "mic":
                audio_source.stop_stream()
                audio_source.close()
                pa.terminate()
        except Exception:
            pass
        porcupine.delete()
        executor.shutdown(wait=False)
        if mode == "stream":
            try:
                audio_source.close()
            except Exception:
                pass

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
                audio_dir = os.path.join(BASE_DIR, "audio_cache")
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
    parser.add_argument("--stream", type=str, default=None, help="Address of audio stream server (format ip:port)")
    args = parser.parse_args()

    use_sonos = args.sonos or bool(args.speaker)
    if args.stream:
        ip, port_str = args.stream.split(":")
        port = int(port_str)
        from jarvis_voice import voice_mode
        voice_mode(use_sonos=use_sonos, speaker=args.speaker, stream_addr=f"{ip}:{port}")
    else:
        from jarvis_voice import voice_mode
        voice_mode(use_sonos=use_sonos, speaker=args.speaker)
