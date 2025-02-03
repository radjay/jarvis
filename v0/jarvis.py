#!/usr/bin/env python3

import argparse
import os
from dotenv import load_dotenv
from llm.chat import chat_with_jarvis_session, chat_with_jarvis_function_call
from tts.elevenlabs_tts import synthesize_speech_elevenlabs
from sonos import play_on_sonos
from playsound import playsound
from utilities import logger

load_dotenv()

BASE_DIR = os.path.dirname(os.path.realpath(__file__))

def cli_speak(text: str, speaker: str = None, filename: str = None):
    if filename is None:
        filename = synthesize_speech_elevenlabs(text)
    else:
        filename = synthesize_speech_elevenlabs(text, output_filename=filename)
    play_on_sonos(filename, room_name=speaker)
    logger.info(f"CLI speak: '{text}' on speaker: '{speaker}', saved to audio_cache/{filename}")

def cli_speak_local(text: str, filename: str = None):
    if filename is None:
        filename = synthesize_speech_elevenlabs(text)
    else:
        filename = synthesize_speech_elevenlabs(text, output_filename=filename)
    audio_path = os.path.join(BASE_DIR, "audio_cache", filename)
    try:
        if os.path.exists(audio_path):
            playsound(audio_path)
        else:
            logger.error(f"Audio file not found: {audio_path}")
            print(f"Error: Audio file not found: {audio_path}")
    except Exception as e:
        logger.error(f"Failed to play audio: {e}")
        print(f"Error: Failed to play audio: {e}")
    logger.info(f"CLI speak local: '{text}', saved to audio_cache/{filename}")

def main():
    parser = argparse.ArgumentParser(description="Jarvis Assistant")
    subparsers = parser.add_subparsers(dest="mode")

    # CLI mode: speak
    speak_parser = subparsers.add_parser("speak", help="Make Jarvis speak a text")
    speak_parser.add_argument("text", type=str, help="Text for Jarvis to speak")
    speak_parser.add_argument("--speaker", type=str, help="Target speaker room name", default=None)
    speak_parser.add_argument("--filename", type=str, help="Name of the output audio file", default=None)
    
    # CLI mode: ask
    ask_parser = subparsers.add_parser("ask", help="Ask Jarvis a question and get a response")
    ask_parser.add_argument("question", type=str, help="The question to ask Jarvis")
    ask_parser.add_argument("--speaker", type=str, help="Target speaker room name for TTS output", default=None)
    ask_parser.add_argument("--local", action="store_true", help="Play through local audio system instead of Sonos")

    args = parser.parse_args()

    if args.mode == "speak":
        if args.speaker:
            cli_speak(args.text, args.speaker, args.filename)
        else:
            cli_speak_local(args.text, args.filename)
    elif args.mode == "ask":
        response_text = chat_with_jarvis_session("cli_user", args.question)
        print("Jarvis:", response_text)
        logger.info(f"CLI ask: Question: '{args.question}' answered with: '{response_text}' on speaker: '{args.speaker}' (local: {args.local})")
        if args.speaker:
            cli_speak(response_text, args.speaker)
        else:
            cli_speak_local(response_text)
if __name__ == "__main__":
    main()
