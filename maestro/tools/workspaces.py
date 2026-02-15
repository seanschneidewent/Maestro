# workspaces.py - Workspace management tools for Maestro V13 (DB-backed)

from __future__ import annotations

import re
from typing import Any, Callable

from maestro.db import repository as repo

_project: dict[str, Any] | None = None
_project_id: str | None = None


def init_workspaces(project: dict[str, Any] | None, project_id: str | None) -> None:
    """Initialize workspace tools with runtime project and project id."""
    global _project, _project_id
    _project = project
    _project_id = project_id


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "workspace"


def _normalize_token(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "_", value.lower())
    return re.sub(r"_+", "_", token).strip("_")


def _project_page_names() -> list[str]:
    if not _project:
        return []
    pages = _project.get("pages", {})
    if not isinstance(pages, dict):
        return []
    return sorted([name for name in pages.keys() if isinstance(name, str)])


def _resolve_candidate_name(query: str, candidates: list[str]) -> tuple[str | None, list[str]]:
    if not candidates:
        return None, []

    raw = query.strip()
    if not raw:
        return None, []

    if raw in candidates:
        return raw, []

    normalized_query = _normalize_token(raw)
    if not normalized_query:
        return None, []

    normalized = {name: _normalize_token(name) for name in candidates}

    prefix_matches = sorted([name for name in candidates if normalized[name].startswith(normalized_query)])
    if len(prefix_matches) == 1:
        return prefix_matches[0], []
    if len(prefix_matches) > 1:
        return None, prefix_matches

    substring_matches = sorted([name for name in candidates if normalized_query in normalized[name]])
    if len(substring_matches) == 1:
        return substring_matches[0], []
    if len(substring_matches) > 1:
        return None, substring_matches

    return None, []


def _resolve_project_page_name(page_name: str) -> tuple[str | None, list[str]]:
    return _resolve_candidate_name(page_name, _project_page_names())


def _resolve_workspace_slug(workspace_slug: str) -> str | None:
    if not _project_id:
        return None
    return repo.resolve_workspace_slug(_project_id, workspace_slug)


def _resolve_workspace_page_name(workspace_slug: str, page_name: str) -> tuple[str | None, list[str], str | None]:
    if not _project_id:
        return None, [], None

    slug = _resolve_workspace_slug(workspace_slug)
    if not slug:
        return None, [], None

    ws = repo.get_workspace(_project_id, slug)
    if not ws:
        return None, [], slug

    page_names = [str(item.get("page_name", "")) for item in ws.get("pages", []) if isinstance(item, dict)]
    resolved, ambiguous = _resolve_candidate_name(page_name, page_names)
    return resolved, ambiguous, slug


def _require_pid() -> str | None:
    if not _project_id:
        return None
    return _project_id


def create_workspace(title: str, description: str) -> dict[str, Any] | str:
    pid = _require_pid()
    if not pid:
        return "Workspace tools are not initialized with a project id."

    clean_title = title.strip() if isinstance(title, str) else ""
    clean_description = description.strip() if isinstance(description, str) else ""
    if not clean_title:
        return "Workspace title is required."
    if not clean_description:
        return "Workspace description is required."

    slug = _slugify(clean_title)
    return repo.create_workspace(pid, clean_title, clean_description, slug)


def list_workspaces() -> dict[str, Any] | str:
    pid = _require_pid()
    if not pid:
        return "Workspace tools are not initialized with a project id."
    return {"workspaces": repo.list_workspaces(pid)}


def get_workspace(workspace_slug: str) -> dict[str, Any] | str:
    pid = _require_pid()
    if not pid:
        return "Workspace tools are not initialized with a project id."

    slug = _resolve_workspace_slug(workspace_slug)
    if not slug:
        return f"Workspace '{workspace_slug}' not found."

    ws = repo.get_workspace(pid, slug)
    if not ws:
        return f"Workspace '{workspace_slug}' not found."
    return ws


def add_page(workspace_slug: str, page_name: str) -> dict[str, Any] | str:
    pid = _require_pid()
    if not pid:
        return "Workspace tools are not initialized with a project id."

    if _project is None:
        return "No project loaded. Run: python ingest.py <folder>"

    slug = _resolve_workspace_slug(workspace_slug)
    if not slug:
        return f"Workspace '{workspace_slug}' not found."

    resolved_page, ambiguous_pages = _resolve_project_page_name(page_name)
    if ambiguous_pages:
        matches = ", ".join(ambiguous_pages)
        return f"Page name '{page_name}' is ambiguous. Matches: {matches}"
    if not resolved_page:
        return f"Page '{page_name}' not found. Use list_pages() to see available pages."

    return repo.add_page(pid, slug, resolved_page)


