import os
import time
import openai
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Global in-memory conversation store keyed by user/session id
conversation_sessions = {}
CONVERSATION_TTL = 10 * 60  # 10 minutes

def chat_with_jarvis_session(user_id: str, user_text: str) -> str:
    """
    Chat with Jarvis using OpenAI's GPT model.
    Returns the assistant's response as a string.
    """
    system_prompt = (
        "You are Jarvis, a witty, calm, and helpful AI assistant with a dry British accent, "
        "inspired by the AI in the Iron Man movies. Your responses are clever, polite, and always concise."
        "Rules:"
        "- Be factual. Don't beat around the bush and don't talk about your latest update."
        "- Be concise. Always aim to respond in one or two sentences unless more detail is required."
        "- Be helpful. If the user asks for help, provide it."
    )
    
    now = time.time()
    session = conversation_sessions.get(user_id)

    # Use existing conversation if within TTL, otherwise start new
    if session and now - session["last_activity"] < CONVERSATION_TTL:
        conversation = session["messages"]
    else:
        conversation = [{"role": "system", "content": system_prompt}]

    # Append user input
    conversation.append({"role": "user", "content": user_text})

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=conversation
    )
    assistant_reply = response.choices[0].message.content.strip()

    # Append assistant reply
    conversation.append({"role": "assistant", "content": assistant_reply})

    # Save session with updated timestamp
    conversation_sessions[user_id] = {"messages": conversation, "last_activity": now}

    return assistant_reply

def chat_with_jarvis_function_call(user_id: str, user_text: str) -> str:
    """
    Chat with Jarvis using GPT-4 function calling to execute commands.
    """
    system_prompt = (
        "You are Jarvis, a witty, calm, and helpful AI assistant with a dry British accent, "
        "inspired by the AI in the Iron Man movies. "
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
    
    # Define functions for potential side-effects.
    functions = [
        {
            "name": "open_garage_door",
            "description": "Opens the garage door.",
            "parameters": {"type": "object", "properties": {}},
        },
        # You can define more functions here as needed.
    ]
    
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=conversation,
        functions=functions,
        function_call="auto"
    )
    
    message = response.choices[0].message
    
    if message.get("function_call"):
        from actions import dispatch_function_call
        result = dispatch_function_call(message["function_call"])
        conversation.append({
            "role": "function",
            "name": message["function_call"]["name"],
            "content": result
        })
        # Get final answer (which may confirm the action was taken)
        second_response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=conversation
        )
        final_message = second_response.choices[0].message.content.strip()
        conversation.append({"role": "assistant", "content": final_message})
    else:
        final_message = message.content.strip()
        conversation.append({"role": "assistant", "content": final_message})
    
    conversation_sessions[user_id] = {"messages": conversation, "last_activity": now}
    return final_message

if __name__ == "__main__":
    # For testing, using a static user_id. Replace with session id logic as needed.
    user_id = "default_user"
    test_prompt = "Hello Jarvis, how are you today?"
    response_text = chat_with_jarvis_session(user_id, test_prompt)
    print(f"User: {test_prompt}")
    print(f"Jarvis: {response_text}")

