# knowledge_v13.py - Load project knowledge from knowledge_store/

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def load_project(project_name: str | None = None) -> dict[str, Any] | None:
    """
    Load a project from knowledge_store/ into memory.
    If project_name is omitted, load the first project folder found.
    """
    store = Path("knowledge_store")
    if not store.exists():
        print("No projects in knowledge_store/. Run: python ingest.py <folder>")
        return None

    if project_name:
        project_dir = store / project_name
        if not project_dir.exists() or not project_dir.is_dir():
            print(f"Project '{project_name}' not found in knowledge_store/")
            return None
    else:
        projects = [d for d in sorted(store.iterdir(), key=lambda p: p.name.lower()) if d.is_dir()]
        if not projects:
            print("No projects in knowledge_store/. Run: python ingest.py <folder>")
            return None
        project_dir = projects[0]

    project_json = project_dir / "project.json"
    if not project_json.exists():
        print(f"No project.json in {project_dir}")
        return None

    project = _load_json(project_json, {})
    if not isinstance(project, dict):
        project = {}
    project.setdefault("name", project_dir.name)
    project.setdefault("source_path", "")
    project.setdefault("total_pages", 0)

    index_path = project_dir / "index.json"
    index_data = _load_json(index_path, {})
    if not isinstance(index_data, dict):
        index_data = {}
    project["index"] = index_data

    project["pages"] = {}
    pages_dir = project_dir / "pages"
    if pages_dir.exists():
        for page_dir in sorted(pages_dir.iterdir(), key=lambda p: p.name.lower()):
            if not page_dir.is_dir():
                continue

            page_name = page_dir.name
            page: dict[str, Any] = {
                "name": page_name,
                "path": str(page_dir),
                "sheet_reflection": "",
                "page_type": "unknown",
                "discipline": "General",
                "index": {},
                "cross_references": [],
                "regions": [],
                "pointers": {},
            }

            pass1_path = page_dir / "pass1.json"
            pass1 = _load_json(pass1_path, {})
            if isinstance(pass1, dict):
                page["sheet_reflection"] = pass1.get("sheet_reflection", "")
                page["page_type"] = pass1.get("page_type", "unknown")
                page["discipline"] = pass1.get("discipline", "General") or "General"
                page["index"] = pass1.get("index", {}) if isinstance(pass1.get("index", {}), dict) else {}
                page["cross_references"] = pass1.get("cross_references", []) if isinstance(pass1.get("cross_references", []), list) else []
                page["regions"] = pass1.get("regions", []) if isinstance(pass1.get("regions", []), list) else []

            pointers_dir = page_dir / "pointers"
            if pointers_dir.exists():
                for pointer_dir in sorted(pointers_dir.iterdir(), key=lambda p: p.name.lower()):
                    if not pointer_dir.is_dir():
                        continue

                    region_id = pointer_dir.name
                    pass2_path = pointer_dir / "pass2.json"
                    pointer_data = _load_json(pass2_path, {})
                    if not isinstance(pointer_data, dict):
                        pointer_data = {}

                    pointer_data.setdefault("content_markdown", "")
                    pointer_data["crop_path"] = str(pointer_dir / "crop.png")
                    page["pointers"][region_id] = pointer_data

            project["pages"][page_name] = page

    derived_disciplines = sorted(
        {
            str(page.get("discipline", "General")).strip() or "General"
            for page in project["pages"].values()
        }
    )
    existing_disciplines = project.get("disciplines")
    if isinstance(existing_disciplines, list) and existing_disciplines:
        project["disciplines"] = sorted(set([str(item).strip() for item in existing_disciplines if str(item).strip()]))
    else:
        project["disciplines"] = derived_disciplines

    page_count = len(project["pages"])
    pointer_count = sum(len(page.get("pointers", {})) for page in project["pages"].values())
    print(f"Loaded: {project['name']} - {page_count} pages, {pointer_count} pointers")
    return project

