# prompt.py — Build Maestro's system prompt
#
# Assembles the system prompt from two sources:
#   1. Identity (static) — soul.json, tone.json (WHO Maestro is)
#   2. Experience (dynamic) — patterns, tools, disciplines (WHAT Maestro has learned)
#
# The prompt is rebuilt fresh for each conversation.
# Learning tools modify the experience files; the next prompt picks up changes.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

IDENTITY_DIR = Path(__file__).resolve().parent
EXPERIENCE_DIR = IDENTITY_DIR / "experience"


def load_identity() -> dict[str, Any]:
    """Load the static identity files (soul.json + tone.json).

    Returns a merged dict with name, role, purpose, boundaries, greeting, farewell,
    style, and communication principles.
    """
    identity: dict[str, Any] = {}

    soul_path = IDENTITY_DIR / "soul.json"
    if soul_path.exists():
        try:
            soul = json.loads(soul_path.read_text(encoding="utf-8"))
            identity.update(soul)
        except (json.JSONDecodeError, OSError):
            pass

    tone_path = IDENTITY_DIR / "tone.json"
    if tone_path.exists():
        try:
            tone = json.loads(tone_path.read_text(encoding="utf-8"))
            identity["style"] = tone.get("style", "")
            identity["principles"] = tone.get("principles", [])
        except (json.JSONDecodeError, OSError):
            pass

    return identity


def build_system_prompt() -> str:
    """Assemble Maestro's full system prompt from identity + experience."""
    parts: list[str] = []

    # --- Identity (static) ---
    identity = load_identity()
    if identity:
        name = identity.get("name", "Maestro")
        role = identity.get("role", "")
        parts.append(f"You are {name}. {role}.")
        if identity.get("purpose"):
            parts.append(identity["purpose"])
        if identity.get("boundaries"):
            parts.append(identity["boundaries"])
        if identity.get("style"):
            parts.append(f"\nCommunication: {identity['style']}")
        for principle in identity.get("principles", []):
            parts.append(f"- {principle}")

    # --- Experience (dynamic) ---

    # Tool strategy
    tools_path = EXPERIENCE_DIR / "tools.json"
    if tools_path.exists():
        try:
            tools = json.loads(tools_path.read_text(encoding="utf-8"))
            if tools.get("strategy"):
                parts.append(f"\nTool strategy: {tools['strategy']}")
            if tools.get("search_tips"):
                parts.append(f"Search: {tools['search_tips']}")
            if tools.get("vision_strategy"):
                parts.append(f"Vision: {tools['vision_strategy']}")
            if tools.get("learning_strategy"):
                parts.append(f"Learning: {tools['learning_strategy']}")
            if tools.get("gaps_strategy"):
                parts.append(f"Gaps: {tools['gaps_strategy']}")

            tool_tips = tools.get("tool_tips", {})
            if tool_tips:
                parts.append("\n### Tool Tips (learned from experience)")
                for tool_name, tips in tool_tips.items():
                    parts.append(f"- **{tool_name}**: {tips}")
        except (json.JSONDecodeError, OSError):
            pass

    # Discipline knowledge
    disc_dir = EXPERIENCE_DIR / "disciplines"
    if disc_dir.exists():
        for disc_file in sorted(disc_dir.glob("*.json")):
            try:
                disc = json.loads(disc_file.read_text(encoding="utf-8"))
                parts.append(f"\n### {disc.get('discipline', disc_file.stem)}")
                parts.append(f"Sheets: {', '.join(disc.get('sheet_prefixes', []))}")
                for item in disc.get("what_to_watch", []):
                    parts.append(f"- Watch: {item}")
                for lesson in disc.get("learned", []):
                    parts.append(f"- Learned: {lesson}")
            except (json.JSONDecodeError, OSError):
                pass

    # Patterns
    patterns_path = EXPERIENCE_DIR / "patterns.json"
    if patterns_path.exists():
        try:
            patterns = json.loads(patterns_path.read_text(encoding="utf-8"))
            if patterns.get("cross_discipline"):
                parts.append("\n### Cross-Discipline Patterns")
                for p in patterns["cross_discipline"]:
                    parts.append(f"- {p}")
            if patterns.get("project_specific"):
                parts.append("\n### Project-Specific")
                for p in patterns["project_specific"]:
                    parts.append(f"- {p}")
            if patterns.get("lessons_from_benchmarks"):
                parts.append("\n### Benchmark Lessons")
                for p in patterns["lessons_from_benchmarks"]:
                    parts.append(f"- {p}")
        except (json.JSONDecodeError, OSError):
            pass

    return "\n".join(parts)
