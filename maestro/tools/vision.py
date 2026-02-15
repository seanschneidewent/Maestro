# vision.py - Visual tools for Maestro V13

from __future__ import annotations

import base64
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

from maestro.db import repository as repo
from maestro.knowledge.gemini_service import _collect_response, _save_trace

load_dotenv()

GEMINI_MODEL = "gemini-3-flash-preview"
WORKSPACES_DIR = Path(__file__).resolve().parents[2] / "workspaces"


def _get_gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    return genai.Client(api_key=api_key)


def _image_to_base64(image_path: Path, max_bytes: int = 4_000_000, max_dim: int = 7999) -> dict[str, Any]:
    """Read an image and return a base64-encoded content block for Anthropic multimodal."""
    img = Image.open(image_path)
    w, h = img.size
    media_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"

    needs_resize = w > max_dim or h > max_dim or image_path.stat().st_size > max_bytes

    scale = min(max_dim / w, max_dim / h, 1.0)
    if needs_resize or True:  # Always optimize for API payload size
        scale = min(scale, 0.5) if (w * h) > 4_000_000 else scale
        new_w, new_h = int(w * scale), int(h * scale)
        if new_w != w or new_h != h:
            img = img.resize((new_w, new_h), Image.LANCZOS)

    img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    raw = buf.getvalue()
    media_type = "image/jpeg"

    b64 = base64.standard_b64encode(raw).decode("ascii")
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": b64,
        },
    }


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


def _safe_filename(value: str) -> str:
    return _normalize_token(value) or "page"


def see_page(page_name: str, project: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return page image as multimodal content blocks for Opus to see directly."""
    if not project:
        return [{"type": "text", "text": "No project loaded."}]

    resolved_page_name = _resolve_project_page_name(page_name, project)
    if not resolved_page_name:
        return [{"type": "text", "text": f"Page '{page_name}' not found"}]

    page = project.get("pages", {}).get(resolved_page_name)
    page_png = Path(page.get("path", "")) / "page.png"
    if not page_png.exists():
        return [{"type": "text", "text": f"No image for '{resolved_page_name}'"}]

    image_block = _image_to_base64(page_png)
    return [
        image_block,
        {
            "type": "text",
            "text": (
                f"This is page '{resolved_page_name}'. You are looking at it directly. "
                "Describe what you see."
            ),
        },
    ]


def highlight_on_page(
    workspace_slug: str,
    page_name: str,
    mission: str,
    project: dict[str, Any] | None,
    project_id: str | None,
) -> dict[str, Any] | str:
    """Generate and persist a Gemini highlight layer for a workspace page."""
    if not project:
        return "No project loaded."
    if not project_id:
        return "No project id available."

    clean_mission = mission.strip() if isinstance(mission, str) else ""
    if not clean_mission:
        return "Mission is required."

    resolved_workspace_page, resolved_slug = _resolve_workspace_page_name(project_id, workspace_slug, page_name)
    if not resolved_slug:
        return f"Workspace '{workspace_slug}' not found."
    if not resolved_workspace_page:
        return f"Page '{page_name}' is not in workspace '{resolved_slug}'."

    resolved_project_page = _resolve_project_page_name(resolved_workspace_page, project)
    if not resolved_project_page:
        return f"Page '{resolved_workspace_page}' not found in loaded project."

    page = project.get("pages", {}).get(resolved_project_page)
    page_png = Path(page.get("path", "")) / "page.png"
    if not page_png.exists():
        return f"No image for '{resolved_project_page}'."

    try:
        from maestro.api.websocket import emit_page_highlight_started

        emit_page_highlight_started(
            workspace_slug=resolved_slug,
            page_name=resolved_workspace_page,
            mission=clean_mission,
        )
    except Exception:
        pass

    try:
        client = _get_gemini_client()
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_bytes(data=page_png.read_bytes(), mime_type="image/png"),
                        types.Part.from_text(
                            text=(
                                "You are generating a visual highlight overlay for a construction plan page.\n\n"
                                f"PAGE: {resolved_workspace_page}\n"
                                f"MISSION: {clean_mission}\n\n"
                                "Use code execution to create exactly one PNG image that highlights only what is relevant "
                                "to the mission. Keep the original page readable. Prefer translucent overlays, outlines, "
                                "and short callouts. Return a brief summary text and the image output."
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
    except Exception as exc:
        return f"Highlight generation failed: {exc}"

    collected = _collect_response(response)
    images = collected.get("images", [])
    trace = collected.get("trace", [])
    result_text = collected.get("text", "")

    if not images:
        text_preview = result_text.strip()
        if text_preview:
            return (
                "Gemini did not return a highlight image. "
                f"Model output preview: {text_preview[:240]}"
            )
        return "Gemini did not return a highlight image."

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    filename_stem = f"{_safe_filename(resolved_workspace_page)}_{timestamp}"
    highlight_dir = WORKSPACES_DIR / resolved_slug / "highlights"
    highlight_dir.mkdir(parents=True, exist_ok=True)

    image_path = (highlight_dir / f"{filename_stem}.png").resolve()
    image_path.write_bytes(images[0])

    saved_trace = _save_trace(trace, images, highlight_dir, prefix=f"{filename_stem}_trace")
    trace_path = highlight_dir / f"{filename_stem}_trace.json"
    try:
        trace_path.write_text(
            json.dumps(
                {
                    "tool": "highlight_on_page",
                    "workspace_slug": resolved_slug,
                    "page_name": resolved_workspace_page,
                    "mission": clean_mission,
                    "model": GEMINI_MODEL,
                    "text": result_text,
                    "trace": saved_trace,
                },
                indent=2,
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass

    saved = repo.add_highlight(
        project_id=project_id,
        slug=resolved_slug,
        page_name=resolved_workspace_page,
        mission=clean_mission,
        image_path=str(image_path),
    )
    if isinstance(saved, str):
        return saved

    highlight_payload = saved.get("highlight", {})

    try:
        from maestro.api.websocket import emit_page_highlight_complete

        emit_page_highlight_complete(
            workspace_slug=resolved_slug,
            page_name=resolved_workspace_page,
            highlight_id=highlight_payload.get("id"),
            mission=clean_mission,
            image_path=str(image_path),
        )
    except Exception:
        pass

    return {
        "workspace_slug": resolved_slug,
        "page_name": resolved_workspace_page,
        "highlight": highlight_payload,
        "message": (result_text or "Highlight generated.")[:500],
    }
