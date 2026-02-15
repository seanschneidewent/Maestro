# google.py — Gemini API provider
#
# Translates between the engine's generic interface and Google's Gemini API.
# Handles: function declaration format, FunctionResponse protos,
# multi-call batching, and the tool-use loop.

from __future__ import annotations

import json
import os
from typing import Any

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()


def create_client() -> None:
    """Configure the Gemini API client. Returns None (genai uses global config)."""
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def build_tool_schemas(tool_definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert generic tool definitions to Gemini function declaration format."""
    function_declarations = []
    for tool in tool_definitions:
        function_declarations.append({
            "name": tool["name"],
            "description": tool["description"],
            "parameters": _json_schema_from_params(tool.get("params", {})),
        })
    return [{"function_declarations": function_declarations}]


def create_chat(model: str, system_prompt: str, tools: list[dict[str, Any]]) -> Any:
    """Create a Gemini chat session."""
    gemini_model = genai.GenerativeModel(
        model,
        tools=tools,
        system_instruction=system_prompt,
    )
    return gemini_model.start_chat()


def send_message(
    chat: Any,
    model: str,
    system_prompt: str,
    message: str,
    tools: list[dict[str, Any]],
    tool_functions: dict[str, Any],
) -> str:
    """Send a message and handle the full tool-use loop.

    Returns the final text response.
    Note: Gemini uses a stateful chat object, not a messages list.
    """
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

            result = _execute_tool(func_name, func_args, tool_functions)

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

    # Extract final text
    final_candidates = getattr(response, "candidates", None) or []
    final_parts = (
        getattr(getattr(final_candidates[0], "content", None), "parts", [])
        if final_candidates else []
    )
    for part in final_parts:
        if getattr(part, "text", None):
            return part.text
    return "No response"


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
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _execute_tool(func_name: str, func_args: dict, tool_functions: dict) -> Any:
    if func_name in tool_functions:
        try:
            result = tool_functions[func_name](**func_args) if func_args else tool_functions[func_name]()
            # Gemini doesn't support multimodal tool results — convert images to text
            if isinstance(result, list) and result and isinstance(result[0], dict):
                if any(item.get("type") == "image" for item in result):
                    return "Image returned. Gemini cannot view images in tool results — use highlight_on_page for visual overlays."
            return result
        except Exception as exc:
            return f"Tool execution error: {exc}"
    return f"Unknown function: {func_name}"


def _stringify_result(result: Any) -> str:
    if isinstance(result, (dict, list)):
        return json.dumps(result, indent=2, ensure_ascii=True)
    return str(result)
