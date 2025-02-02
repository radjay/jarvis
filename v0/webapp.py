from flask import Flask, request, render_template
import os
import json
from sonos import play_on_sonos
from tts import synthesize_speech_elevenlabs
from sonos.speakers import find_sonos_speakers
from sonos.cache import load_sonos_cache, save_sonos_cache
from llm.chat import chat_with_jarvis

app = Flask(__name__)

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sonos_cache.json")

def get_speaker_list():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
        return list(cache.keys())
    return []

def refresh_speaker_list():
    speakers = find_sonos_speakers()
    cache = load_sonos_cache()
    if speakers:
        for speaker in speakers:
            cache[speaker.player_name] = speaker.ip_address
        save_sonos_cache(cache)
    return list(cache.keys())

@app.route("/", methods=["GET", "POST"])
def index():
    speakers = get_speaker_list()
    result = ""
    selected_speaker = ""
    if request.method == "POST":
        if "refresh" in request.form:
            speakers = refresh_speaker_list()
            result = "Speaker list refreshed."
        elif "ask" in request.form:
            question = request.form.get("message", "")
            selected_speaker = request.form.get("speaker", "")
            if question:
                try:
                    answer = chat_with_jarvis(question)
                    filename = synthesize_speech_elevenlabs(answer)
                    play_on_sonos(filename, room_name=selected_speaker)
                    result = f"Jarvis responded: {answer}"
                except Exception as e:
                    result = f"Error: {e}"
            else:
                result = "Please enter a question."
        else:
            message = request.form.get("message", "")
            selected_speaker = request.form.get("speaker", "")
            if message:
                try:
                    filename = synthesize_speech_elevenlabs(message)
                    play_on_sonos(filename, room_name=selected_speaker)
                    result = f"Played message on speaker '{selected_speaker}'."
                except Exception as e:
                    result = f"Error: {e}"
    return render_template("index.html", speakers=speakers, result=result, selected_speaker=selected_speaker)

if __name__ == "__main__":
    app.run(debug=True, port=5000)