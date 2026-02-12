# learning.py — Maestro's Learning Harness V2
# GPT 5.2 powered, JSON-based, hierarchical experience updates

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

LEARNING_MODEL = "gpt-5.2"
EXPERIENCE_DIR = Path(__file__).resolve().parent / "experience"
LEARNING_LOG = EXPERIENCE_DIR / "learning_log.json"


def _get_client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _read_experience_tree() -> dict[str, Any]:
    """Read the full experience tree into a dict for the learning agent."""
    tree = {}

    for json_file in sorted(EXPERIENCE_DIR.rglob("*.json")):
        if json_file.name == "learning_log.json":
            continue
        rel = json_file.relative_to(EXPERIENCE_DIR).as_posix()
        try:
            tree[rel] = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            tree[rel] = {"_error": f"Could not read {rel}"}

    return tree


def _apply_update(update: dict[str, Any]) -> str:
    """Apply a single update from the learning agent.

    Supported actions:
      - append_to_learned: append a string to the 'learned' array
      - append_to_list: append a string to any named list field
      - set_field: set a specific field to a value
    """
    file_rel = update.get("file", "")
    action = update.get("action", "")
    target_path = EXPERIENCE_DIR / file_rel

    if not target_path.exists():
        return f"SKIP: {file_rel} does not exist"

    if not target_path.suffix == ".json":
        return f"SKIP: {file_rel} is not a JSON file"

    try:
        data = json.loads(target_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return f"ERROR reading {file_rel}: {exc}"

    result = ""

    if action == "append_to_learned":
        value = update.get("value", "")
        if not isinstance(data.get("learned"), list):
            data["learned"] = []
        if value and value not in data["learned"]:
            data["learned"].append(value)
            result = f"OK: appended to {file_rel} learned[]"
        else:
            result = f"SKIP: duplicate or empty value for {file_rel}"

    elif action == "append_to_list":
        field = update.get("field", "")
        value = update.get("value", "")
        if isinstance(data.get(field), list):
            if value and value not in data[field]:
                data[field].append(value)
                result = f"OK: appended to {file_rel} {field}[]"
            else:
                result = f"SKIP: duplicate or empty for {file_rel} {field}"
        else:
            result = f"SKIP: {field} is not a list in {file_rel}"

    elif action == "set_field":
        field = update.get("field", "")
        value = update.get("value")
        if field:
            data[field] = value
            result = f"OK: set {file_rel} {field}"
        else:
            result = f"SKIP: no field specified for set_field"

    else:
        result = f"SKIP: unknown action '{action}'"

    if result.startswith("OK"):
        target_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    return result


def _log_learning(trigger: str, context: dict[str, Any], updates: list[dict], results: list[str]) -> None:
    """Append to learning_log.json."""
    log_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "trigger": trigger,
        "context_summary": context.get("query", "")[:200],
        "model": LEARNING_MODEL,
        "updates": updates,
        "results": results,
    }

    log = []
    if LEARNING_LOG.exists():
        try:
            log = json.loads(LEARNING_LOG.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            log = []

    log.append(log_entry)
    LEARNING_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


def learn(learning_mission: str, context: dict[str, Any] | None = None) -> str:
    """Main learning entry point. Called as a Maestro tool or by the benchmark harness.

    Args:
        learning_mission: What to learn / what went wrong / feedback from superintendent.
        context: Optional dict with 'query', 'response', 'engine', 'grounding_score', etc.

    Returns:
        Summary of what was learned and updated.
    """
    if context is None:
        context = {}

    client = _get_client()
    experience_tree = _read_experience_tree()

    system_prompt = """You are Maestro's learning agent. Your job is to analyze feedback, benchmark results, 
or self-corrections and decide how to improve Maestro's experience.

You have access to Maestro's full experience tree (hierarchical JSON files).
You must output a JSON object with an 'updates' array. Each update has:
- "file": relative path within experience/ (e.g. "disciplines/architectural.json")
- "action": one of "append_to_learned", "append_to_list", "set_field"
- "field": (for append_to_list/set_field) which field to modify
- "value": what to add or set
- "reasoning": why this update matters

Rules:
- Be specific. "Be better at dimensions" is useless. "When asked about egress, always quote the exact travel distances from the plan" is useful.
- Don't duplicate existing lessons. Read the current learned[] arrays first.
- Target the right file. Architectural lessons go in disciplines/architectural.json. Cross-cutting insights go in patterns.json.
- Keep lessons actionable for a construction superintendent context.
- Output ONLY valid JSON. No markdown, no explanation outside the JSON."""

    user_message = f"""LEARNING MISSION: {learning_mission}

CONTEXT:
{json.dumps(context, indent=2, default=str)[:3000]}

CURRENT EXPERIENCE TREE:
{json.dumps(experience_tree, indent=2, ensure_ascii=False)[:6000]}

Analyze and output your updates as JSON."""

    try:
        response = client.chat.completions.create(
            model=LEARNING_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        parsed = json.loads(raw)
        updates = parsed.get("updates", [])

    except Exception as exc:
        error_msg = f"Learning agent error: {type(exc).__name__}: {exc}"
        _log_learning("error", context, [], [error_msg])
        return error_msg

    # Apply updates
    results = []
    for update in updates:
        result = _apply_update(update)
        results.append(result)
        print(f"  [LEARN] {result}")

    # Log everything
    _log_learning(context.get("trigger", "explicit"), context, updates, results)

    # Build summary
    applied = [r for r in results if r.startswith("OK")]
    skipped = [r for r in results if r.startswith("SKIP")]

    summary = f"Learning complete: {len(applied)} updates applied, {len(skipped)} skipped."
    if applied:
        summary += "\nApplied:\n" + "\n".join(f"  - {r}" for r in applied)

    return summary


def build_system_prompt() -> str:
    """Assemble Maestro's system prompt from the hierarchical experience tree."""
    prompt_parts: list[str] = []

    # Soul
    soul_path = EXPERIENCE_DIR / "soul.json"
    if soul_path.exists():
        soul = json.loads(soul_path.read_text(encoding="utf-8"))
        prompt_parts.append(f"You are {soul.get('name', 'Maestro')}. {soul.get('role', '')}.")
        prompt_parts.append(soul.get("purpose", ""))
        prompt_parts.append(soul.get("boundaries", ""))

    # Tone
    tone_path = EXPERIENCE_DIR / "tone.json"
    if tone_path.exists():
        tone = json.loads(tone_path.read_text(encoding="utf-8"))
        prompt_parts.append(f"\nCommunication: {tone.get('style', '')}")
        for principle in tone.get("principles", []):
            prompt_parts.append(f"- {principle}")

    # Tools strategy
    tools_path = EXPERIENCE_DIR / "tools.json"
    if tools_path.exists():
        tools = json.loads(tools_path.read_text(encoding="utf-8"))
        prompt_parts.append(f"\nTool strategy: {tools.get('strategy', '')}")
        prompt_parts.append(f"Search: {tools.get('search_tips', '')}")
        prompt_parts.append(f"Vision: {tools.get('vision_strategy', '')}")
        prompt_parts.append(f"Gaps: {tools.get('gaps_strategy', '')}")

    # Discipline knowledge
    disc_dir = EXPERIENCE_DIR / "disciplines"
    if disc_dir.exists():
        for disc_file in sorted(disc_dir.glob("*.json")):
            disc = json.loads(disc_file.read_text(encoding="utf-8"))
            prompt_parts.append(f"\n### {disc.get('discipline', disc_file.stem)}")
            prompt_parts.append(f"Sheets: {', '.join(disc.get('sheet_prefixes', []))}")
            for item in disc.get("what_to_watch", []):
                prompt_parts.append(f"- Watch: {item}")
            for lesson in disc.get("learned", []):
                prompt_parts.append(f"- Learned: {lesson}")

    # Patterns
    patterns_path = EXPERIENCE_DIR / "patterns.json"
    if patterns_path.exists():
        patterns = json.loads(patterns_path.read_text(encoding="utf-8"))
        if patterns.get("cross_discipline"):
            prompt_parts.append("\n### Cross-Discipline Patterns")
            for p in patterns["cross_discipline"]:
                prompt_parts.append(f"- {p}")
        if patterns.get("project_specific"):
            prompt_parts.append("\n### Project-Specific")
            for p in patterns["project_specific"]:
                prompt_parts.append(f"- {p}")
        if patterns.get("lessons_from_benchmarks"):
            prompt_parts.append("\n### Benchmark Lessons")
            for p in patterns["lessons_from_benchmarks"]:
                prompt_parts.append(f"- {p}")

    return "\n".join(prompt_parts)
