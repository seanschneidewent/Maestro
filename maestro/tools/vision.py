# vision.py - Async visual highlight agents for Maestro V13

from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from maestro.db import repository as repo
from maestro.knowledge.gemini_service import _collect_response

load_dotenv()

logger = logging.getLogger(__name__)
GEMINI_MODEL = "gemini-3-flash-preview"


_COORD_PATTERN = re.compile(
    r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)"
)
_COORD_BRACKET_PATTERN = re.compile(
    r"\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]"
)
_BOX2D_PATTERN = re.compile(
    r"box_2d\s*[:=]\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]",
    re.IGNORECASE,
)


def _get_gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    return genai.Client(api_key=api_key)


def _normalize_token(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "_", value.lower())
    return re.sub(r"_+", "_", token).strip("_")


def _resolve_project_page_name(page_name: str, project: dict[str, Any]) -> str | None:
    pages = project.get("pages", {}) if isinstance(project, dict) else {}
    if not isinstance(pages, dict) or not page_name.strip():
        return None

    if page_name in pages:
        return page_name

    normalized_query = _normalize_token(page_name)
    if not normalized_query:
        return None

    candidates = [name for name in pages.keys() if isinstance(name, str)]
    normalized = {name: _normalize_token(name) for name in candidates}

    prefix_matches = sorted([name for name in candidates if normalized[name].startswith(normalized_query)])
    if len(prefix_matches) == 1:
        return prefix_matches[0]

    substring_matches = sorted([name for name in candidates if normalized_query in normalized[name]])
    if len(substring_matches) == 1:
        return substring_matches[0]

    return None


def _resolve_workspace_page_name(project_id: str, workspace_slug: str, page_name: str) -> tuple[str | None, str | None]:
    resolved_slug = repo.resolve_workspace_slug(project_id, workspace_slug)
    if not resolved_slug:
        return None, None

    workspace = repo.get_workspace(project_id, resolved_slug)
    if not workspace:
        return None, resolved_slug

    pages = [str(p.get("page_name", "")) for p in workspace.get("pages", []) if isinstance(p, dict)]
    if page_name in pages:
        return page_name, resolved_slug

    normalized_query = _normalize_token(page_name)
    if not normalized_query:
        return None, resolved_slug

    normalized = {name: _normalize_token(name) for name in pages}

    prefix_matches = sorted([name for name in pages if normalized[name].startswith(normalized_query)])
    if len(prefix_matches) == 1:
        return prefix_matches[0], resolved_slug

    substring_matches = sorted([name for name in pages if normalized_query in normalized[name]])
    if len(substring_matches) == 1:
        return substring_matches[0], resolved_slug

    return None, resolved_slug


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _normalize_bbox(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> dict[str, float] | None:
    if width <= 0 or height <= 0:
        return None

    left = min(x1, x2)
    right = max(x1, x2)
    top = min(y1, y2)
    bottom = max(y1, y2)

    if right <= left or bottom <= top:
        return None

    nx = _clamp(left / width, 0.0, 1.0)
    ny = _clamp(top / height, 0.0, 1.0)
    nright = _clamp(right / width, 0.0, 1.0)
    nbottom = _clamp(bottom / height, 0.0, 1.0)

    nwidth = nright - nx
    nheight = nbottom - ny
    if nwidth <= 0 or nheight <= 0:
        return None

    return {
        "x": round(nx, 6),
        "y": round(ny, 6),
        "width": round(nwidth, 6),
        "height": round(nheight, 6),
    }


def _dedupe_bboxes(bboxes: list[dict[str, float]]) -> list[dict[str, float]]:
    seen: set[tuple[float, float, float, float]] = set()
    out: list[dict[str, float]] = []

    for bbox in bboxes:
        key = (
            round(float(bbox["x"]), 4),
            round(float(bbox["y"]), 4),
            round(float(bbox["width"]), 4),
            round(float(bbox["height"]), 4),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "x": float(key[0]),
                "y": float(key[1]),
                "width": float(key[2]),
                "height": float(key[3]),
            }
        )

    return out


def _extract_raw_pixel_boxes(text: str) -> list[tuple[float, float, float, float]]:
    if not text:
        return []

    boxes: list[tuple[float, float, float, float]] = []
    lowered = text.lower()

    for match in _BOX2D_PATTERN.finditer(text):
        vals = tuple(float(match.group(i)) for i in range(1, 5))
        boxes.append(vals)

    if "rectangle" in lowered or "crop" in lowered or "bbox" in lowered or "box" in lowered:
        for match in _COORD_PATTERN.finditer(text):
            vals = tuple(float(match.group(i)) for i in range(1, 5))
            boxes.append(vals)
        for match in _COORD_BRACKET_PATTERN.finditer(text):
            vals = tuple(float(match.group(i)) for i in range(1, 5))
            boxes.append(vals)

    return boxes


def _extract_bboxes_from_trace(trace: list[dict[str, Any]], image_width: int, image_height: int) -> list[dict[str, float]]:
    bboxes: list[dict[str, float]] = []

    for entry in trace:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") not in {"code", "code_result", "text"}:
            continue

        content = entry.get("content", "")
        if not isinstance(content, str) or not content.strip():
            continue

        for x1, y1, x2, y2 in _extract_raw_pixel_boxes(content):
            normalized = _normalize_bbox(x1, y1, x2, y2, image_width, image_height)
            if normalized is not None:
                bboxes.append(normalized)

    return _dedupe_bboxes(bboxes)


