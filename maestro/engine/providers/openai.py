# openai.py — GPT API provider
#
# Translates between the engine's generic interface and OpenAI's Chat Completions API.
# Handles: function tool format, tool_call parsing, and the tool-use loop.

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def create_client() -> OpenAI:
    """Create an OpenAI API client."""
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def build_tool_schemas(tool_definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert generic tool definitions to OpenAI function tool format."""
    tools = []
    for tool in tool_definitions:
        tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": _json_schema_from_params(tool.get("params", {})),
            },
        })
    return tools


def send_message(
    client: OpenAI,
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
    # Ensure system prompt is first message
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": system_prompt})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
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

            result = _execute_tool(func_name, func_args, tool_functions)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": _stringify_result(result),
            })

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
        )
        message = response.choices[0].message

    content = message.content if message.content is not None else "No response"
    return messages, content


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


def _stringify_result(result: Any) -> str:
    if isinstance(result, (dict, list)):
        return json.dumps(result, indent=2, ensure_ascii=True)
    return str(result)
