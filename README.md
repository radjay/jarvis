## Setup

1. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables**

   Create a `.env` file in your project root with the following:

   ```
   OPENAI_API_KEY=your_openai_api_key
   ELEVENLABS_API_KEY=your_elevenlabs_api_key
   PORCUPINE_ACCESS_KEY=your_porcupine_access_key
   SONOS_SPEAKER_IP=your_default_sonos_ip
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_anon_key
   ```

3. **Virtual Environment (Optional but Recommended)**

   Create and activate a virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

   _(For automatic activation, consider using [direnv](https://direnv.net/).)_

4. **Running the Assistant**

   - **CLI Mode**

     ```bash
     python jarvis.py speak "Hello, world!" --speaker "Living Room"
     ```

   - **Voice Mode**
     ```bash
     python jarvis.py voice --speaker "Living Room"
     ```

5. **Supabase Configuration**

   - **Environment Variables**

     Add the following to your `.env` file:

     ```
     SUPABASE_URL=your_supabase_url
     SUPABASE_KEY=your_supabase_anon_key
     ```

   - **Database Tables**

     Use Supabase SQL editor to create the following tables:

   ```sql
   -- Todos Table
   CREATE TABLE todos (
   id SERIAL PRIMARY KEY,
   user_id TEXT NOT NULL,
   task TEXT NOT NULL,
   completed BOOLEAN DEFAULT FALSE,
   created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
   );

   -- Calendar Items Table
   CREATE TABLE calendar_items (
   id SERIAL PRIMARY KEY,
   user_id TEXT NOT NULL,
   title TEXT NOT NULL,
   event_date DATE NOT NULL,
   start_time TIME,
   end_time TIME,
   all_day BOOLEAN DEFAULT FALSE,
   description TEXT,
   created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
   );

   -- Messages Table
   CREATE TABLE messages (
   id SERIAL PRIMARY KEY,
   user_id TEXT NOT NULL,
   subject TEXT NOT NULL,
   body TEXT NOT NULL,
   sent BOOLEAN DEFAULT FALSE,
   created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
   );
   ```

## Features

- **Sonos Integration**: Manage and play audio on Sonos speakers.
- **Text-to-Speech**: Generate speech using ElevenLabs TTS.
- **Hotword Detection**: Listen for the "Hey Jarvis" keyword to activate.
- **Audio Server**: Serve audio files for playback on Sonos.

## Notes

- Make "jarvis" globally available as a command:
  sudo ln -s /Users/radjay/dev/jarvis/v0/jarvis.py /usr/local/bin/jarvis

## License

MIT License

## Messages Table Schema

The `messages` table stores both system messages and synced Google email data. The schema is as follows:

- **id**: SERIAL PRIMARY KEY
- **user_id**: TEXT  
  Identifier for the user.
- **subject**: TEXT  
  The subject of the message or email.
- **body**: TEXT  
  The body content.
- **unique_id**: TEXT  
  A unique identifier from the source system (e.g., Gmail message ID). This is used to ensure that duplicate messages are not synced.
- **message_type**: TEXT (default: 'email')  
  Indicates the type of message, currently set to `"email"` for Google Mail messages.
- **sent**: BOOLEAN (default: FALSE)  
  Indicates whether the message has been processed or sent.
- **important**: BOOLEAN (default: FALSE)  
  Marks whether the message is in the priority inbox (i.e., Gmail's "Important" label).
- **created_at**: TIMESTAMP  
  (Optional) Timestamp of record creation if managed by Supabase.
- **updated_at**: TIMESTAMP  
  (Optional) Timestamp of last update.

This schema ensures unique syncing of emails by enforcing a uniqueness constraint on the combination of user_id and unique_id.

```

```