def _run_highlight_agent(
    workspace_slug: str,
    page_name: str,
    mission: str,
    highlight_id: int,
    project: dict[str, Any],
    project_page_name: str,
) -> None:
    try:
        page = project.get("pages", {}).get(project_page_name, {})
        page_png = Path(page.get("path", "")) / "page.png"
        if not page_png.exists():
            raise RuntimeError(f"No image for '{project_page_name}'.")

        from PIL import Image

        with Image.open(page_png) as img:
            image_width, image_height = img.size

        client = _get_gemini_client()
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_bytes(data=page_png.read_bytes(), mime_type="image/png"),
                        types.Part.from_text(
                            text=(
                                "You are analyzing a construction plan page.\\n\\n"
                                f"PAGE: {page_name}\\n"
                                f"MISSION: {mission}\\n\\n"
                                "Use code execution to inspect the image and identify rectangular regions relevant "
                                "to the mission. Think with code naturally."
                            )
                        ),
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0,
                thinking_config=types.ThinkingConfig(thinking_level="high"),
                tools=[types.Tool(code_execution=types.ToolCodeExecution)],
            ),
        )

        collected = _collect_response(response)
        trace = collected.get("trace", [])
        bboxes = _extract_bboxes_from_trace(
            trace,
            image_width=image_width or 1,
            image_height=image_height or 1,
        )
        if not bboxes:
            raise RuntimeError("No valid bbox coordinates found in Gemini trace.")

        completed = repo.complete_highlight(highlight_id, bboxes)
        if isinstance(completed, str):
            raise RuntimeError(completed)

        try:
            from maestro.api.websocket import emit_page_highlight_complete

            emit_page_highlight_complete(
                workspace_slug=workspace_slug,
                page_name=page_name,
                highlight_id=highlight_id,
                mission=mission,
                bboxes=bboxes,
            )
        except Exception:
            pass

    except Exception as exc:
        logger.exception("Highlight agent failed for %s/%s (%s)", workspace_slug, page_name, highlight_id)
        repo.fail_highlight(highlight_id)
        try:
            from maestro.api.websocket import emit_page_highlight_failed

            emit_page_highlight_failed(
                workspace_slug=workspace_slug,
                page_name=page_name,
                highlight_id=highlight_id,
            )
        except Exception:
            pass
        logger.debug("Highlight failure reason: %s", exc)


def spawn_highlights(
    workspace_slug: str,
    page_missions: list[dict[str, Any]],
    project: dict[str, Any] | None,
    project_id: str | None,
) -> dict[str, Any] | str:
    """Spawn highlight agents and return immediately."""
    if not project:
        return "No project loaded."
    if not project_id:
        return "No project id available."
    if not isinstance(page_missions, list) or not page_missions:
        return "page_missions must be a non-empty list of {page_name, mission}."

    spawned: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for item in page_missions:
        if not isinstance(item, dict):
            skipped.append({"page_name": "", "reason": "Invalid mission item."})
            continue

        raw_page_name = str(item.get("page_name", "")).strip()
        mission = str(item.get("mission", "")).strip()

        if not raw_page_name or not mission:
            skipped.append({"page_name": raw_page_name, "reason": "Both page_name and mission are required."})
            continue

        resolved_workspace_page, resolved_slug = _resolve_workspace_page_name(project_id, workspace_slug, raw_page_name)
        if not resolved_slug:
            return f"Workspace '{workspace_slug}' not found."
        if not resolved_workspace_page:
            skipped.append({
                "page_name": raw_page_name,
                "reason": f"Page is not in workspace '{resolved_slug}'.",
            })
            continue

        resolved_project_page = _resolve_project_page_name(resolved_workspace_page, project)
        if not resolved_project_page:
            skipped.append({
                "page_name": resolved_workspace_page,
                "reason": "Page not found in loaded project.",
            })
            continue

        created = repo.add_highlight(
            project_id=project_id,
            slug=resolved_slug,
            page_name=resolved_workspace_page,
            mission=mission,
        )
        if isinstance(created, str):
            skipped.append({"page_name": resolved_workspace_page, "reason": created})
            continue

        highlight = created.get("highlight", {}) if isinstance(created, dict) else {}
        highlight_id = highlight.get("id")
        if not isinstance(highlight_id, int):
            skipped.append({"page_name": resolved_workspace_page, "reason": "Failed to create highlight row."})
            continue

        try:
            from maestro.api.websocket import emit_page_highlight_started

            emit_page_highlight_started(
                workspace_slug=resolved_slug,
                page_name=resolved_workspace_page,
                highlight_id=highlight_id,
                mission=mission,
            )
        except Exception:
            pass

        worker = threading.Thread(
            target=_run_highlight_agent,
            kwargs={
                "workspace_slug": resolved_slug,
                "page_name": resolved_workspace_page,
                "mission": mission,
                "highlight_id": highlight_id,
                "project": project,
                "project_page_name": resolved_project_page,
            },
            daemon=True,
            name=f"highlight-{highlight_id}",
        )
        worker.start()

        spawned.append(
            {
                "highlight_id": highlight_id,
                "workspace_slug": resolved_slug,
                "page_name": resolved_workspace_page,
                "mission": mission,
                "status": "pending",
            }
        )

    if not spawned:
        detail = skipped[0]["reason"] if skipped else "No highlights were spawned."
        return f"No highlights spawned. {detail}"

    return {
        "workspace_slug": spawned[0]["workspace_slug"],
        "spawned": spawned,
        "skipped": skipped,
        "message": (
            f"Spawned {len(spawned)} highlight agents. "
            "Results will appear in the workspace as they complete."
        ),
    }


def highlight_pages(
    workspace_slug: str,
    page_missions: list[dict[str, Any]],
    project: dict[str, Any] | None,
    project_id: str | None,
) -> dict[str, Any] | str:
    """Public tool wrapper for async highlight spawning."""
    return spawn_highlights(
        workspace_slug=workspace_slug,
        page_missions=page_missions,
        project=project,
        project_id=project_id,
    )
