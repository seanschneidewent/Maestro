# engine.py — Maestro's engine setup utilities
#
# Loads the project, wires tools, builds the system prompt.
# The actual conversation loop lives in messaging/conversation.py.
# The server entry point lives in server.py (root).
#
# This module provides setup functions that conversation.py and
# other layers use. It does NOT run a chat loop.

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.config import PROVIDERS, DEFAULT
from knowledge.loader import load_project
from identity.prompt import build_system_prompt, load_identity
from tools.registry import build_tool_registry


def setup(engine_name: str | None = None) -> dict[str, Any]:
    """Initialize Maestro's engine components.

    Returns a dict with everything needed to run conversations:
        {
            "engine_name": str,
            "provider_name": str,
            "model": str,
            "display": str,
            "project": dict | None,
            "tool_definitions": list,
            "tool_functions": dict,
            "system_prompt": str,
            "identity": dict,
        }
    """
    engine_name = engine_name or DEFAULT
    if engine_name not in PROVIDERS:
        raise ValueError(f"Unknown engine: {engine_name}. Available: {', '.join(PROVIDERS.keys())}")

    provider_config = PROVIDERS[engine_name]

    project = load_project()
    tool_definitions, tool_functions = build_tool_registry(project)
    identity = load_identity()
    system_prompt = build_system_prompt()

    return {
        "engine_name": engine_name,
        "provider_name": provider_config["provider"],
        "model": provider_config["model"],
        "display": provider_config["display"],
        "project": project,
        "tool_definitions": tool_definitions,
        "tool_functions": tool_functions,
        "system_prompt": system_prompt,
        "identity": identity,
    }
