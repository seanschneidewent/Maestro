# maestro_v12.py - Fully separated: engine + experience + knowledge + tools
import os
import google.generativeai as genai
from dotenv import load_dotenv
from experience_v12 import experience
from knowledge_v12 import project
from tools_v12 import tool_declarations, tool_functions
from learning_v12 import learn, save_experience

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


# === LEARN TOOL (needs access to experience, so it lives in the engine) ===
def learn_tool(learning_mission: str):
    """Wrapper that calls the learning engine and saves the result."""
    global experience
    print(f"\n  [Learning] Mission: {learning_mission}")
    updated = learn(learning_mission, experience)
    save_experience(updated, filepath="experience_v10.py")
    experience.update(updated)
    return "Got it. I've updated my experience. This will stick."

# Register the learn tool
tool_functions["learn"] = learn_tool


# === BUILD SYSTEM PROMPT FROM EXPERIENCE ===
def build_system_prompt():
    """Assemble the system prompt from the experience config."""
    return f"""{experience["soul"]}
{experience["purpose"]}
{experience["tools"]}
{experience["tone"]}
{experience["boundaries"]}"""


# === PROCESS ONE MESSAGE ===
def process_message(chat, message):
    """Send a message and handle any tool calls until we get a final answer."""

    response = chat.send_message(message)

    while response.candidates[0].content.parts:
        part = response.candidates[0].content.parts[0]

        if hasattr(part, 'function_call') and part.function_call:
            func_call = part.function_call
            func_name = func_call.name
            func_args = dict(func_call.args) if func_call.args else {}

            print(f"  [Tool] {func_name}({func_args})")

            if func_name in tool_functions:
                if func_args:
                    result = tool_functions[func_name](**func_args)
                else:
                    result = tool_functions[func_name]()
            else:
                result = f"Unknown function: {func_name}"

            response = chat.send_message(
                genai.protos.Content(
                    parts=[genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=func_name,
                            response={"result": str(result)}
                        )
                    )]
                )
            )
        else:
            break

    return response.candidates[0].content.parts[0].text


# === INTERACTIVE CHAT LOOP ===
def main():
    system_prompt = build_system_prompt()

    print("=" * 60)
    print(f"  {experience['soul']}")
    print(f"  Project: {project['name']}")
    print("=" * 60)
    print(f"{experience['greeting']}\n")

    model = genai.GenerativeModel(
        "gemini-3-pro-preview",
        tools=tool_declarations,
        system_instruction=system_prompt
    )

    chat = model.start_chat()

    while True:
        user_input = input("\nYou: ").strip()

        if user_input.lower() == 'quit':
            print(f"\nMaestro: {experience['farewell']}")
            break

        if not user_input:
            continue

        print("\nMaestro is thinking...")
        answer = process_message(chat, user_input)
        print(f"\nMaestro: {answer}")


if __name__ == "__main__":
    main()
