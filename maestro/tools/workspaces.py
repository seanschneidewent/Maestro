# workspaces.py - Workspace management tools for Maestro V13

from __future__ import annotations

import copy
import json
import re
import time
from pathlib import Path
from typing import Any, Callable

WORKSPACES_DIR = Path(__file__).resolve().parents[2] / "workspaces"
WORKSPACES_INDEX_PATH = WORKSPACES_DIR / "workspaces.json"

_project: dict[str, Any] | None = None


def init_workspaces(project: dict[str, Any] | None) -> None:
    """Initialize workspace module with the currently loaded project."""
    global _project
    _project = project


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "workspace"


def _normalize_token(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "_", value.lower())
    return re.sub(r"_+", "_", token).strip("_")


def _read_json_default(path: Path, default: Any) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return copy.deepcopy(default)
    if isinstance(default, dict) and isinstance(data, dict):
        return data
    if isinstance(default, list) and isinstance(data, list):
        return data
    return copy.deepcopy(default)


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)
    tmp_path.replace(path)


def _load_index() -> dict[str, list[dict[str, Any]]]:
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    if not WORKSPACES_INDEX_PATH.exists():
        _write_json_atomic(WORKSPACES_INDEX_PATH, {"workspaces": []})

    raw = _read_json_default(WORKSPACES_INDEX_PATH, {"workspaces": []})
    items = raw.get("workspaces", []) if isinstance(raw, dict) else []
    if not isinstance(items, list):
        items = []

    cleaned: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug", "")).strip()
        title = str(item.get("title", "")).strip()
        if not slug or not title or slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        created = str(item.get("created", "")).strip()
        updated = str(item.get("updated", "")).strip()
        try:
            page_count = int(item.get("page_count", 0))
        except (TypeError, ValueError):
            page_count = 0
        cleaned.append(
            {
                "slug": slug,
                "title": title,
                "page_count": max(page_count, 0),
                "created": created,
                "updated": updated,
            }
        )

    return {"workspaces": cleaned}


def _save_index(index: dict[str, list[dict[str, Any]]]) -> None:
    _write_json_atomic(WORKSPACES_INDEX_PATH, index)


def _find_index_entry(index: dict[str, list[dict[str, Any]]], slug: str) -> dict[str, Any] | None:
    for entry in index.get("workspaces", []):
        if entry.get("slug") == slug:
            return entry
    return None


def _resolve_workspace_slug(workspace_slug: str, index: dict[str, list[dict[str, Any]]]) -> str | None:
    raw = workspace_slug.strip()
    if not raw:
        return None

    entries = index.get("workspaces", [])
    exact = [entry["slug"] for entry in entries if entry.get("slug") == raw]
    if len(exact) == 1:
        return exact[0]

    slugified = _slugify(raw)
    slugified_matches = [entry["slug"] for entry in entries if entry.get("slug") == slugified]
    if len(slugified_matches) == 1:
        return slugified_matches[0]

    title_matches = [entry["slug"] for entry in entries if str(entry.get("title", "")).strip().lower() == raw.lower()]
    if len(title_matches) == 1:
        return title_matches[0]

    return None


def _workspace_paths(slug: str) -> dict[str, Path]:
    workspace_dir = WORKSPACES_DIR / slug
    return {
        "dir": workspace_dir,
        "workspace": workspace_dir / "workspace.json",
        "pages": workspace_dir / "pages.json",
        "notes": workspace_dir / "notes.json",
        "annotations": workspace_dir / "annotations",
    }


def _ensure_workspace_files(slug: str, title: str, description: str) -> None:
    paths = _workspace_paths(slug)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    paths["annotations"].mkdir(parents=True, exist_ok=True)

    now = _now_iso()
    metadata_default = {
        "title": title,
        "slug": slug,
        "description": description,
        "created": now,
        "updated": now,
        "status": "active",
    }
    metadata = _read_json_default(paths["workspace"], metadata_default)
    if not isinstance(metadata, dict):
        metadata = metadata_default
    changed = not paths["workspace"].exists()
    for key, fallback in metadata_default.items():
        value = metadata.get(key)
        if key == "status":
            if value not in {"active", "archived"}:
                metadata[key] = "active"
                changed = True
            continue
        if value is None or str(value).strip() == "":
            metadata[key] = fallback
            changed = True
    if changed:
        _write_json_atomic(paths["workspace"], metadata)

    pages = _read_json_default(paths["pages"], {"pages": []})
    if not isinstance(pages, dict) or not isinstance(pages.get("pages"), list):
        pages = {"pages": []}
        _write_json_atomic(paths["pages"], pages)
    elif not paths["pages"].exists():
        _write_json_atomic(paths["pages"], pages)

    notes = _read_json_default(paths["notes"], {"notes": []})
    if not isinstance(notes, dict) or not isinstance(notes.get("notes"), list):
        notes = {"notes": []}
        _write_json_atomic(paths["notes"], notes)
    elif not paths["notes"].exists():
        _write_json_atomic(paths["notes"], notes)


