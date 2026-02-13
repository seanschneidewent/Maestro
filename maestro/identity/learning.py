# learning.py — Maestro's Learning System V2
# Direct-apply, real-time learning tools. No background worker.
# Tools: update_experience, update_tool_description, update_knowledge

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

EXPERIENCE_DIR = Path(__file__).resolve().parent / "experience"
LEARNING_LOG = EXPERIENCE_DIR / "learning_log.json"

# Denylist — these files cannot be modified
DENYLIST = {"soul.json"}


# ---------------------------------------------------------------------------
# Changelog / Audit
# ---------------------------------------------------------------------------

def _log_change(tool: str, details: dict[str, Any]) -> None:
    """Append to learning_log.json."""
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tool": tool,
        **details,
    }
    log = []
    if LEARNING_LOG.exists():
        try:
            log = json.loads(LEARNING_LOG.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            log = []
    log.append(entry)
    LEARNING_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Tool: update_experience
# ---------------------------------------------------------------------------

def update_experience(file: str, action: str, field: str, value: str, reasoning: str) -> str:
    """Update an experience JSON file. Direct-apply, logged.
    
    Args:
        file: Relative path within experience/ (e.g. "disciplines/kitchen.json")
        action: "append_to_list" or "set_field"
        field: Field name to modify
        value: Value to append or set
        reasoning: Why this update matters
    """
    # Denylist check
    if Path(file).name in DENYLIST:
        return f"DENIED: {file} is read-only"

    target = EXPERIENCE_DIR / file
    if not target.exists():
        return f"NOT FOUND: {file} does not exist in experience/"

    if not target.suffix == ".json":
        return f"SKIP: {file} is not a JSON file"

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return f"ERROR reading {file}: {exc}"

    result = ""

    if action == "append_to_list":
        if not isinstance(data.get(field), list):
            data[field] = []
        if value and value not in data[field]:
            data[field].append(value)
            result = f"OK: appended to {file} → {field}[]"
        else:
            result = f"SKIP: duplicate or empty value for {file} → {field}"

    elif action == "set_field":
        if field:
            # Try to parse value as JSON for structured data
            try:
                parsed = json.loads(value)
                data[field] = parsed
            except (json.JSONDecodeError, TypeError):
                data[field] = value
            result = f"OK: set {file} → {field}"
        else:
            result = f"SKIP: no field specified"

    else:
        result = f"SKIP: unknown action '{action}'"

    if result.startswith("OK"):
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    _log_change("update_experience", {
        "file": file,
        "action": action,
        "field": field,
        "value": value[:500],
        "reasoning": reasoning,
        "result": result,
    })

    return result


# ---------------------------------------------------------------------------
# Tool: update_tool_description
# ---------------------------------------------------------------------------

def update_tool_description(tool_name: str, tips: str) -> str:
    """Add/update usage tips for a tool in experience/tools.json.
    
    These tips are injected into the system prompt to guide future tool use.
    """
    tools_path = EXPERIENCE_DIR / "tools.json"
    if not tools_path.exists():
        return "NOT FOUND: tools.json missing"

    try:
        data = json.loads(tools_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return f"ERROR reading tools.json: {exc}"

    if "tool_tips" not in data:
        data["tool_tips"] = {}

    data["tool_tips"][tool_name] = tips
    tools_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    _log_change("update_tool_description", {
        "tool_name": tool_name,
        "tips": tips[:500],
        "result": f"OK: updated tips for {tool_name}",
    })

    return f"OK: updated tips for {tool_name}"


# ---------------------------------------------------------------------------
# Tool: update_knowledge
# ---------------------------------------------------------------------------

def update_knowledge(
    page_name: str,
    field: str,
    value: str,
    reasoning: str,
    region_id: str | None = None,
    project: dict[str, Any] | None = None,
) -> str:
    """Patch the knowledge store for a page or region. Direct-apply.
    
    Args:
        page_name: Which page to update
        field: What to update — sheet_reflection, index, regions, or content_markdown (for pointers)
        value: New or corrected content
        reasoning: Why this correction is needed
        region_id: Target a specific pointer (required for content_markdown)
        project: The in-memory project dict (updated in-place)
    """
    if not project:
        return "No project loaded."

    page = project.get("pages", {}).get(page_name)
    if not page:
        return f"Page '{page_name}' not found"

    page_dir = Path(page.get("path", ""))

    # Determine which file to patch
    if region_id and field == "content_markdown":
        # Patch pointer pass2.json
        pointer = page.get("pointers", {}).get(region_id)
        if not pointer:
            return f"Region '{region_id}' not found on '{page_name}'"

        pass2_path = page_dir / "pointers" / region_id / "pass2.json"
        if not pass2_path.exists():
            return f"No pass2.json for region '{region_id}'"

        try:
            data = json.loads(pass2_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return f"ERROR reading pass2.json: {exc}"

        data["content_markdown"] = value
        pass2_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        # Update in-memory
        pointer["content_markdown"] = value

        result = f"OK: updated {page_name}/{region_id} content_markdown"

    else:
        # Patch page pass1.json
        pass1_path = page_dir / "pass1.json"
        if not pass1_path.exists():
            return f"No pass1.json for page '{page_name}'"

        try:
            data = json.loads(pass1_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return f"ERROR reading pass1.json: {exc}"

        if field == "sheet_reflection":
            data["sheet_reflection"] = value
            page["sheet_reflection"] = value
            result = f"OK: updated {page_name} sheet_reflection"

        elif field == "index":
            # Merge index updates
            try:
                index_update = json.loads(value)
                if isinstance(index_update, dict):
                    if not isinstance(data.get("index"), dict):
                        data["index"] = {}
                    data["index"].update(index_update)
                    page["index"].update(index_update)
                    result = f"OK: merged {page_name} index"
                else:
                    result = "SKIP: index value must be a JSON object"
            except json.JSONDecodeError:
                result = "SKIP: index value must be valid JSON"

        elif field == "cross_references":
            # Append cross references
            try:
                new_refs = json.loads(value)
                if isinstance(new_refs, list):
                    existing = data.get("cross_references", [])
                    if not isinstance(existing, list):
                        existing = []
                    existing.extend(new_refs)
                    data["cross_references"] = existing
                    page["cross_references"] = existing
                    result = f"OK: added cross_references to {page_name}"
                else:
                    result = "SKIP: cross_references value must be a JSON array"
            except json.JSONDecodeError:
                result = "SKIP: cross_references value must be valid JSON"

        else:
            result = f"SKIP: unknown field '{field}' for page update"

        if result.startswith("OK"):
            pass1_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    _log_change("update_knowledge", {
        "page_name": page_name,
        "field": field,
        "region_id": region_id,
        "value": value[:500],
        "reasoning": reasoning,
        "result": result,
    })

    return result


# ---------------------------------------------------------------------------
# System Prompt Builder (kept from V1)
# ---------------------------------------------------------------------------

def _read_experience_tree() -> dict[str, Any]:
    """Read the full experience tree into a dict."""
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
        prompt_parts.append(f"Learning: {tools.get('learning_strategy', '')}")
        prompt_parts.append(f"Gaps: {tools.get('gaps_strategy', '')}")

        # Inject tool tips if they exist
        tool_tips = tools.get("tool_tips", {})
        if tool_tips:
            prompt_parts.append("\n### Tool Tips (learned from experience)")
            for tool_name, tips in tool_tips.items():
                prompt_parts.append(f"- **{tool_name}**: {tips}")

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
