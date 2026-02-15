# registry.py — Master tool registry
#
# Single source of truth for ALL tool definitions and function mappings.
# The engine imports this once. Tools never get defined in engine files.
#
# Each tool category lives in its own file:
#   - knowledge.py  — search, list, read from knowledge store
#   - vision.py     — see pages, generate Gemini workspace highlights
#   - workspaces.py — workspace CRUD (create, add page, notes, descriptions)
#   - learning.py   — update experience, tool tips, knowledge corrections

from __future__ import annotations

from typing import Any, Callable

from tools import knowledge, workspaces, schedule
from tools.vision import highlight_on_page, see_page
from tools.learning import update_experience, update_tool_description, update_knowledge


def build_tool_registry(
    project: dict[str, Any] | None,
    project_id: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Callable]]:
    """Build the complete tool registry for the engine.

    Returns (tool_definitions, tool_functions) where:
        tool_definitions = list of dicts describing each tool (name, description, params)
        tool_functions = dict mapping tool name → callable

    All tool functions receive their arguments directly from the model.
    Project-dependent tools get the project wired in via closures.
    """
    # Initialize modules that need the project reference
    knowledge.project = project
    workspaces.init_workspaces(project, project_id)
    schedule.init_schedule(project_id=project_id)

    # --- Build function map ---
    functions: dict[str, Callable] = {}

    # Knowledge tools
    functions.update(knowledge.tool_functions)

    # Workspace tools
    functions.update(workspaces.workspace_tool_functions)

    # Vision tools (wrapped with project)
    def _see_page(page_name: str) -> Any:
        if not project:
            return [{"type": "text", "text": "No project loaded."}]
        return see_page(page_name, project)

    def _highlight_on_page(workspace_slug: str, page_name: str, mission: str) -> dict[str, Any] | str:
        if not project:
            return "No project loaded."
        print(f"\n  [Highlight] Workspace: {workspace_slug} | Page: {page_name} | Mission: {mission[:80]}...")
        return highlight_on_page(
            workspace_slug=workspace_slug,
            page_name=page_name,
            mission=mission,
            project=project,
            project_id=project_id,
        )

    functions["see_page"] = _see_page
    functions["highlight_on_page"] = _highlight_on_page

    # Learning tools (wrapped with project for update_knowledge)
    def _update_experience(file: str, action: str, field: str, value: str, reasoning: str) -> str:
        print(f"\n  [Learn] update_experience: {file} → {field}")
        return update_experience(file, action, field, value, reasoning)

    def _update_tool_description(tool_name: str, tips: str) -> str:
        print(f"\n  [Learn] update_tool_description: {tool_name}")
        return update_tool_description(tool_name, tips)

    def _update_knowledge(page_name: str, field: str, value: str, reasoning: str, region_id: str | None = None) -> str:
        if not project:
            return "No project loaded."
        target = f"{page_name}/{region_id}" if region_id else page_name
        print(f"\n  [Learn] update_knowledge: {target} → {field}")
        return update_knowledge(page_name, field, value, reasoning, region_id=region_id, project=project)

    functions["update_experience"] = _update_experience
    functions["update_tool_description"] = _update_tool_description
    functions["update_knowledge"] = _update_knowledge

    # Schedule tools
    functions["list_events"] = schedule.list_events
    functions["get_event"] = schedule.get_event
    functions["add_event"] = schedule.add_event
    functions["update_event"] = schedule.update_event
    functions["remove_event"] = schedule.remove_event
    functions["upcoming"] = schedule.upcoming

    # --- Build definitions list ---
    definitions = (
        KNOWLEDGE_TOOL_DEFINITIONS
        + WORKSPACE_TOOL_DEFINITIONS
        + VISION_TOOL_DEFINITIONS
        + LEARNING_TOOL_DEFINITIONS
        + SCHEDULE_TOOL_DEFINITIONS
    )

    return definitions, functions


# ==========================================================================
# Tool Definitions — the model sees these as available tools
# ==========================================================================

KNOWLEDGE_TOOL_DEFINITIONS = [
    {"name": "list_disciplines", "description": "List all disciplines in the project", "params": {}},
    {
        "name": "list_pages",
        "description": "List all pages, optionally filtered by discipline",
        "params": {
            "discipline": {"type": "string", "description": "Filter by discipline name", "required": False},
        },
    },
    {
        "name": "get_sheet_summary",
        "description": "Get the superintendent briefing for a page",
        "params": {"page_name": {"type": "string", "required": True}},
    },
    {
        "name": "get_sheet_index",
        "description": "Get the searchable index for a page (keywords, materials, cross-refs)",
        "params": {"page_name": {"type": "string", "required": True}},
    },
    {
        "name": "list_regions",
        "description": "List all detail regions on a page",
        "params": {"page_name": {"type": "string", "required": True}},
    },
    {
        "name": "get_region_detail",
        "description": "Get the deep technical brief for a region/pointer",
        "params": {
            "page_name": {"type": "string", "required": True},
            "region_id": {"type": "string", "required": True},
        },
    },
    {
        "name": "search",
        "description": "Search all pages and pointers for a keyword, material, or term",
        "params": {"query": {"type": "string", "required": True}},
    },
    {
        "name": "find_cross_references",
        "description": "Find what sheets reference a page and what it references",
        "params": {"page_name": {"type": "string", "required": True}},
    },
    {
        "name": "list_modifications",
        "description": "List all install/demolish/protect items across the project",
        "params": {},
    },
    {
        "name": "check_gaps",
        "description": "Find broken cross-references and regions missing deep analysis",
        "params": {},
    },
]

