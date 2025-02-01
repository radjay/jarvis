import os
import openai
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def chat_with_jarvis(user_text: str) -> str:
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
    
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ]
    )
    
    return response.choices[0].message.content.strip()


if __name__ == "__main__":
    test_prompt = "Hello Jarvis, how are you today?"
    response = chat_with_jarvis(test_prompt)
    print(f"User: {test_prompt}")
    print(f"Jarvis: {response}")

