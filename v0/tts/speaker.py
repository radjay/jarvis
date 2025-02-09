import os
import platform
import subprocess
from playsound import playsound
from sonos import play_on_sonos
from tts.elevenlabs_tts import synthesize_speech_elevenlabs
from utilities import logger
from config import BASE_DIR
import time

def cli_speak(text: str, speaker: str = None, filename: str = None):
    if filename is None:
        filename = synthesize_speech_elevenlabs(text)
    else:
        filename = synthesize_speech_elevenlabs(text, output_filename=filename)
    play_on_sonos(filename, room_name=speaker)
    logger.info(f"CLI speak: '{text}' on speaker: '{speaker}', saved to audio_cache/{filename}")
    return filename

def cli_speak_local(text: str, filename: str = None):
    if filename is None:
        filename = synthesize_speech_elevenlabs(text)
    else:
        filename = synthesize_speech_elevenlabs(text, output_filename=filename)
    audio_path = os.path.join(BASE_DIR, "audio_cache", filename)
    try:
        if os.path.exists(audio_path):
            if platform.system() == "Darwin":
                subprocess.call(["afplay", audio_path])
            else:
                playsound(audio_path)
        else:
            logger.error(f"Audio file not found: {audio_path}")
            print(f"Error: Audio file not found: {audio_path}")
    except Exception as e:
        logger.error(f"Failed to play audio: {e}")
        print(f"Error: Failed to play audio: {e}")
    logger.info(f"CLI speak local: '{text}', saved to audio_cache/{filename}")
    return filename
