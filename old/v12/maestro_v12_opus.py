# maestro_v12_opus.py - Maestro powered by Claude Opus 4.6
# Same architecture as V12 Gemini — just a different brain.
import os
import anthropic
from dotenv import load_dotenv
from experience_v12 import experience
from knowledge_v12 import project
from tools_v12 import tool_functions
from learning_v12 import learn, save_experience

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


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


# === TOOL DECLARATIONS (Claude format — different from Gemini) ===
claude_tools = [
    {
        "name": "list_disciplines",
        "description": "List all disciplines (like Architectural, MEP, Structural) in the project",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "list_pages",
        "description": "List all pages within a specific discipline",
        "input_schema": {
            "type": "object",
            "properties": {
                "discipline": {
                    "type": "string",
                    "description": "The discipline name (e.g., 'MEP', 'Architectural')"
                }
            },
            "required": ["discipline"]
        }
    },
    {
        "name": "get_page_knowledge",
        "description": "Get detailed knowledge from a specific page",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_name": {
                    "type": "string",
                    "description": "The page name (e.g., 'E101', 'M102 - HVAC Specs')"
                }
            },
            "required": ["page_name"]
        }
    },
    {
        "name": "learn",
        "description": "Learn from feedback. Use when the superintendent corrects your behavior, tells you to do something differently, or teaches you something about how to work. This permanently updates your experience.",
        "input_schema": {
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

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        system=build_system_prompt(),
        tools=claude_tools,
        messages=messages
    )

    # Agentic loop: keep going while Claude wants to call tools
    while response.stop_reason == "tool_use":
        # Find all tool use blocks in the response
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                func_name = block.name
                func_args = block.input
                tool_id = block.id

                print(f"  [Tool] {func_name}({func_args})")

                # Execute the function
                if func_name in tool_functions:
                    if func_args:
                        result = tool_functions[func_name](**func_args)
                    else:
                        result = tool_functions[func_name]()
                else:
                    result = f"Unknown function: {func_name}"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": str(result)
                })

        # Add assistant response and tool results to conversation
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        # Send back to Claude
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=build_system_prompt(),
            tools=claude_tools,
            messages=messages
        )

    # Get final text answer
    for block in response.content:
        if hasattr(block, 'text'):
            return response, block.text

    return response, "No response"


# === INTERACTIVE CHAT LOOP ===
def main():
    print("=" * 60)
    print(f"  {experience['soul']}  [Opus 4.6]")
    print(f"  Project: {project['name']}")
    print("=" * 60)
    print(f"{experience['greeting']}\n")

    # Claude uses a messages list (not a chat object like Gemini)
    messages = []

    while True:
        user_input = input("\nYou: ").strip()

        if user_input.lower() == 'quit':
            print(f"\nMaestro: {experience['farewell']}")
            break

        if not user_input:
            continue

        print("\nMaestro is thinking...")

        # Add user message to conversation history
        messages.append({"role": "user", "content": user_input})

        # Process and get answer
        response, answer = process_message(messages)

        # Add assistant response to history (for conversation memory)
        messages.append({"role": "assistant", "content": response.content})

        print(f"\nMaestro: {answer}")


if __name__ == "__main__":
    main()
