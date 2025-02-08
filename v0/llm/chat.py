import os
import time
import json
import openai
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Global in-memory conversation store keyed by user/session id
conversation_sessions = {}
CONVERSATION_TTL = 10 * 60  # 10 minutes

def load_style_examples():
    try:
        path = os.path.join(os.path.dirname(__file__), "prompts", "style.json")
        with open(path, "r") as f:
            examples = json.load(f)
        return "\n".join(examples)
    except Exception:
        return ""

STYLED_EXAMPLES = load_style_examples()

def chat_with_jarvis_session(user_id: str, user_text: str) -> str:
    """
    Chat with Jarvis using OpenAI's GPT model.
    Returns the assistant's response as a string.
    """
    system_prompt = (
        "You are Jarvis, a helpful AI assistant with a dry British accent, "
        "inspired by the AI in the Iron Man movies. He's sometimes a little sarcastic and a little witty."
        "He's also a little bit of a smartass, but generally is brief and to the point with his responses."
        "Examples of how you speak:\n" + STYLED_EXAMPLES + "\n"
    )
    
    now = time.time()
    session = conversation_sessions.get(user_id)
    
    if session and now - session["last_activity"] < CONVERSATION_TTL:
        conversation = session["messages"]
    else:
        conversation = [{"role": "system", "content": system_prompt}]
    
    conversation.append({"role": "user", "content": user_text})
    
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=conversation
    )
    assistant_reply = response.choices[0].message.content.strip()
    print(f"[LOG] Assistant Response: {assistant_reply}; No function call occurred.")
    
    conversation.append({"role": "assistant", "content": assistant_reply})
    conversation_sessions[user_id] = {"messages": conversation, "last_activity": now}
    
    return assistant_reply

def chat_with_jarvis_function_call(user_id: str, user_text: str) -> str:
    """
    Chat with Jarvis using GPT-4 function calling to execute commands.
    """
    system_prompt = (
        "You are Jarvis, a helpful AI assistant with a dry British accent, "
        "inspired by the AI in the Iron Man movies. He's sometimes a little sarcastic and a little witty."
        "He's also a little bit of a smartass, but generally is brief and to the point with his responses."
        "Examples of how you speak:\n" + STYLED_EXAMPLES + "\n"
        "If the user's request is to perform an action (like opening the garage door), "
        "call the corresponding function instead of replying with plain text."
    )
    
    now = time.time()
    session = conversation_sessions.get(user_id)
    if session and now - session["last_activity"] < CONVERSATION_TTL:
        conversation = session["messages"]
    else:
        conversation = [{"role": "system", "content": system_prompt}]
    
    conversation.append({"role": "user", "content": user_text})
    
    functions = [
        {
            "name": "open_garage_door",
            "description": "Opens the garage door.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "get_tasks",
            "description": "Retrieve a list of tasks or todos.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "create_task",
            "description": "Create a new task or todo with the provided description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "The description of the new task"
                    }
                },
                "required": ["task"]
            },
        },
        {
            "name": "mark_task_done",
            "description": "Mark a task as done using a snippet of its description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "A snippet of the task description to mark as done."
                    }
                },
                "required": ["task"]
            },
        },
    ]
    
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=conversation,
        functions=functions,
        function_call="auto"
    )
    
    message = response.choices[0].message
    
    if message.get("function_call"):
        print(f"[LOG] Function call requested: {message['function_call']}")
        from actions import dispatch_function_call
        result = dispatch_function_call(message["function_call"])
        conversation.append({
            "role": "function",
            "name": message["function_call"]["name"],
            "content": result
        })
        # Insert a hidden system update that instructs Jarvis to acknowledge the result.
        conversation.append({
            "role": "system",
            "content": f"The action '{message['function_call']['name']}' was executed successfully with result: {result}. Please ensure your final response reflects this."
        })
        second_response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=conversation
        )
        final_message = second_response.choices[0].message.content.strip()
        conversation.append({"role": "assistant", "content": final_message})
        print(f"[LOG] Final Response after function call: {final_message}")
    else:
        final_message = message.content.strip()
        conversation.append({"role": "assistant", "content": final_message})
        print(f"[LOG] Assistant Response (plain text): {final_message}")
    
    conversation_sessions[user_id] = {"messages": conversation, "last_activity": now}
    return final_message

if __name__ == "__main__":
    user_id = "default_user"
    test_prompt = "Hello Jarvis, how are you today?"
    response_text = chat_with_jarvis_session(user_id, test_prompt)
    print(f"User: {test_prompt}")
    print(f"Jarvis: {response_text}")