def _read_workspace_state(slug: str) -> dict[str, Any]:
    paths = _workspace_paths(slug)
    metadata = _read_json_default(paths["workspace"], {})
    pages_payload = _read_json_default(paths["pages"], {"pages": []})
    notes_payload = _read_json_default(paths["notes"], {"notes": []})

    pages = pages_payload.get("pages", []) if isinstance(pages_payload, dict) else []
    notes = notes_payload.get("notes", []) if isinstance(notes_payload, dict) else []
    if not isinstance(pages, list):
        pages = []
    if not isinstance(notes, list):
        notes = []

    return {
        "metadata": metadata if isinstance(metadata, dict) else {},
        "pages": pages,
        "notes": notes,
    }


def _save_workspace_metadata(slug: str, metadata: dict[str, Any]) -> None:
    paths = _workspace_paths(slug)
    _write_json_atomic(paths["workspace"], metadata)


def _save_workspace_pages(slug: str, pages: list[dict[str, Any]]) -> None:
    paths = _workspace_paths(slug)
    _write_json_atomic(paths["pages"], {"pages": pages})


def _save_workspace_notes(slug: str, notes: list[dict[str, Any]]) -> None:
    paths = _workspace_paths(slug)
    _write_json_atomic(paths["notes"], {"notes": notes})


def _set_index_workspace_values(
    index: dict[str, list[dict[str, Any]]],
    slug: str,
    *,
    page_count: int | None = None,
    updated: str | None = None,
) -> None:
    entry = _find_index_entry(index, slug)
    if not entry:
        return
    if page_count is not None:
        entry["page_count"] = max(page_count, 0)
    if updated is not None:
        entry["updated"] = updated


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


def create_workspace(title: str, description: str) -> dict[str, Any] | str:
    clean_title = title.strip() if isinstance(title, str) else ""
    clean_description = description.strip() if isinstance(description, str) else ""
    if not clean_title:
        return "Workspace title is required."
    if not clean_description:
        return "Workspace description is required."

    slug = _slugify(clean_title)
    index = _load_index()
    existing = _find_index_entry(index, slug)

    if existing:
        _ensure_workspace_files(slug, str(existing.get("title", clean_title)), clean_description)
        state = _read_workspace_state(slug)
        metadata = state["metadata"]
        return {
            "slug": slug,
            "title": metadata.get("title", existing.get("title", clean_title)),
            "description": metadata.get("description", clean_description),
            "created": metadata.get("created", existing.get("created", "")),
            "updated": metadata.get("updated", existing.get("updated", "")),
            "status": metadata.get("status", "active"),
            "page_count": len(state["pages"]),
        }

    now = _now_iso()
    _ensure_workspace_files(slug, clean_title, clean_description)

    metadata = {
        "title": clean_title,
        "slug": slug,
        "description": clean_description,
        "created": now,
        "updated": now,
        "status": "active",
    }
    _save_workspace_metadata(slug, metadata)
    _save_workspace_pages(slug, [])
    _save_workspace_notes(slug, [])

    index["workspaces"].append(
        {
            "slug": slug,
            "title": clean_title,
            "page_count": 0,
            "created": now,
            "updated": now,
        }
    )
    _save_index(index)

    return {
        "slug": slug,
        "title": clean_title,
        "description": clean_description,
        "created": now,
        "updated": now,
        "status": "active",
        "page_count": 0,
    }


def list_workspaces() -> list[dict[str, Any]]:
    index = _load_index()
    rows: list[dict[str, Any]] = []

    for entry in index.get("workspaces", []):
        slug = str(entry.get("slug", "")).strip()
        if not slug:
            continue

        metadata = _read_json_default(_workspace_paths(slug)["workspace"], {})
        pages_payload = _read_json_default(_workspace_paths(slug)["pages"], {"pages": []})
        pages = pages_payload.get("pages", []) if isinstance(pages_payload, dict) else []
        if not isinstance(pages, list):
            pages = []

        rows.append(
            {
                "slug": slug,
                "title": metadata.get("title", entry.get("title", "")),
                "description": metadata.get("description", ""),
                "page_count": len(pages),
                "status": metadata.get("status", "active"),
                "created": metadata.get("created", entry.get("created", "")),
                "updated": metadata.get("updated", entry.get("updated", "")),
            }
        )

    return rows


def get_workspace(workspace_slug: str) -> dict[str, Any] | str:
    index = _load_index()
    slug = _resolve_workspace_slug(workspace_slug, index)
    if not slug:
        return f"Workspace '{workspace_slug}' not found."

    entry = _find_index_entry(index, slug)
    title = str(entry.get("title", slug)) if entry else slug
    _ensure_workspace_files(slug, title, "")
    state = _read_workspace_state(slug)

    return {
        "metadata": state["metadata"],
        "pages": state["pages"],
        "notes": state["notes"],
    }


