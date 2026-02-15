# knowledge.py — Knowledge store query tools
#
# Tools for searching, listing, and reading from the in-memory project data.
# These tools give Maestro access to everything the ingest pipeline extracted.

from __future__ import annotations

from typing import Any

from knowledge.loader import load_project

# Project reference — set by registry.py at startup
project = None


def _no_project() -> str:
    return "No project loaded. Run: python ingest.py <folder>"


def _resolve_page(page_name: str) -> dict[str, Any] | None:
    """Fuzzy-match a page name. Tries exact match first, then prefix/substring."""
    if not project:
        return None
    pages = project.get("pages", {})

    # Exact match
    if page_name in pages:
        return pages[page_name]

    # Normalize: replace dots/dashes/spaces with underscores, strip _p001 suffix
    normalized = page_name.replace(".", "_").replace("-", "_").replace(" ", "_").strip("_")

    # Try prefix match (e.g. "A111" matches "A111_Floor_Finish_Plan_p001")
    candidates = []
    for name, page in pages.items():
        if name.startswith(normalized) or name.startswith(normalized + "_"):
            candidates.append((name, page))

    if len(candidates) == 1:
        return candidates[0][1]

    # Try substring match (e.g. "Floor_Finish" matches "A111_Floor_Finish_Plan_p001")
    if not candidates:
        lower = normalized.lower()
        for name, page in pages.items():
            if lower in name.lower():
                candidates.append((name, page))

    if len(candidates) == 1:
        return candidates[0][1]
    if candidates:
        # Multiple matches — return first but this is still better than nothing
        return candidates[0][1]

    return None


def _resolve_page_name(page_name: str) -> str | None:
    """Resolve to the actual page name string (for error messages)."""
    page = _resolve_page(page_name)
    if page:
        return page.get("name", page_name)
    return None


def list_disciplines() -> list[str] | str:
    """List all disciplines in the loaded project."""
    if not project:
        return _no_project()
    return project.get("disciplines", [])


def list_pages(discipline: str | None = None) -> list[dict[str, Any]] | str:
    """List pages, optionally filtered by discipline."""
    if not project:
        return _no_project()

    pages: list[dict[str, Any]] = []
    for name, page in project.get("pages", {}).items():
        page_discipline = str(page.get("discipline", ""))
        if discipline and page_discipline.lower() != discipline.lower():
            continue
        pages.append(
            {
                "name": name,
                "type": page.get("page_type", "unknown"),
                "discipline": page_discipline,
                "region_count": len(page.get("regions", [])),
            }
        )
    return sorted(pages, key=lambda p: p["name"].lower())


def get_sheet_summary(page_name: str) -> str:
    """Get Pass 1 summary text for a page."""
    if not project:
        return _no_project()
    page = _resolve_page(page_name)
    if not page:
        return f"Page '{page_name}' not found. Use list_pages() to see available pages."
    return page.get("sheet_reflection", "No summary available")


def get_sheet_index(page_name: str) -> dict[str, Any] | str:
    """Get searchable Pass 1 index for a page."""
    if not project:
        return _no_project()
    page = _resolve_page(page_name)
    if not page:
        return f"Page '{page_name}' not found. Use list_pages() to see available pages."
    return page.get("index", {})


def list_regions(page_name: str) -> list[dict[str, Any]] | str:
    """List all extracted regions for a page."""
    if not project:
        return _no_project()
    page = _resolve_page(page_name)
    if not page:
        return f"Page '{page_name}' not found. Use list_pages() to see available pages."

    pointers = page.get("pointers", {})
    regions = []
    for region in page.get("regions", []):
        if not isinstance(region, dict):
            continue
        region_id = region.get("id", "")
        regions.append(
            {
                "id": region_id,
                "type": region.get("type"),
                "label": region.get("label"),
                "detail_number": region.get("detail_number"),
                "has_pass2": bool(region_id and region_id in pointers),
            }
        )
    return regions


