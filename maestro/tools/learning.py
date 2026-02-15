# learning.py — Maestro's learning tools
#
# Direct-apply, real-time learning. No background worker.
# Experience file updates stay as file I/O (identity/experience/*.json).
# Audit log goes to DB via repository.
#
# Tools:
#   update_experience     — Modify experience JSON files (patterns, disciplines, etc.)
#   update_tool_description — Add usage tips for tools
#   update_knowledge      — Correct/enrich knowledge store pages and pointers
#
# Identity files (soul.json, tone.json) are on the denylist and cannot be modified.
# Everything in experience/ is fair game.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from maestro.db import repository as repo

IDENTITY_DIR = Path(__file__).resolve().parent.parent / "identity"
EXPERIENCE_DIR = IDENTITY_DIR / "experience"

# Denylist — these files cannot be modified by learning tools
DENYLIST = {"soul.json", "tone.json"}


# ---------------------------------------------------------------------------
# Changelog / Audit — now goes to DB
# ---------------------------------------------------------------------------

def _log_change(tool: str, details: dict[str, Any]) -> None:
    """Log to DB experience_log table."""
    repo.log_experience(tool, details)


# ---------------------------------------------------------------------------
# Tool: update_experience
# ---------------------------------------------------------------------------

def update_experience(file: str, action: str, field: str, value: str, reasoning: str) -> str:
    """Update an experience JSON file. Direct-apply, logged."""
    if Path(file).name in DENYLIST:
        return f"DENIED: {file} is read-only (identity file)"

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
        "file": file, "action": action, "field": field,
        "value": value[:500], "reasoning": reasoning, "result": result,
    })

    return result


# ---------------------------------------------------------------------------
# Tool: update_tool_description
# ---------------------------------------------------------------------------

def update_tool_description(tool_name: str, tips: str) -> str:
    """Add/update usage tips for a tool in experience/tools.json."""
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
        "tool_name": tool_name, "tips": tips[:500],
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

    Knowledge store stays as files — this tool modifies pass1.json / pass2.json
    on disk and updates the in-memory project dict.
    """
    if not project:
        return "No project loaded."

    page = project.get("pages", {}).get(page_name)
    if not page:
        return f"Page '{page_name}' not found"

    page_dir = Path(page.get("path", ""))

    if region_id and field == "content_markdown":
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
        pointer["content_markdown"] = value
        result = f"OK: updated {page_name}/{region_id} content_markdown"

    else:
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
        "page_name": page_name, "field": field, "region_id": region_id,
        "value": value[:500], "reasoning": reasoning, "result": result,
    })

    return result