WORKSPACE_TOOL_DEFINITIONS = [
    {
        "name": "create_workspace",
        "description": "Create a new workspace for a focused scope of work",
        "params": {
            "title": {"type": "string", "description": "Workspace title", "required": True},
            "description": {"type": "string", "description": "Workspace scope description", "required": True},
        },
    },
    {"name": "list_workspaces", "description": "List all workspaces with summary metadata", "params": {}},
    {
        "name": "get_workspace",
        "description": "Get full workspace state including metadata, pages, and notes",
        "params": {"workspace_slug": {"type": "string", "required": True}},
    },
    {
        "name": "add_page",
        "description": "Add a knowledge-store page reference to a workspace",
        "params": {
            "workspace_slug": {"type": "string", "required": True},
            "page_name": {"type": "string", "required": True},
        },
    },
    {
        "name": "remove_page",
        "description": "Remove a page reference from a workspace",
        "params": {
            "workspace_slug": {"type": "string", "required": True},
            "page_name": {"type": "string", "required": True},
        },
    },
    {
        "name": "add_note",
        "description": "Add a note or observation to a workspace",
        "params": {
            "workspace_slug": {"type": "string", "required": True},
            "note_text": {"type": "string", "required": True},
            "source_page": {"type": "string", "description": "Optional source page name", "required": False},
        },
    },
    {
        "name": "add_description",
        "description": "Set or clear a page description within a workspace",
        "params": {
            "workspace_slug": {"type": "string", "required": True},
            "page_name": {"type": "string", "required": True},
            "description": {"type": "string", "required": True},
        },
    },
    {
        "name": "remove_highlight",
        "description": "Remove a generated highlight layer from a workspace page",
        "params": {
            "workspace_slug": {"type": "string", "required": True},
            "page_name": {"type": "string", "required": True},
            "highlight_id": {"type": "string", "required": True},
        },
    },
]

VISION_TOOL_DEFINITIONS = [
    {
        "name": "see_page",
        "description": "Look at the full page image yourself to visually inspect it.",
        "params": {"page_name": {"type": "string", "required": True}},
    },
    {
        "name": "highlight_on_page",
        "description": "Generate a Gemini visual highlight layer for a page already in a workspace. Use this when you need to visually mark findings tied to a specific mission.",
        "params": {
            "workspace_slug": {"type": "string", "required": True},
            "page_name": {"type": "string", "required": True},
            "mission": {"type": "string", "description": "What to highlight and why", "required": True},
        },
    },
]

LEARNING_TOOL_DEFINITIONS = [
    {
        "name": "update_experience",
        "description": "Update Maestro's experience files. Use to record lessons learned, refine discipline knowledge, or update behavioral patterns. Identity files (soul.json, tone.json) are read-only.",
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

SCHEDULE_TOOL_DEFINITIONS = [
    {
        "name": "list_events",
        "description": "List schedule events, optionally filtered by date range or type",
        "params": {
            "from_date": {"type": "string", "description": "Start of range (YYYY-MM-DD)", "required": False},
            "to_date": {"type": "string", "description": "End of range (YYYY-MM-DD)", "required": False},
            "event_type": {"type": "string", "description": "Filter by type (milestone, phase, inspection, delivery)", "required": False},
        },
    },
    {
        "name": "get_event",
        "description": "Get details for a specific schedule event",
        "params": {"event_id": {"type": "string", "required": True}},
    },
    {
        "name": "add_event",
        "description": "Add a new event to the construction schedule",
        "params": {
            "title": {"type": "string", "description": "Event name (e.g. Foundation Pour, Kitchen Rough-In)", "required": True},
            "start": {"type": "string", "description": "Start date (YYYY-MM-DD or YYYY-MM-DDTHH:MM)", "required": True},
            "end": {"type": "string", "description": "End date. Defaults to same as start.", "required": False},
            "event_type": {"type": "string", "description": "milestone, phase, inspection, delivery, meeting", "required": False},
            "notes": {"type": "string", "description": "Additional context", "required": False},
        },
    },
    {
        "name": "update_event",
        "description": "Update an existing schedule event. Only provided fields are changed.",
        "params": {
            "event_id": {"type": "string", "required": True},
            "title": {"type": "string", "required": False},
            "start": {"type": "string", "required": False},
            "end": {"type": "string", "required": False},
            "event_type": {"type": "string", "required": False},
            "notes": {"type": "string", "required": False},
        },
    },
    {
        "name": "remove_event",
        "description": "Remove an event from the schedule",
        "params": {"event_id": {"type": "string", "required": True}},
    },
    {
        "name": "upcoming",
        "description": "Quick view of schedule events in the next N days. Great for morning briefings.",
        "params": {
            "days": {"type": "string", "description": "How many days ahead to look (default 7)", "required": False},
        },
    },
]