def get_region_detail(page_name: str, region_id: str) -> str:
    """Get the Pass 2 technical brief for a region."""
    if not project:
        return _no_project()
    page = _resolve_page(page_name)
    if not page:
        return f"Page '{page_name}' not found. Use list_pages() to see available pages."
    pointer = page.get("pointers", {}).get(region_id)
    if not pointer:
        return f"Region '{region_id}' not found on '{page.get('name', page_name)}'. Use list_regions() to see available regions."
    return pointer.get("content_markdown", "No detail available")


def search(query: str) -> list[dict[str, Any]] | str:
    """Search across aggregated index and page/pointer content."""
    if not project:
        return _no_project()

    query_lower = query.lower()
    results: list[dict[str, Any]] = []
    idx = project.get("index", {})
    if not isinstance(idx, dict):
        idx = {}

    for material, sources in idx.get("materials", {}).items():
        if query_lower in str(material).lower():
            results.append({"type": "material", "match": material, "found_in": sources})

    for keyword, sources in idx.get("keywords", {}).items():
        if query_lower in str(keyword).lower():
            results.append({"type": "keyword", "match": keyword, "found_in": sources})

    for page_name, page in project.get("pages", {}).items():
        if query_lower in str(page.get("sheet_reflection", "")).lower():
            results.append({"type": "page", "match": page_name, "context": "sheet_reflection"})

        for pointer_id, pointer in page.get("pointers", {}).items():
            if query_lower in str(pointer.get("content_markdown", "")).lower():
                results.append(
                    {
                        "type": "pointer",
                        "match": f"{page_name}/{pointer_id}",
                        "context": "content_markdown",
                    }
                )

    return results if results else f"No results for '{query}'"


def find_cross_references(page_name: str) -> dict[str, Any] | str:
    """Find references from and to a page."""
    if not project:
        return _no_project()
    page = project.get("pages", {}).get(page_name)
    if not page:
        return f"Page '{page_name}' not found"

    idx = project.get("index", {})
    cross_refs = idx.get("cross_refs", {}) if isinstance(idx, dict) else {}
    refs_to = cross_refs.get(page_name, [])
    refs_from = page.get("cross_references", [])
    return {
        "references_from_this_page": refs_from,
        "pages_that_reference_this": refs_to,
    }


def list_modifications() -> list[dict[str, Any]] | str:
    """List all project modifications across all pointers."""
    if not project:
        return _no_project()
    idx = project.get("index", {})
    return idx.get("modifications", []) if isinstance(idx, dict) else []


def check_gaps() -> list[dict[str, Any]] | str:
    """List broken refs and regions missing Pass 2."""
    if not project:
        return _no_project()

    gaps: list[dict[str, Any]] = []
    idx = project.get("index", {})
    if isinstance(idx, dict):
        for ref in idx.get("broken_refs", []):
            gaps.append({"type": "broken_ref", "detail": ref})

    for page_name, page in project.get("pages", {}).items():
        pointers = page.get("pointers", {})
        for region in page.get("regions", []):
            if not isinstance(region, dict):
                continue
            region_id = region.get("id", "")
            if region_id and region_id not in pointers:
                gaps.append(
                    {
                        "type": "missing_pass2",
                        "page": page_name,
                        "region": region_id,
                        "label": region.get("label", ""),
                    }
                )

    return gaps if gaps else "No gaps found"


tool_definitions = [
    {"name": "list_disciplines", "description": "List all disciplines in the project", "params": {}},
    {
        "name": "list_pages",
        "description": "List all pages, optionally filtered by discipline",
        "params": {
            "discipline": {"type": "string", "description": "Filter by discipline name", "required": False}
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
    {"name": "list_modifications", "description": "List all install/demolish/protect items across the project", "params": {}},
    {"name": "check_gaps", "description": "Find broken cross-references and regions missing deep analysis", "params": {}},
]


tool_functions = {
    "list_disciplines": list_disciplines,
    "list_pages": list_pages,
    "get_sheet_summary": get_sheet_summary,
    "get_sheet_index": get_sheet_index,
    "list_regions": list_regions,
    "get_region_detail": get_region_detail,
    "search": search,
    "find_cross_references": find_cross_references,
    "list_modifications": list_modifications,
    "check_gaps": check_gaps,
}

