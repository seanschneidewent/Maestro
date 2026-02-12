# vision.py - On-demand visual inspection tools for Maestro V13

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image, ImageDraw

load_dotenv()

BRAIN_MODE_MODEL = "gemini-3-flash-preview"


def _get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    return genai.Client(api_key=api_key)


def _collect_response(response: Any) -> dict[str, Any]:
    from knowledge.gemini_service import _collect_response as collect

    return collect(response)


def _save_trace(trace: list[dict[str, Any]], images: list[bytes], directory: str | Path, prefix: str = "trace") -> list[dict[str, Any]]:
    from knowledge.gemini_service import _save_trace as save

    return save(trace, images, directory, prefix)


def _normalize_bbox_to_pixels(bbox: dict[str, Any], width: int, height: int) -> tuple[int, int, int, int]:
    x0 = max(0, min(width, int((float(bbox.get("x0", 0)) / 1000.0) * width)))
    y0 = max(0, min(height, int((float(bbox.get("y0", 0)) / 1000.0) * height)))
    x1 = max(0, min(width, int((float(bbox.get("x1", 1000)) / 1000.0) * width)))
    y1 = max(0, min(height, int((float(bbox.get("y1", 1000)) / 1000.0) * height)))
    if x1 <= x0:
        x1 = min(width, x0 + 1)
    if y1 <= y0:
        y1 = min(height, y0 + 1)
    return x0, y0, x1, y1


def see_page(page_name: str, project: dict[str, Any] | None) -> str:
    """Look at a full page image and return Gemini's description."""
    if not project:
        return "No project loaded."
    page = project.get("pages", {}).get(page_name)
    if not page:
        return f"Page '{page_name}' not found"

    page_png = Path(page.get("path", "")) / "page.png"
    if not page_png.exists():
        return f"No image for '{page_name}'"

    client = _get_client()
    image_bytes = page_png.read_bytes()

    response = client.models.generate_content(
        model=BRAIN_MODE_MODEL,
        contents=[
            types.Content(
                parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                    types.Part.from_text(
                        text="You are Maestro, looking at a construction plan page. Describe the key zones, notes, dimensions, and details. Be concise and accurate."
                    ),
                ]
            )
        ],
        config=types.GenerateContentConfig(
            temperature=0,
            thinking_config=types.ThinkingConfig(thinking_level="medium"),
            tools=[types.Tool(code_execution=types.ToolCodeExecution)],
        ),
    )

    collected = _collect_response(response)
    page_dir = Path(page.get("path", ""))
    _save_trace(collected["trace"], collected["images"], page_dir, prefix="see_page")

    with (page_dir / "see_page_trace.json").open("w", encoding="utf-8") as f:
        json.dump(collected["trace"], f, indent=2)

    return collected.get("text", "")


def see_pointer(page_name: str, region_id: str, project: dict[str, Any] | None) -> str:
    """Look at a cropped pointer image and return Gemini's description."""
    if not project:
        return "No project loaded."
    page = project.get("pages", {}).get(page_name)
    if not page:
        return f"Page '{page_name}' not found"

    pointer = page.get("pointers", {}).get(region_id)
    if not pointer:
        return f"Region '{region_id}' not found"

    crop_path = Path(pointer.get("crop_path", ""))
    if not crop_path.exists():
        return f"No crop image for region '{region_id}'"

    client = _get_client()
    crop_bytes = crop_path.read_bytes()

    response = client.models.generate_content(
        model=BRAIN_MODE_MODEL,
        contents=[
            types.Content(
                parts=[
                    types.Part.from_bytes(data=crop_bytes, mime_type="image/png"),
                    types.Part.from_text(
                        text="You are Maestro, looking at a cropped construction detail. Describe dimensions, notes, materials, callouts, and visible constraints."
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
    pointer_dir = crop_path.parent
    _save_trace(collected["trace"], collected["images"], pointer_dir, prefix="see_pointer")

    with (pointer_dir / "see_pointer_trace.json").open("w", encoding="utf-8") as f:
        json.dump(collected["trace"], f, indent=2)

    return collected.get("text", "")


def find_missing_pointer(page_name: str, mission: str, project: dict[str, Any] | None) -> str:
    """
    Find a missing region on a page.
    Sends the page image with existing bboxes drawn in red.
    """
    if not project:
        return "No project loaded."
    page = project.get("pages", {}).get(page_name)
    if not page:
        return f"Page '{page_name}' not found"

    page_png = Path(page.get("path", "")) / "page.png"
    if not page_png.exists():
        return f"No image for '{page_name}'"

    img = Image.open(page_png).convert("RGB")
    draw = ImageDraw.Draw(img)
    width, height = img.size

    for region in page.get("regions", []):
        if not isinstance(region, dict):
            continue
        bbox = region.get("bbox", {})
        if not isinstance(bbox, dict):
            continue
        x0, y0, x1, y1 = _normalize_bbox_to_pixels(bbox, width, height)
        draw.rectangle([x0, y0, x1, y1], outline="red", width=3)
        label = region.get("label") or region.get("id", "")
        draw.text((x0 + 5, y0 + 5), str(label), fill="red")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    annotated_bytes = buffer.getvalue()

    client = _get_client()
    prompt = f"""You are Maestro's vision assistant.
This construction plan page already has known regions marked in red.

MISSION: {mission}

Use Python code execution to inspect the page and:
1) identify the missing target region not covered by existing red boxes,
2) draw a green box around it,
3) output normalized coordinates as: BBOX: x0, y0, x1, y1,
4) explain what is in that region.
"""

    response = client.models.generate_content(
        model=BRAIN_MODE_MODEL,
        contents=[
            types.Content(
                parts=[
                    types.Part.from_bytes(data=annotated_bytes, mime_type="image/png"),
                    types.Part.from_text(text=prompt),
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
    page_dir = Path(page.get("path", ""))
    _save_trace(collected["trace"], collected["images"], page_dir, prefix="find_missing")

    with (page_dir / "find_missing_trace.json").open("w", encoding="utf-8") as f:
        json.dump(collected["trace"], f, indent=2)

    return collected.get("text", "")


def double_check_pointer(page_name: str, region_id: str, mission: str, project: dict[str, Any] | None) -> str:
    """Run deeper agentic visual inspection on one pointer crop."""
    if not project:
        return "No project loaded."
    page = project.get("pages", {}).get(page_name)
    if not page:
        return f"Page '{page_name}' not found"

    pointer = page.get("pointers", {}).get(region_id)
    if not pointer:
        return f"Region '{region_id}' not found"

    crop_path = Path(pointer.get("crop_path", ""))
    if not crop_path.exists():
        return f"No crop image for region '{region_id}'"

    client = _get_client()
    crop_bytes = crop_path.read_bytes()

    prompt = f"""You are Maestro's deep inspection system.
MISSION: {mission}

Use Python code execution to:
1) inspect and zoom where needed,
2) annotate important evidence in images,
3) read dimensions, notes, and callouts,
4) provide a detailed technical report,
5) explicitly note any uncertainty.
"""

    response = client.models.generate_content(
        model=BRAIN_MODE_MODEL,
        contents=[
            types.Content(
                parts=[
                    types.Part.from_bytes(data=crop_bytes, mime_type="image/png"),
                    types.Part.from_text(text=prompt),
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
    pointer_dir = crop_path.parent
    _save_trace(collected["trace"], collected["images"], pointer_dir, prefix="doublecheck")

    with (pointer_dir / "doublecheck_trace.json").open("w", encoding="utf-8") as f:
        json.dump(collected["trace"], f, indent=2)

    return collected.get("text", "")

