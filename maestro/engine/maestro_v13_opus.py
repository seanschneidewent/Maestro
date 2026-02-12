# maestro_v13_opus.py - Maestro powered by Claude Opus 4.6

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Make maestro python/ the import root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic
from dotenv import load_dotenv

from tools import tools_v13, workspaces
from identity.experience_v13 import experience
from knowledge.knowledge_v13 import load_project
from identity.learning import build_system_prompt as _build_experience_prompt
from learning import agent as learning_agent
from learning import status as learning_status
from tools.tools_v13 import tool_definitions
from tools.workspaces import workspace_tool_definitions, workspace_tool_functions
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
    for tool in all_tool_definitions:
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


tool_functions["see_page"] = see_page_tool
tool_functions["see_pointer"] = see_pointer_tool
tool_functions["find_missing_pointer"] = find_missing_pointer_tool
tool_functions["double_check_pointer"] = double_check_pointer_tool


def _stringify_result(result: Any) -> str:
    if isinstance(result, (dict, list)):
        return json.dumps(result, indent=2, ensure_ascii=True)
    return str(result)


def build_system_prompt() -> str:
    return _build_experience_prompt()


def process_message(
    messages: list[dict[str, Any]],
    claude_tools: list[dict[str, Any]],
) -> tuple[Any, str, dict[str, Any]]:
    tool_calls: list[dict[str, Any]] = []
    workspace_slugs: set[str] = set()

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

            start = time.perf_counter()
            success = True
            error_text: str | None = None
            if func_name in tool_functions:
                try:
                    result = tool_functions[func_name](**func_args) if func_args else tool_functions[func_name]()
                except Exception as exc:
                    success = False
                    result = f"Tool execution error: {exc}"
                    error_text = str(exc)
            else:
                success = False
                result = f"Unknown function: {func_name}"
                error_text = result

            elapsed_ms = int((time.perf_counter() - start) * 1000)
            workspace_slug = learning_agent.mutated_workspace_slug_from_tool_call(func_name, func_args, result)
            if workspace_slug:
                workspace_slugs.add(workspace_slug)

            tool_calls.append(
                {
                    "id": tool_id,
                    "name": func_name,
                    "args": func_args,
                    "time_ms": elapsed_ms,
                    "success": success,
                    "error": error_text,
                    "result": result,
                }
            )

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

    return response, final_text or "No response", {
        "tool_calls": tool_calls,
        "workspace_slugs": sorted(workspace_slugs),
    }


def main() -> None:
    project_name = project["name"] if project else "No project loaded"
    claude_tools = _build_claude_tools()

    print("=" * 60)
    print(f"  {experience['soul']}  [Opus 4.6]")
    print(f"  Project: {project_name}")
    print("=" * 60)
    print(f"{experience['greeting']}\n")

    learning_agent.start_worker_if_enabled()

    messages: list[dict[str, Any]] = []
    last_assistant_response = ""
    last_tool_calls: list[dict[str, Any]] = []

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == "quit":
            print(f"\nMaestro: {experience['farewell']}")
            break
        if not user_input:
            continue

        if learning_agent.is_explicit_correction(user_input):
            learning_agent.enqueue_feedback_job(
                user_message=user_input,
                prior_assistant_response=last_assistant_response,
                prior_tool_calls=last_tool_calls,
            )

        print("\nMaestro is thinking...")
        messages.append({"role": "user", "content": user_input})
        response, answer, turn_meta = process_message(messages, claude_tools)
        messages.append({"role": "assistant", "content": response.content})
        print(f"\nMaestro: {answer}")

        for workspace_slug in turn_meta.get("workspace_slugs", []):
            learning_agent.enqueue_workspace_job(
                workspace_slug=workspace_slug,
                user_message=user_input,
                assistant_response=answer,
                tool_calls=turn_meta.get("tool_calls", []),
            )

        status_payload = learning_status.read_status()
        if isinstance(status_payload, dict) and status_payload.get("active"):
            status_message = str(status_payload.get("message", "")).strip()
            if status_message:
                print("-" * 57)
                print(f" [Learning] {status_message}")

        last_assistant_response = answer
        last_tool_calls = turn_meta.get("tool_calls", [])


if __name__ == "__main__":
    main()
