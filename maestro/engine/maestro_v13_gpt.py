# maestro_v13_gpt.py - Maestro powered by GPT-5.2

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Make maestro python/ the import root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from openai import OpenAI

from tools import tools_v13, workspaces
from identity.experience_v13 import experience
from knowledge.knowledge_v13 import load_project
from identity.learning import learn, build_system_prompt as _build_experience_prompt
from tools.tools_v13 import tool_definitions
from tools.workspaces import workspace_tool_definitions, workspace_tool_functions
from tools.vision import double_check_pointer, find_missing_pointer, see_page, see_pointer

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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


def _build_openai_tools() -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for tool in all_tool_definitions:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": _json_schema_from_params(tool.get("params", {})),
                },
            }
        )
    return tools


project = load_project()
tools_v13.project = project
workspaces.init_workspaces(project)
all_tool_definitions = tool_definitions + workspace_tool_definitions
tool_functions = dict(tools_v13.tool_functions)
tool_functions.update(workspace_tool_functions)


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


def process_message(messages: list[dict[str, Any]], openai_tools: list[dict[str, Any]]) -> tuple[Any, str]:
    response = client.chat.completions.create(
        model="gpt-5.2",
        messages=messages,
        tools=openai_tools,
    )
    message = response.choices[0].message

    while message.tool_calls:
        messages.append(message)

        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            raw_args = tool_call.function.arguments or "{}"
            try:
                func_args = json.loads(raw_args)
            except json.JSONDecodeError:
                func_args = {}

            print(f"  [Tool] {func_name}({func_args})")

            if func_name in tool_functions:
                try:
                    result = tool_functions[func_name](**func_args) if func_args else tool_functions[func_name]()
                except Exception as exc:
                    result = f"Tool execution error: {exc}"
            else:
                result = f"Unknown function: {func_name}"

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": _stringify_result(result),
                }
            )

        response = client.chat.completions.create(
            model="gpt-5.2",
            messages=messages,
            tools=openai_tools,
        )
        message = response.choices[0].message

    content = message.content if message.content is not None else "No response"
    return message, content


def main() -> None:
    project_name = project["name"] if project else "No project loaded"
    openai_tools = _build_openai_tools()

    print("=" * 60)
    print(f"  {experience['soul']}  [GPT-5.2]")
    print(f"  Project: {project_name}")
    print("=" * 60)
    print(f"{experience['greeting']}\n")

    messages: list[dict[str, Any]] = [{"role": "system", "content": build_system_prompt()}]

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == "quit":
            print(f"\nMaestro: {experience['farewell']}")
            break
        if not user_input:
            continue

        print("\nMaestro is thinking...")
        messages.append({"role": "user", "content": user_input})
        _, answer = process_message(messages, openai_tools)
        messages.append({"role": "assistant", "content": answer})
        print(f"\nMaestro: {answer}")


if __name__ == "__main__":
    main()
