# anthropic.py — Claude API provider
#
# Translates between the engine's generic interface and Anthropic's Messages API.
# Handles: tool schema conversion, message formatting, multimodal content blocks,
# and the tool_use loop.

from __future__ import annotations

import json
import os
from typing import Any

import anthropic
from dotenv import load_dotenv

load_dotenv()


def create_client() -> anthropic.Anthropic:
    """Create an Anthropic API client."""
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def build_tool_schemas(tool_definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert generic tool definitions to Anthropic's tool schema format."""
    tools = []
    for tool in tool_definitions:
        tools.append({
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": _json_schema_from_params(tool.get("params", {})),
        })
    return tools


def send_message(
    client: anthropic.Anthropic,
    model: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_functions: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    """Send a message and handle the full tool-use loop.

    Returns (updated_messages, final_text_response).
    Messages list is updated in place with assistant/tool turns.
    """
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        tools=tools,
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

            result = _execute_tool(func_name, func_args, tool_functions)
            stringified = _stringify_result(result)

            if isinstance(stringified, list):
                # Multimodal content blocks (images + text)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": stringified,
                })
            else:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": str(stringified),
                })

        # Serialize assistant content for next API call
        assistant_content = _serialize_content(response.content)
        messages.append({"role": "assistant", "content": assistant_content})
        messages.append({"role": "user", "content": tool_results})

        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

    # Extract final text
    final_text = ""
    for block in response.content:
        if hasattr(block, "text") and block.text:
            final_text = block.text
            break

    return messages, final_text or "No response"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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


def _execute_tool(func_name: str, func_args: dict, tool_functions: dict) -> Any:
    if func_name in tool_functions:
        try:
            return tool_functions[func_name](**func_args) if func_args else tool_functions[func_name]()
        except Exception as exc:
            return f"Tool execution error: {exc}"
    return f"Unknown function: {func_name}"


def _stringify_result(result: Any) -> Any:
    """Convert tool result to Anthropic content format.

    Multimodal results (list of content blocks with images) pass through.
    Everything else gets JSON-stringified.
    """
    if isinstance(result, list) and result and isinstance(result[0], dict):
        if result[0].get("type") in ("image", "text"):
            if any(item.get("type") == "image" for item in result):
                return result  # Multimodal content blocks
    if isinstance(result, (dict, list)):
        return json.dumps(result, indent=2, ensure_ascii=True)
    return str(result)


def _serialize_content(content: Any) -> list[dict[str, Any]]:
    """Serialize Anthropic response content blocks to dicts."""
    serialized = []
    for block in content:
        if block.type == "text":
            serialized.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            serialized.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
        elif block.type == "thinking":
            serialized.append({"type": "thinking", "thinking": block.thinking})
    return serialized
