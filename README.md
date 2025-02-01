## Setup

1. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables**

   Create a `.env` file with the following:

   ```
   OPENAI_API_KEY=your_openai_api_key
   ELEVENLABS_API_KEY=your_elevenlabs_api_key
   SONOS_SPEAKER_IP=your_default_sonos_ip
   ```

3. **Running the Assistant**

   - **CLI Mode**

     ```bash
     python jarvis.py speak "Hello, world!" --speaker "Living Room"
     ```

   - **Listen Mode**
     ```bash
     python _listen-for-jarvis.py
     ```

## Features

- **Sonos Integration**: Manage and play audio on Sonos speakers.
- **Text-to-Speech**: Generate speech using ElevenLabs TTS.
- **Hotword Detection**: Listen for the "Hey Jarvis" keyword to activate.
- **Audio Server**: Serve audio files for playback on Sonos.

## License

MIT License
