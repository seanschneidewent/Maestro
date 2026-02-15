# routes.py — REST API for Maestro's frontend
#
# Read-only endpoints that expose project state to the dashboard.
# All mutations happen through conversation (iMessage / heartbeat).
#
# Mount: app.include_router(api_router, prefix="/api")
#
# Endpoints:
#   GET /api/project                    — Project metadata
#   GET /api/workspaces                 — List all workspaces
#   GET /api/workspaces/:slug           — Full workspace (metadata + pages + notes)
#   GET /api/schedule                   — All events (with optional filters)
#   GET /api/schedule/upcoming          — Next N days
#   GET /api/schedule/:event_id         — Single event
#   GET /api/conversation               — Conversation state (summary + stats)
#   GET /api/conversation/messages      — Messages (paginated)
#   GET /api/knowledge/pages            — List all pages in knowledge store
#   GET /api/knowledge/pages/:page_name — Page summary + regions
#   GET /api/knowledge/disciplines      — List disciplines
#   GET /api/knowledge/search           — Search knowledge store
#   GET /api/health                     — Health + engine info

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from maestro.db import repository as repo

api_router = APIRouter()

# ===================================================================
# Discipline Normalization
# ===================================================================

# Canonical groups in display order
_CANONICAL_ORDER = [
    "General",
    "Architectural",
    "Structural",
    "Civil",
    "MEP",          # header only — sub-disciplines below
    "Mechanical",
    "Electrical",
    "Plumbing",
    "Kitchen",
    "Landscape",
    "Vapor Mitigation",
    "Canopy",
]

# Mapping rules: lowercased keyword → canonical name
_DISCIPLINE_MAP: dict[str, str] = {
    "general":              "General",
    "architectural":        "Architectural",
    "structural":           "Structural",
    "civil":                "Civil",
    "traffic":              "Civil",
    "traffic signal":       "Civil",
    "traffic control":      "Civil",
    "traffic / civil":      "Civil",
    "traffic / electrical": "Civil",
    "surveying":            "Civil",
    "mechanical":           "Mechanical",
    "electrical":           "Electrical",
    "electrical/lighting":  "Electrical",
    "plumbing":             "Plumbing",
    "plumbing (mep)":       "Plumbing",
    "kitchen":              "Kitchen",
    "foodservice":          "Kitchen",
    "foodservice equipment":"Kitchen",
    "landscape":            "Landscape",
    "irrigation":           "Landscape",
    "vapor mitigation":     "Vapor Mitigation",
    "environmental":        "Vapor Mitigation",
    "demolition":           "Vapor Mitigation",
    "canopy":               "Canopy",
    "signage & canopy":     "Canopy",
    "specialties (canopy)": "Canopy",
}

_MEP_SUBS = {"Mechanical", "Electrical", "Plumbing"}


def _normalize_discipline(raw: str) -> str:
    """Map a raw discipline string to its canonical group."""
    if not raw:
        return "General"
    lower = raw.strip().lower()
    # Direct match
    if lower in _DISCIPLINE_MAP:
        return _DISCIPLINE_MAP[lower]
    # Compound discipline like "Structural/Electrical" → first named
    if "/" in lower:
        first = lower.split("/")[0].strip()
        if first in _DISCIPLINE_MAP:
            return _DISCIPLINE_MAP[first]
    # Substring fallback for partial matches
    for key, canonical in _DISCIPLINE_MAP.items():
        if key in lower:
            return canonical
    return "General"


def _sort_key(name: str) -> int:
    """Sort disciplines by canonical display order."""
    try:
        return _CANONICAL_ORDER.index(name)
    except ValueError:
        return len(_CANONICAL_ORDER)

# These get set by server.py after Conversation is initialized
_project_id: str | None = None
_conversation: Any = None  # Conversation instance
_project: dict[str, Any] | None = None  # In-memory knowledge store


def init_api(project_id: str, conversation: Any, project: dict[str, Any] | None = None) -> None:
    """Wire up the API with runtime references."""
    global _project_id, _conversation, _project
    _project_id = project_id
    _conversation = conversation
    _project = project


def _require_pid() -> str:
    if not _project_id:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return _project_id


# ===================================================================
# Project
# ===================================================================

