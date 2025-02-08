import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

from flask import Flask, request, render_template, redirect, url_for, abort, jsonify
import json
from sonos import play_on_sonos
from tts import synthesize_speech_elevenlabs
from sonos.speakers import find_sonos_speakers
from sonos.cache import load_sonos_cache, save_sonos_cache
from llm.chat import chat_with_jarvis_session, chat_with_jarvis_function_call, conversation_sessions
from utilities import logger
from db.models import (
    add_todo, get_todos, update_todo, delete_todo,
    add_calendar_item, get_calendar_items, update_calendar_item, delete_calendar_item,
    add_message, get_messages, update_message, delete_message,
)
from integrations.google import google_bp
import secrets

app = Flask(__name__)
# For production, set the SECRET_KEY environment variable; otherwise, this generates a secure random key.
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

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
                    user_id = request.remote_addr  # Use request IP as user identifier; replace as needed.
                    answer = chat_with_jarvis_session(user_id, question)
                    if jarvisify:
                        answer = chat_with_jarvis_session(user_id, "Rewrite the following text in Jarvis style: " + answer)
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

@app.route("/todos", methods=["GET", "POST"])
def manage_todos():
    user_id = request.remote_addr
    if request.method == "POST":
        task = request.form.get("task")
        if task:
            add_todo(user_id, task)
            logger.info(f"Added todo: {task} for user: {user_id}")
            return redirect(url_for('manage_todos'))
    todos = get_todos(user_id).data
    return render_template("todos.html", todos=todos)

@app.route("/todos/update/<int:todo_id>", methods=["POST"])
def update_todo_route(todo_id):
    completed = request.form.get("completed") == "on"
    update_todo(todo_id, {"completed": completed})
    logger.info(f"Updated todo ID {todo_id} to completed={completed}")
    return redirect(url_for('manage_todos'))

@app.route("/todos/delete/<int:todo_id>", methods=["POST"])
def delete_todo_route(todo_id):
    delete_todo(todo_id)
    logger.info(f"Deleted todo ID {todo_id}")
    return redirect(url_for('manage_todos'))

@app.route("/calendar", methods=["GET", "POST"])
def manage_calendar():
    user_id = request.remote_addr
    if request.method == "POST":
        title = request.form.get("title")
        event_date = request.form.get("event_date")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")
        all_day = request.form.get("all_day") == "on"
        description = request.form.get("description", "")
        if title and event_date:
            add_calendar_item(user_id, title, event_date, start_time, end_time, all_day, description)
            logger.info(f"Added calendar item: {title} on {event_date} for user: {user_id}")
            return redirect(url_for('manage_calendar'))
    events = get_calendar_items(user_id).data
    return render_template("calendar.html", events=events)

@app.route("/calendar/edit/<int:item_id>", methods=["GET"])
def edit_calendar_route(item_id):
    response = supabase.table("calendar_items").select("*").eq("id", item_id).single().execute()
    event = response.data
    if not event:
        abort(404, description="Calendar event not found.")
    return render_template("edit_calendar.html", event=event)

@app.route("/calendar/update/<int:item_id>", methods=["POST"])
def update_calendar_route(item_id):
    # Handle POST to update the event
    ...

@app.route("/calendar/delete/<int:item_id>", methods=["POST"])
def delete_calendar_route(item_id):
    delete_calendar_item(item_id)
    logger.info(f"Deleted calendar item ID {item_id}")
    return redirect(url_for('manage_calendar'))

@app.route("/messages", methods=["GET", "POST"])
def manage_messages():
    user_id = request.remote_addr
    if request.method == "POST":
        subject = request.form.get("subject")
        body = request.form.get("body")
        if subject and body:
            add_message(user_id, subject, body)
            logger.info(f"Added message: {subject} for user: {user_id}")
            return redirect(url_for('manage_messages'))
    messages = get_messages(user_id).data
    return render_template("messages.html", messages=messages)

@app.route("/messages/update/<int:message_id>", methods=["POST"])
def update_message_route(message_id):
    sent = request.form.get("sent") == "on"
    update_message(message_id, {"sent": sent})
    logger.info(f"Updated message ID {message_id} to sent={sent}")
    return redirect(url_for('manage_messages'))

@app.route("/messages/delete/<int:message_id>", methods=["POST"])
def delete_message_route(message_id):
    delete_message(message_id)
    logger.info(f"Deleted message ID {message_id}")
    return redirect(url_for('manage_messages'))

@app.route("/chat", methods=["GET", "POST"])
def chat():
    user_id = request.remote_addr
    if request.method == "POST":
        user_message = request.form.get("message", "").strip()
        if user_message:
            # Use function calling to maintain conversation context
            chat_with_jarvis_function_call(user_id, user_message)
    session_data = conversation_sessions.get(user_id, {"messages": []})
    # Filter out any system messages
    conversation = [msg for msg in session_data["messages"] if msg.get("role") != "system"]
    return render_template("chat.html", conversation=conversation)

@app.route("/chat_ajax", methods=["POST"])
def chat_ajax():
    user_id = request.remote_addr
    user_message = request.form.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400
    # Process the message through your function-calling method.
    chat_with_jarvis_function_call(user_id, user_message)
    session_data = conversation_sessions.get(user_id, {"messages": []})
    conversation = [msg for msg in session_data["messages"] if msg.get("role") != "system"]
    # Return the latest assistant message.
    new_message = conversation[-1] if conversation and conversation[-1].get("role") == "assistant" else {}
    return jsonify({"new_message": new_message})

app.register_blueprint(google_bp)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)