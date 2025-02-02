from flask import Flask, request, render_template
import os
import json
from sonos import play_on_sonos
from tts import synthesize_speech_elevenlabs
from sonos.speakers import find_sonos_speakers
from sonos.cache import load_sonos_cache, save_sonos_cache
from llm.chat import chat_with_jarvis
from utilities import logger

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

def get_history():
    import re
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "app.log")
    entries = []
    log_re = re.compile(r'^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<level>\w+):\s+(?P<message>.+)$')
    try:
        with open(log_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                m = log_re.match(line)
                if m:
                    entries.append(m.groupdict())
                else:
                    entries.append({"date": "", "level": "", "message": line})
        return entries[::-1]
    except Exception as e:
        print("Error loading log history:", e)
        return []

@app.route("/", methods=["GET", "POST"])
def index():
    speakers = get_speaker_list()
    result = ""
    selected_speaker = ""
    if request.method == "POST":
        jarvisify = request.form.get("jarvisify")
        if "refresh" in request.form:
            speakers = refresh_speaker_list()
            result = "Speaker list refreshed."
            logger.info(f"Speaker list refreshed. Available speakers: {speakers}")
        elif "ask" in request.form:
            question = request.form.get("message", "")
            selected_speaker = request.form.get("speaker", "")
            if question:
                try:
                    answer = chat_with_jarvis(question)
                    if jarvisify:
                        answer = chat_with_jarvis("Rewrite the following text in Jarvis style: " + answer)
                    filename = synthesize_speech_elevenlabs(answer)
                    play_on_sonos(filename, room_name=selected_speaker)
                    result = f"Jarvis responded: {answer}"
                    logger.info(f"Answered question: '{question}' with response: '{answer[:50]}...' on speaker: '{selected_speaker}' (jarvisify: {'yes' if jarvisify else 'no'})")
                except Exception as e:
                    result = f"Error: {e}"
                    logger.error(f"Error answering question: '{question}' on speaker: '{selected_speaker}' - {e}")
            else:
                result = "Please enter a question."
        else:
            message = request.form.get("message", "")
            selected_speaker = request.form.get("speaker", "")
            if message:
                try:
                    if jarvisify:
                        message = chat_with_jarvis("Rewrite the following text in Jarvis style: " + message)
                    filename = synthesize_speech_elevenlabs(message)
                    play_on_sonos(filename, room_name=selected_speaker)
                    result = f"Played message on speaker '{selected_speaker}'."
                    logger.info(f"Spoke message: '{message}' on '{selected_speaker}' (jarvisify: {'yes' if jarvisify else 'no'})")
                except Exception as e:
                    result = f"Error: {e}"
                    logger.error(f"Error speaking message: '{message}' on '{selected_speaker}' - {e}")
    history = get_history() or []  # force non-null history
    return render_template("index.html", speakers=speakers, result=result, selected_speaker=selected_speaker, history=history)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)