@api_router.get("/project")
async def get_project():
    pid = _require_pid()
    project = repo.get_project(pid)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Enrich with knowledge store stats
    page_count = 0
    pointer_count = 0
    disciplines = set()
    if _project:
        pages = _project.get("pages", {})
        page_count = len(pages)
        for page in pages.values():
            pointer_count += len(page.get("pointers", {}))
            disc = page.get("discipline", "")
            if disc:
                disciplines.add(disc)

    return {
        **project,
        "page_count": page_count,
        "pointer_count": pointer_count,
        "discipline_count": len(disciplines),
        "engine": _conversation.engine_name if _conversation else None,
    }


# ===================================================================
# Workspaces
# ===================================================================

@api_router.get("/workspaces")
async def list_workspaces():
    pid = _require_pid()
    return repo.list_workspaces(pid)


@api_router.get("/workspaces/{slug}")
async def get_workspace(slug: str):
    pid = _require_pid()
    ws = repo.get_workspace(pid, slug)
    if not ws:
        # Try slug resolution
        resolved = repo.resolve_workspace_slug(pid, slug)
        if resolved:
            ws = repo.get_workspace(pid, resolved)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace '{slug}' not found")
    return ws


# ===================================================================
# Schedule
# ===================================================================

@api_router.get("/schedule")
async def list_events(
    from_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    event_type: str | None = Query(None, description="Filter by type"),
):
    pid = _require_pid()
    events = repo.list_events(pid, from_date=from_date, to_date=to_date, event_type=event_type)
    return {"events": events, "count": len(events)}


@api_router.get("/schedule/upcoming")
async def upcoming_events(days: int = Query(7, description="Days ahead")):
    pid = _require_pid()
    events = repo.upcoming_events(pid, days=days)
    return {"events": events, "count": len(events), "days": days}


