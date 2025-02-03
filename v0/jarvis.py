#!/usr/bin/env python3

import argparse
import os
from dotenv import load_dotenv
from llm.chat import chat_with_jarvis_session, chat_with_jarvis_function_call
from tts.elevenlabs_tts import synthesize_speech_elevenlabs
from sonos import play_on_sonos
from playsound import playsound
from utilities import logger
from jarvis_voice import voice_mode
from tts.speaker import cli_speak, cli_speak_local
from config import BASE_DIR

load_dotenv()

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
    
    # CLI mode: voice
    voice_parser = subparsers.add_parser("voice", help="Activate voice mode")
    voice_parser.add_argument("--speaker", type=str, default=None, help="Target Sonos speaker room name")

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
    elif args.mode == "voice":
        use_sonos = bool(args.speaker)  # Set use_sonos to True if a speaker is specified
        voice_mode(use_sonos=use_sonos, speaker=args.speaker)

if __name__ == "__main__":
    main()
