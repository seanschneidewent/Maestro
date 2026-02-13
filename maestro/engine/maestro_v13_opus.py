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

from tools import tools_v13, workspaces
from identity.experience_v13 import experience
from knowledge.knowledge_v13 import load_project
from identity.learning import (
    build_system_prompt as _build_experience_prompt,
    update_experience,
    update_tool_description,
    update_knowledge,
)
from tools.tools_v13 import tool_definitions
from tools.workspaces import workspace_tool_definitions, workspace_tool_functions
from tools.vision import see_page, see_pointer, gemini_vision_agent

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


# ---------------------------------------------------------------------------
# Vision tool definitions
# ---------------------------------------------------------------------------

vision_tool_definitions = [
    {
        "name": "see_page",
        "description": "Look at the full page image yourself to visually inspect it.",
        "params": {"page_name": {"type": "string", "required": True}},
    },
    {
        "name": "see_pointer",
        "description": "Look at a cropped region image to visually inspect a detail.",
        "params": {
            "page_name": {"type": "string", "required": True},
            "region_id": {"type": "string", "required": True},
        },
    },
    {
        "name": "gemini_vision_agent",
        "description": "Dispatch Gemini as a vision specialist to deeply inspect a page. Use when you need pixel-level detail extraction, verification of specific claims, or finding something not in the knowledge store. Write a clear mission describing what to look for.",
        "params": {
            "page_name": {"type": "string", "required": True},
            "mission": {"type": "string", "description": "What to look for, verify, or extract", "required": True},
        },
    },
]

# ---------------------------------------------------------------------------
# Learning tool definitions
# ---------------------------------------------------------------------------

learning_tool_definitions = [
    {
        "name": "update_experience",
        "description": "Update Maestro's experience files. Use to record lessons learned, refine discipline knowledge, or update behavioral patterns. soul.json is read-only.",
        "params": {
            "file": {"type": "string", "description": "Relative path in experience/ (e.g. disciplines/kitchen.json, patterns.json)", "required": True},
            "action": {"type": "string", "description": "append_to_list or set_field", "required": True},
            "field": {"type": "string", "description": "Field name to modify", "required": True},
            "value": {"type": "string", "description": "Value to append or set", "required": True},
            "reasoning": {"type": "string", "description": "Why this update matters", "required": True},
        },
    },
    {
        "name": "update_tool_description",
        "description": "Update tips and strategy for a specific tool based on what you've learned works well. These tips appear in your system prompt to guide future use.",
        "params": {
            "tool_name": {"type": "string", "description": "Name of the tool to add tips for", "required": True},
            "tips": {"type": "string", "description": "Usage tips, patterns that work, things to remember", "required": True},
        },
    },
    {
        "name": "update_knowledge",
        "description": "Correct or enrich the knowledge store for a page or region. Use when you find errors in sheet reflections, missing cross-references, or inaccurate region details.",
        "params": {
            "page_name": {"type": "string", "required": True},
            "field": {"type": "string", "description": "Field to update: sheet_reflection, index, cross_references, or content_markdown (for pointers)", "required": True},
            "value": {"type": "string", "description": "New or corrected content", "required": True},
            "region_id": {"type": "string", "description": "Target a specific pointer (required for content_markdown)", "required": False},
            "reasoning": {"type": "string", "description": "Why this correction is needed", "required": True},
        },
    },
]

# ---------------------------------------------------------------------------
# Load project and wire tools
# ---------------------------------------------------------------------------

project = load_project()
tools_v13.project = project
workspaces.init_workspaces(project)

all_tool_definitions = (
    tool_definitions
    + workspace_tool_definitions
    + vision_tool_definitions
    + learning_tool_definitions
)

tool_functions = dict(tools_v13.tool_functions)
tool_functions.update(workspace_tool_functions)


def _project_required() -> str | None:
    if project is None:
        return "No project loaded. Run: python ingest.py <folder>"
    return None


# --- Vision tool wrappers ---

def see_page_tool(page_name: str) -> Any:
    err = _project_required()
    if err:
        return err
    return see_page(page_name, project)


def see_pointer_tool(page_name: str, region_id: str) -> Any:
    err = _project_required()
    if err:
        return err
    return see_pointer(page_name, region_id, project)


def gemini_vision_agent_tool(page_name: str, mission: str) -> str:
    err = _project_required()
    if err:
        return err
    print(f"\n  [Gemini Vision] Page: {page_name} | Mission: {mission[:80]}...")
    return gemini_vision_agent(page_name, mission, project)


# --- Learning tool wrappers ---

def update_experience_tool(file: str, action: str, field: str, value: str, reasoning: str) -> str:
    print(f"\n  [Learn] update_experience: {file} → {field}")
    return update_experience(file, action, field, value, reasoning)


def update_tool_description_tool(tool_name: str, tips: str) -> str:
    print(f"\n  [Learn] update_tool_description: {tool_name}")
    return update_tool_description(tool_name, tips)


def update_knowledge_tool(page_name: str, field: str, value: str, reasoning: str, region_id: str | None = None) -> str:
    err = _project_required()
    if err:
        return err
    target = f"{page_name}/{region_id}" if region_id else page_name
    print(f"\n  [Learn] update_knowledge: {target} → {field}")
    return update_knowledge(page_name, field, value, reasoning, region_id=region_id, project=project)


tool_functions["see_page"] = see_page_tool
tool_functions["see_pointer"] = see_pointer_tool
tool_functions["gemini_vision_agent"] = gemini_vision_agent_tool
tool_functions["update_experience"] = update_experience_tool
tool_functions["update_tool_description"] = update_tool_description_tool
tool_functions["update_knowledge"] = update_knowledge_tool


# ---------------------------------------------------------------------------
# Tool result handling (supports multimodal content blocks)
# ---------------------------------------------------------------------------

def _stringify_result(result: Any) -> Any:
    """Convert tool result to content for Anthropic API.
    
    If result is a list of content blocks (multimodal), return as-is.
    Otherwise stringify for text-only tool results.
    """
    if isinstance(result, list) and result and isinstance(result[0], dict) and "type" in result[0]:
        return result  # Multimodal content blocks
    if isinstance(result, (dict, list)):
        return json.dumps(result, indent=2, ensure_ascii=True)
    return str(result)


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

            # Handle multimodal vs text tool results
            stringified = _stringify_result(result)
            if isinstance(stringified, list):
                # Multimodal content blocks (images + text)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": stringified,
                    }
                )
            else:
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": str(stringified),
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
    print(f"  Tools: {len(all_tool_definitions)} ({len(tool_definitions)} knowledge + {len(workspace_tool_definitions)} workspace + {len(vision_tool_definitions)} vision + {len(learning_tool_definitions)} learning)")
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
