# maestro_v13_gemini.py - Maestro powered by Gemini 3 Pro

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Make maestro python/ the import root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import google.generativeai as genai
from dotenv import load_dotenv

from tools import tools_v13
from identity.experience_v13 import experience
from knowledge.knowledge_v13 import load_project
from identity.learning import learn, build_system_prompt as _build_experience_prompt
from tools.tools_v13 import tool_definitions
from tools.vision import double_check_pointer, find_missing_pointer, see_page, see_pointer

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


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

    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _build_gemini_tool_declarations() -> list[dict[str, Any]]:
    function_declarations = []
    for tool in tool_definitions:
        function_declarations.append(
            {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": _json_schema_from_params(tool.get("params", {})),
            }
        )
    return [{"function_declarations": function_declarations}]


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


def process_message(chat: Any, message: str) -> str:
    response = chat.send_message(message)

    while True:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            break
        parts = getattr(getattr(candidates[0], "content", None), "parts", [])

        # Collect ALL function calls in this turn (Gemini can return multiple)
        function_calls = []
        for part in parts:
            if hasattr(part, "function_call") and part.function_call:
                function_calls.append(part.function_call)

        if not function_calls:
            break

        # Execute all function calls and build response parts
        response_parts = []
        for fc in function_calls:
            func_name = fc.name
            func_args = dict(fc.args) if fc.args else {}
            print(f"  [Tool] {func_name}({func_args})")

            if func_name in tool_functions:
                try:
                    result = tool_functions[func_name](**func_args) if func_args else tool_functions[func_name]()
                except Exception as exc:
                    result = f"Tool execution error: {exc}"
            else:
                result = f"Unknown function: {func_name}"

            response_parts.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=func_name,
                        response={"result": _stringify_result(result)},
                    )
                )
            )

        response = chat.send_message(
            genai.protos.Content(parts=response_parts)
        )

    final_candidates = getattr(response, "candidates", None) or []
    final_parts = getattr(getattr(final_candidates[0], "content", None), "parts", []) if final_candidates else []
    for part in final_parts:
        if getattr(part, "text", None):
            return part.text
    return "No response"


def main() -> None:
    project_name = project["name"] if project else "No project loaded"

    print("=" * 60)
    print(f"  {experience['soul']}  [Gemini 3 Pro]")
    print(f"  Project: {project_name}")
    print("=" * 60)
    print(f"{experience['greeting']}\n")

    model = genai.GenerativeModel(
        "gemini-3-pro-preview",
        tools=_build_gemini_tool_declarations(),
        system_instruction=build_system_prompt(),
    )
    chat = model.start_chat()

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == "quit":
            print(f"\nMaestro: {experience['farewell']}")
            break
        if not user_input:
            continue

        print("\nMaestro is thinking...")
        answer = process_message(chat, user_input)
        print(f"\nMaestro: {answer}")


if __name__ == "__main__":
    main()