@api_router.get("/schedule/{event_id}")
async def get_event(event_id: str):
    pid = _require_pid()
    event = repo.get_event(pid, event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    return event


# ===================================================================
# Conversation
# ===================================================================

@api_router.get("/conversation")
async def get_conversation():
    pid = _require_pid()
    state = repo.get_or_create_conversation(pid)

    # Add live stats from conversation object
    stats = {}
    if _conversation:
        stats = _conversation.get_stats()

    return {**state, **stats}


@api_router.get("/conversation/messages")
async def get_messages(
    limit: int = Query(50, ge=1, le=500, description="Max messages to return"),
    before: int | None = Query(None, description="Return messages before this ID"),
):
    pid = _require_pid()

    if before:
        # Paginate backwards from a specific message
        messages = repo.get_messages(pid)
        messages = [m for m in messages if m["id"] < before]
        messages = messages[-limit:]  # Take last N
    else:
        # Get most recent
        messages = repo.get_recent_messages(pid, count=limit)

    return {
        "messages": messages,
        "count": len(messages),
        "total": repo.count_messages(pid),
    }


# ===================================================================
# Knowledge Store (read-only, from in-memory project)
# ===================================================================

@api_router.get("/knowledge/disciplines")
async def list_disciplines():
    if not _project:
        return {"disciplines": []}

    counts: dict[str, int] = {}
    for page in _project.get("pages", {}).values():
        canonical = _normalize_discipline(page.get("discipline", ""))
        counts[canonical] = counts.get(canonical, 0) + 1

    # Build response: MEP is a header grouping its sub-disciplines
    result = []
    for name in _CANONICAL_ORDER:
        if name == "MEP":
            # Collect sub-discipline counts
            subs = []
            mep_total = 0
            for sub in _MEP_SUBS:
                if sub in counts:
                    subs.append({"name": sub, "page_count": counts[sub]})
                    mep_total += counts[sub]
            if mep_total > 0:
                subs.sort(key=lambda s: _sort_key(s["name"]))
                result.append({"name": "MEP", "page_count": mep_total, "children": subs})
        elif name in _MEP_SUBS:
            continue  # handled inside MEP
        elif name in counts:
            result.append({"name": name, "page_count": counts[name]})

    return {"disciplines": result}


@api_router.get("/knowledge/pages")
async def list_pages(discipline: str | None = Query(None, description="Filter by discipline")):
    if not _project:
        return {"pages": []}

    pages = []
    for name, page in sorted(_project.get("pages", {}).items()):
        canonical = _normalize_discipline(page.get("discipline", ""))
        if discipline:
            # Match exact canonical name, or if filtering by "MEP" match any sub-discipline
            if discipline == "MEP":
                if canonical not in _MEP_SUBS:
                    continue
            elif canonical != discipline:
                continue
        pages.append({
            "page_name": name,
            "discipline": canonical,
            "sheet_reflection": page.get("sheet_reflection", "")[:200],
            "pointer_count": len(page.get("pointers", {})),
            "cross_references": page.get("cross_references", []),
        })

    return {"pages": pages, "count": len(pages)}


@api_router.get("/knowledge/page-image/{page_name}")
async def get_page_image(page_name: str):
    """Return the image URL for a knowledge store page."""
    if not _project:
        raise HTTPException(status_code=503, detail="No project loaded")
    page = _project.get("pages", {}).get(page_name)
    if not page:
        raise HTTPException(status_code=404, detail=f"Page '{page_name}' not found")
    project_name = _project.get("name", "")
    return {"image_url": f"/static/pages/{project_name}/pages/{page_name}/page.png"}


@api_router.get("/knowledge/page-thumb/{page_name}")
async def get_page_thumb(
    page_name: str,
    w: int = Query(800, ge=100, le=2000, description="Max width in pixels"),
    q: int = Query(80, ge=10, le=100, description="JPEG quality"),
):
    """Return a resized JPEG thumbnail of a plan page. Cached to disk after first gen."""
    from PIL import Image

    if not _project:
        raise HTTPException(status_code=503, detail="No project loaded")
    page = _project.get("pages", {}).get(page_name)
    if not page:
        raise HTTPException(status_code=404, detail=f"Page '{page_name}' not found")

    page_path = Path(page["path"])
    png_path = page_path / "page.png"
    if not png_path.exists():
        raise HTTPException(status_code=404, detail="Page image not found")

    # Cache path: thumb_800_80.jpg next to page.png
    cache_name = f"thumb_{w}_{q}.jpg"
    cache_path = page_path / cache_name

    if not cache_path.exists():
        img = Image.open(png_path)
        # Resize maintaining aspect ratio
        ratio = w / img.width
        new_h = int(img.height * ratio)
        img = img.resize((w, new_h), Image.LANCZOS)
        # Convert RGBA to RGB if needed
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(str(cache_path), "JPEG", quality=q, optimize=True)

    return FileResponse(str(cache_path), media_type="image/jpeg")


@api_router.get("/knowledge/pages/{page_name:path}")
async def get_page(page_name: str):
    if not _project:
        raise HTTPException(status_code=503, detail="No project loaded")

    page = _project.get("pages", {}).get(page_name)
    if not page:
        raise HTTPException(status_code=404, detail=f"Page '{page_name}' not found")

    # Return page summary + pointer list (not full content — that's heavy)
    pointers = []
    for rid, ptr in sorted(page.get("pointers", {}).items()):
        pointers.append({
            "region_id": rid,
            "label": ptr.get("label", ""),
            "content_preview": (ptr.get("content_markdown", "") or "")[:150],
        })

    return {
        "page_name": page_name,
        "discipline": page.get("discipline", ""),
        "sheet_reflection": page.get("sheet_reflection", ""),
        "index": page.get("index", {}),
        "cross_references": page.get("cross_references", []),
        "pointers": pointers,
        "pointer_count": len(pointers),
    }


@api_router.get("/knowledge/search")
async def search_knowledge(q: str = Query(..., description="Search query")):
    if not _project:
        return {"results": [], "query": q}

    # Simple keyword search across pages and pointers
    query_lower = q.lower()
    results = []

    for page_name, page in _project.get("pages", {}).items():
        # Search page-level
        reflection = page.get("sheet_reflection", "") or ""
        index_text = str(page.get("index", {}))

        if query_lower in reflection.lower() or query_lower in index_text.lower():
            results.append({
                "type": "page",
                "page_name": page_name,
                "discipline": page.get("discipline", ""),
                "match_context": reflection[:200],
            })

        # Search pointers
        for rid, ptr in page.get("pointers", {}).items():
            content = ptr.get("content_markdown", "") or ""
            label = ptr.get("label", "") or ""
            if query_lower in content.lower() or query_lower in label.lower():
                results.append({
                    "type": "pointer",
                    "page_name": page_name,
                    "region_id": rid,
                    "label": label,
                    "match_context": content[:200],
                })

    return {"results": results, "count": len(results), "query": q}


# ===================================================================
# Health (enriched version for API)
# ===================================================================

@api_router.get("/health")
async def api_health():
    return {
        "status": "ok",
        "engine": _conversation.engine_name if _conversation else None,
        "project_id": _project_id,
        "time": datetime.now().isoformat(),
        "tools": len(_conversation.tool_definitions) if _conversation else 0,
    }
