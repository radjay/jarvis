def main():
    porcupine_instance = pvporcupine.create(keyword_paths=porcupine_keyword_paths)
    pa = pyaudio.PyAudio()

    audio_stream = pa.open(
        rate=porcupine_instance.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine_instance.frame_length
    )

    print("Listening for 'Hey Jarvis' hotword...")

    try:
        while True:
            pcm = audio_stream.read(porcupine_instance.frame_length, exception_on_overflow=False)
            pcm = bytes(pcm)

            keyword_index = porcupine_instance.process(pcm)
            if keyword_index >= 0:
                # Hotword Detected
                print("Hotword Detected! Recording user query...")
                record_audio(output_filename="input.wav", record_seconds=5)

                # Transcribe
                user_text = transcribe_audio_with_whisper("input.wav")
                print("User said:", user_text)

                # Query GPT
                ai_response = chat_with_gpt(user_text)
                print("AI response:", ai_response)

                # TTS
                synthesize_speech_elevenlabs(ai_response, output_filename="response.mp3")

                # Play on Sonos
                play_on_sonos("response.mp3")

    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        audio_stream.close()
        pa.terminate()
        porcupine_instance.delete()
