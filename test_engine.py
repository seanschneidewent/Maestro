"""Quick test: send one query to Gemini engine and print the response."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "maestro python"))

from engine.maestro_v13_gemini import build_system_prompt, process_message, _build_gemini_tool_declarations, tool_functions
import google.generativeai as genai

print("=== System Prompt ===")
sp = build_system_prompt()
print(sp[:500])
print(f"... ({len(sp)} chars total)")

print("\n=== Creating Chat ===")
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",  # Use flash for quick test
    system_instruction=sp,
    tools=_build_gemini_tool_declarations(),
)
chat = model.start_chat()

print("\n=== Query: What architectural sheets do we have? ===")
response = process_message(chat, "What architectural sheets do we have?")
print(f"\n=== Response ===\n{response}")
