# maestro_v13_opus.py - Maestro powered by Claude Opus 4.6

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Make maestro python/ the import root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic
from dotenv import load_dotenv

from tools import tools_v13
from identity.experience_v13 import experience
from knowledge.knowledge_v13 import load_project
from identity.learning import learn, build_system_prompt as _build_experience_prompt
from tools.tools_v13 import tool_definitions
from tools.vision import double_check_pointer, find_missing_pointer, see_page, see_pointer

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _json_schema_from_params(params: dict[str, Any]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, spec in params.items():
        field: dict[str, Any] = {"type": spec.get("type", "string")}
        description = spec.get("description")
        if description:
            field["description"] = description
        properties[name] = field
        if spec.get("required", False):
            required.append(name)
    return {"type": "object", "properties": properties, "required": required}


def _build_claude_tools() -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for tool in tool_definitions:
        tools.append(
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": _json_schema_from_params(tool.get("params", {})),
            }
        )
    return tools


project = load_project()
tools_v13.project = project
tool_functions = dict(tools_v13.tool_functions)


def _project_required() -> str | None:
    if project is None:
        return "No project loaded. Run: python ingest.py <folder>"
    return None


def see_page_tool(page_name: str) -> str:
    err = _project_required()
    if err:
        return err
    return see_page(page_name, project)


def see_pointer_tool(page_name: str, region_id: str) -> str:
    err = _project_required()
    if err:
        return err
    return see_pointer(page_name, region_id, project)


def find_missing_pointer_tool(page_name: str, mission: str) -> str:
    err = _project_required()
    if err:
        return err
    return find_missing_pointer(page_name, mission, project)


def double_check_pointer_tool(page_name: str, region_id: str, mission: str) -> str:
    err = _project_required()
    if err:
        return err
    return double_check_pointer(page_name, region_id, mission, project)


def learn_tool(learning_mission: str) -> str:
    print(f"\n  [Learning] Mission: {learning_mission}")
    result = learn(learning_mission)
    return result


tool_functions["see_page"] = see_page_tool
tool_functions["see_pointer"] = see_pointer_tool
tool_functions["find_missing_pointer"] = find_missing_pointer_tool
tool_functions["double_check_pointer"] = double_check_pointer_tool
tool_functions["learn"] = learn_tool


def _stringify_result(result: Any) -> str:
    if isinstance(result, (dict, list)):
        return json.dumps(result, indent=2, ensure_ascii=True)
    return str(result)


def build_system_prompt() -> str:
    return _build_experience_prompt()


def process_message(messages: list[dict[str, Any]], claude_tools: list[dict[str, Any]]) -> tuple[Any, str]:
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        system=build_system_prompt(),
        tools=claude_tools,
        messages=messages,
    )

    while response.stop_reason == "tool_use":
        tool_results = []

        for block in response.content:
            if block.type != "tool_use":
                continue

            func_name = block.name
            func_args = block.input or {}
            tool_id = block.id
            print(f"  [Tool] {func_name}({func_args})")

            if func_name in tool_functions:
                try:
                    result = tool_functions[func_name](**func_args) if func_args else tool_functions[func_name]()
                except Exception as exc:
                    result = f"Tool execution error: {exc}"
            else:
                result = f"Unknown function: {func_name}"

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": _stringify_result(result),
                }
            )

        # Serialize content blocks to dicts for the next API call
        assistant_content = []
        for block in response.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
            elif block.type == "thinking":
                assistant_content.append({"type": "thinking", "thinking": block.thinking})

        messages.append({"role": "assistant", "content": assistant_content})
        messages.append({"role": "user", "content": tool_results})

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=build_system_prompt(),
            tools=claude_tools,
            messages=messages,
        )

    final_text = ""
    for block in response.content:
        if hasattr(block, "text") and block.text:
            final_text = block.text
            break

    return response, final_text or "No response"


def main() -> None:
    project_name = project["name"] if project else "No project loaded"
    claude_tools = _build_claude_tools()

    print("=" * 60)
    print(f"  {experience['soul']}  [Opus 4.6]")
    print(f"  Project: {project_name}")
    print("=" * 60)
    print(f"{experience['greeting']}\n")

    messages: list[dict[str, Any]] = []

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == "quit":
            print(f"\nMaestro: {experience['farewell']}")
            break
        if not user_input:
            continue

        print("\nMaestro is thinking...")
        messages.append({"role": "user", "content": user_input})
        response, answer = process_message(messages, claude_tools)
        messages.append({"role": "assistant", "content": response.content})
        print(f"\nMaestro: {answer}")


if __name__ == "__main__":
    main()

