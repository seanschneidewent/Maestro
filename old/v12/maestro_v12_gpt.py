# maestro_v12_gpt.py - Maestro powered by GPT-5.2
# Same architecture as V12 — just a different brain.
import os
from openai import OpenAI
from dotenv import load_dotenv
from experience_v12 import experience
from knowledge_v12 import project
from tools_v12 import tool_functions
from learning_v12 import learn, save_experience

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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


# === TOOL DECLARATIONS (OpenAI format) ===
openai_tools = [
    {
        "type": "function",
        "function": {
            "name": "list_disciplines",
            "description": "List all disciplines (like Architectural, MEP, Structural) in the project",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_pages",
            "description": "List all pages within a specific discipline",
            "parameters": {
                "type": "object",
                "properties": {
                    "discipline": {
                        "type": "string",
                        "description": "The discipline name (e.g., 'MEP', 'Architectural')"
                    }
                },
                "required": ["discipline"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_page_knowledge",
            "description": "Get detailed knowledge from a specific page",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_name": {
                        "type": "string",
                        "description": "The page name (e.g., 'E101', 'M102 - HVAC Specs')"
                    }
                },
                "required": ["page_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "learn",
            "description": "Learn from feedback. Use when the superintendent corrects your behavior, tells you to do something differently, or teaches you something about how to work. This permanently updates your experience.",
            "parameters": {
                "type": "object",
                "properties": {
                    "learning_mission": {
                        "type": "string",
                        "description": "What to learn (e.g., 'Don't ask which discipline to check — just go look autonomously')"
                    }
                },
                "required": ["learning_mission"]
            }
        }
    }
]


# === BUILD SYSTEM PROMPT FROM EXPERIENCE ===
def build_system_prompt():
    """Assemble the system prompt from the experience config."""
    return f"""{experience["soul"]}
{experience["purpose"]}
{experience["tools"]}
{experience["tone"]}
{experience["boundaries"]}"""


# === PROCESS ONE MESSAGE ===
def process_message(messages):
    """Send messages and handle any tool calls until we get a final answer."""
    import json

    response = client.chat.completions.create(
        model="gpt-5.2",
        messages=messages,
        tools=openai_tools
    )

    message = response.choices[0].message

    # Agentic loop: keep going while GPT wants to call tools
    while message.tool_calls:
        # Add assistant message with tool calls to history
        messages.append(message)

        # Process each tool call
        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}

            print(f"  [Tool] {func_name}({func_args})")

            # Execute the function
            if func_name in tool_functions:
                if func_args:
                    result = tool_functions[func_name](**func_args)
                else:
                    result = tool_functions[func_name]()
            else:
                result = f"Unknown function: {func_name}"

            # Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            })

        # Send back to GPT
        response = client.chat.completions.create(
            model="gpt-5.2",
            messages=messages,
            tools=openai_tools
        )
        message = response.choices[0].message

    return message, message.content


# === INTERACTIVE CHAT LOOP ===
def main():
    print("=" * 60)
    print(f"  {experience['soul']}  [GPT-5.2]")
    print(f"  Project: {project['name']}")
    print("=" * 60)
    print(f"{experience['greeting']}\n")

    # OpenAI uses a messages list with system message first
    messages = [
        {"role": "system", "content": build_system_prompt()}
    ]

    while True:
        user_input = input("\nYou: ").strip()

        if user_input.lower() == 'quit':
            print(f"\nMaestro: {experience['farewell']}")
            break

        if not user_input:
            continue

        print("\nMaestro is thinking...")

        # Add user message
        messages.append({"role": "user", "content": user_input})

        # Process and get answer
        message, answer = process_message(messages)

        # Add assistant response to history
        messages.append({"role": "assistant", "content": answer})

        print(f"\nMaestro: {answer}")


if __name__ == "__main__":
    main()