def remove_page(workspace_slug: str, page_name: str) -> dict[str, Any] | str:
    pid = _require_pid()
    if not pid:
        return "Workspace tools are not initialized with a project id."

    resolved_page, ambiguous_pages, slug = _resolve_workspace_page_name(workspace_slug, page_name)
    if not slug:
        return f"Workspace '{workspace_slug}' not found."

    if ambiguous_pages:
        matches = ", ".join(ambiguous_pages)
        return f"Page name '{page_name}' is ambiguous in workspace '{slug}'. Matches: {matches}"
    if not resolved_page:
        return f"Page '{page_name}' is not in workspace '{slug}'."

    return repo.remove_page(pid, slug, resolved_page)


def add_note(workspace_slug: str, note_text: str, source_page: str | None = None) -> dict[str, Any] | str:
    pid = _require_pid()
    if not pid:
        return "Workspace tools are not initialized with a project id."

    slug = _resolve_workspace_slug(workspace_slug)
    if not slug:
        return f"Workspace '{workspace_slug}' not found."

    clean_note = note_text.strip() if isinstance(note_text, str) else ""
    if not clean_note:
        return "Note text is required."

    resolved_source: str | None = None
    if isinstance(source_page, str) and source_page.strip():
        if _project is not None:
            resolved, ambiguous = _resolve_project_page_name(source_page)
            if ambiguous:
                matches = ", ".join(ambiguous)
                return f"Source page '{source_page}' is ambiguous. Matches: {matches}"
            if not resolved:
                return f"Source page '{source_page}' not found. Use list_pages() to see available pages."
            resolved_source = resolved
        else:
            resolved_source = source_page.strip()

    return repo.add_note(pid, slug, clean_note, source_page=resolved_source)


def add_description(workspace_slug: str, page_name: str, description: str) -> dict[str, Any] | str:
    pid = _require_pid()
    if not pid:
        return "Workspace tools are not initialized with a project id."

    resolved_page, ambiguous_pages, slug = _resolve_workspace_page_name(workspace_slug, page_name)
    if not slug:
        return f"Workspace '{workspace_slug}' not found."

    if ambiguous_pages:
        matches = ", ".join(ambiguous_pages)
        return f"Page name '{page_name}' is ambiguous in workspace '{slug}'. Matches: {matches}"
    if not resolved_page:
        return f"Page '{page_name}' is not in workspace '{slug}'."

    clean_description = description.strip() if isinstance(description, str) else ""
    return repo.add_description(pid, slug, resolved_page, clean_description)


def remove_highlight(workspace_slug: str, page_name: str, highlight_id: int | str) -> dict[str, Any] | str:
    pid = _require_pid()
    if not pid:
        return "Workspace tools are not initialized with a project id."

    resolved_page, ambiguous_pages, slug = _resolve_workspace_page_name(workspace_slug, page_name)
    if not slug:
        return f"Workspace '{workspace_slug}' not found."

    if ambiguous_pages:
        matches = ", ".join(ambiguous_pages)
        return f"Page name '{page_name}' is ambiguous in workspace '{slug}'. Matches: {matches}"
    if not resolved_page:
        return f"Page '{page_name}' is not in workspace '{slug}'."

    try:
        parsed_highlight_id = int(highlight_id)
    except (TypeError, ValueError):
        return f"Invalid highlight id '{highlight_id}'."

    return repo.remove_highlight(pid, slug, resolved_page, parsed_highlight_id)


workspace_tool_definitions = [
    {
        "name": "create_workspace",
        "description": "Create a new workspace for a focused scope of work",
        "params": {
            "title": {"type": "string", "description": "Workspace title", "required": True},
            "description": {"type": "string", "description": "Workspace scope description", "required": True},
        },
    },
    {
        "name": "list_workspaces",
        "description": "List all workspaces with summary metadata",
        "params": {},
    },
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
            "source_page": {
                "type": "string",
                "description": "Optional source page name for the note",
                "required": False,
            },
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


workspace_tool_functions: dict[str, Callable[..., Any]] = {
    "create_workspace": create_workspace,
    "list_workspaces": list_workspaces,
    "get_workspace": get_workspace,
    "add_page": add_page,
    "remove_page": remove_page,
    "add_note": add_note,
    "add_description": add_description,
    "remove_highlight": remove_highlight,
}
