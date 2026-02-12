"""Interactive chat with Maestro V13 — Gemini engine."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "maestro python"))

from engine.maestro_v13_gemini import build_system_prompt, process_message, _build_gemini_tool_declarations, tool_functions, experience
import google.generativeai as genai

print(f"\n  {experience['soul']}  [Gemini 3 Pro]\n")

sp = build_system_prompt()
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    system_instruction=sp,
    tools=_build_gemini_tool_declarations(),
)
chat = model.start_chat()

print(f"{experience.get('greeting', 'Ready.')}\n")

while True:
    try:
        user_input = input("You: ").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{experience.get('farewell', 'Later.')}")
        break

    if not user_input:
        continue
    if user_input.lower() in ("quit", "exit", "bye"):
        print(f"\n{experience.get('farewell', 'Later.')}")
        break

    response = process_message(chat, user_input)
    print(f"\nMaestro: {response}\n")