def add_page(workspace_slug: str, page_name: str, reason: str) -> dict[str, Any] | str:
    index = _load_index()
    slug = _resolve_workspace_slug(workspace_slug, index)
    if not slug:
        return f"Workspace '{workspace_slug}' not found."

    clean_reason = reason.strip() if isinstance(reason, str) else ""
    if not clean_reason:
        return "A reason is required when adding a page."

    if _project is None:
        return "No project loaded. Run: python ingest.py <folder>"

    resolved_page, ambiguous_pages = _resolve_project_page_name(page_name)
    if ambiguous_pages:
        matches = ", ".join(ambiguous_pages)
        return f"Page name '{page_name}' is ambiguous. Matches: {matches}"
    if not resolved_page:
        return f"Page '{page_name}' not found. Use list_pages() to see available pages."

    entry = _find_index_entry(index, slug)
    title = str(entry.get("title", slug)) if entry else slug
    _ensure_workspace_files(slug, title, "")
    state = _read_workspace_state(slug)
    pages = state["pages"]

    for item in pages:
        if isinstance(item, dict) and item.get("page_name") == resolved_page:
            return f"Page '{resolved_page}' is already in workspace '{slug}'."

    now = _now_iso()
    pages.append(
        {
            "page_name": resolved_page,
            "reason": clean_reason,
            "added_by": "maestro",
            "added_at": now,
            "regions_of_interest": [],
        }
    )
    _save_workspace_pages(slug, pages)

    metadata = state["metadata"]
    metadata["updated"] = now
    _save_workspace_metadata(slug, metadata)

    _set_index_workspace_values(index, slug, page_count=len(pages), updated=now)
    _save_index(index)

    return {
        "workspace_slug": slug,
        "page_name": resolved_page,
        "reason": clean_reason,
        "page_count": len(pages),
    }


def remove_page(workspace_slug: str, page_name: str) -> dict[str, Any] | str:
    index = _load_index()
    slug = _resolve_workspace_slug(workspace_slug, index)
    if not slug:
        return f"Workspace '{workspace_slug}' not found."

    entry = _find_index_entry(index, slug)
    title = str(entry.get("title", slug)) if entry else slug
    _ensure_workspace_files(slug, title, "")
    state = _read_workspace_state(slug)
    pages = state["pages"]

    workspace_page_names = [str(item.get("page_name", "")) for item in pages if isinstance(item, dict)]
    resolved_page, ambiguous_pages = _resolve_candidate_name(page_name, workspace_page_names)
    if ambiguous_pages:
        matches = ", ".join(ambiguous_pages)
        return f"Page name '{page_name}' is ambiguous in workspace '{slug}'. Matches: {matches}"
    if not resolved_page:
        return f"Page '{page_name}' is not in workspace '{slug}'."

    filtered_pages = [item for item in pages if not (isinstance(item, dict) and item.get("page_name") == resolved_page)]
    if len(filtered_pages) == len(pages):
        return f"Page '{resolved_page}' is not in workspace '{slug}'."

    now = _now_iso()
    _save_workspace_pages(slug, filtered_pages)

    metadata = state["metadata"]
    metadata["updated"] = now
    _save_workspace_metadata(slug, metadata)

    _set_index_workspace_values(index, slug, page_count=len(filtered_pages), updated=now)
    _save_index(index)

    return {
        "workspace_slug": slug,
        "page_name": resolved_page,
        "page_count": len(filtered_pages),
        "removed": True,
    }


def add_note(workspace_slug: str, note_text: str, source_page: str | None = None) -> dict[str, Any] | str:
    index = _load_index()
    slug = _resolve_workspace_slug(workspace_slug, index)
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

    entry = _find_index_entry(index, slug)
    title = str(entry.get("title", slug)) if entry else slug
    _ensure_workspace_files(slug, title, "")
    state = _read_workspace_state(slug)
    notes = state["notes"]

    now = _now_iso()
    note = {
        "text": clean_note,
        "source": "maestro",
        "source_page": resolved_source,
        "added_at": now,
    }
    notes.append(note)
    _save_workspace_notes(slug, notes)

    metadata = state["metadata"]
    metadata["updated"] = now
    _save_workspace_metadata(slug, metadata)

    _set_index_workspace_values(index, slug, updated=now)
    _save_index(index)

    return {
        "workspace_slug": slug,
        "note": note,
        "note_count": len(notes),
    }


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
            "reason": {"type": "string", "required": True},
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
]


workspace_tool_functions: dict[str, Callable[..., Any]] = {
    "create_workspace": create_workspace,
    "list_workspaces": list_workspaces,
    "get_workspace": get_workspace,
    "add_page": add_page,
    "remove_page": remove_page,
    "add_note": add_note,
}
