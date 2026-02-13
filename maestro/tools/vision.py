# vision.py - On-demand visual inspection tools for Maestro V13
#
# see_page / see_pointer: Return image bytes for Opus native multimodal vision
# gemini_vision_agent: Dispatch Gemini as a specialist for deep extraction

from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

load_dotenv()

GEMINI_MODEL = "gemini-3-flash-preview"


def _get_gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    return genai.Client(api_key=api_key)


def _image_to_base64(image_path: Path, max_bytes: int = 4_000_000, max_dim: int = 7999) -> dict[str, Any]:
    """Read an image and return a base64-encoded content block for Anthropic multimodal.
    
    Resizes if file exceeds max_bytes or any dimension exceeds max_dim (Anthropic limit: 8000px).
    """
    img = Image.open(image_path)
    w, h = img.size
    media_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"

    needs_resize = w > max_dim or h > max_dim or image_path.stat().st_size > max_bytes

    # Always scale to fit within max_dim and convert to JPEG for size
    scale = min(max_dim / w, max_dim / h, 1.0)
    if needs_resize or True:  # Always optimize for API
        scale = min(scale, 0.5) if (w * h) > 4_000_000 else scale
        new_w, new_h = int(w * scale), int(h * scale)
        if new_w != w or new_h != h:
            img = img.resize((new_w, new_h), Image.LANCZOS)

    # Convert to JPEG — much smaller than PNG for construction plans
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


def _png_to_jpeg_bytes(png_path: Path, scale: float = 0.5, quality: int = 85) -> bytes:
    """Convert a PNG to scaled JPEG bytes for Gemini API (faster, smaller)."""
    img = Image.open(png_path).convert("RGB")
    w, h = img.size
    img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def see_page(page_name: str, project: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return page image as multimodal content blocks for Opus to see directly."""
    if not project:
        return [{"type": "text", "text": "No project loaded."}]
    page = project.get("pages", {}).get(page_name)
    if not page:
        return [{"type": "text", "text": f"Page '{page_name}' not found"}]

    page_png = Path(page.get("path", "")) / "page.png"
    if not page_png.exists():
        return [{"type": "text", "text": f"No image for '{page_name}'"}]

    image_block = _image_to_base64(page_png)
    return [
        image_block,
        {"type": "text", "text": f"This is page '{page_name}'. You are looking at it directly. Describe what you see."},
    ]


def see_pointer(page_name: str, region_id: str, project: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return cropped region image as multimodal content blocks for Opus to see directly."""
    if not project:
        return [{"type": "text", "text": "No project loaded."}]
    page = project.get("pages", {}).get(page_name)
    if not page:
        return [{"type": "text", "text": f"Page '{page_name}' not found"}]

    pointer = page.get("pointers", {}).get(region_id)
    if not pointer:
        return [{"type": "text", "text": f"Region '{region_id}' not found on '{page_name}'"}]

    crop_path = Path(pointer.get("crop_path", ""))
    if not crop_path.exists():
        return [{"type": "text", "text": f"No crop image for region '{region_id}'"}]

    image_block = _image_to_base64(crop_path)
    return [
        image_block,
        {"type": "text", "text": f"This is region '{region_id}' on page '{page_name}'. You are looking at the cropped detail directly."},
    ]


def gemini_vision_agent(page_name: str, mission: str, project: dict[str, Any] | None) -> str:
    """Dispatch Gemini as a vision specialist for deep extraction on a page.
    
    Converts PNG to JPEG at 50% scale for speed (proven: 12s vs 312s).
    Uses thinking=high for maximum accuracy.
    """
    if not project:
        return "No project loaded."
    page = project.get("pages", {}).get(page_name)
    if not page:
        return f"Page '{page_name}' not found"

    page_png = Path(page.get("path", "")) / "page.png"
    if not page_png.exists():
        return f"No image for '{page_name}'"

    # Convert to JPEG for fast Gemini processing
    jpeg_bytes = _png_to_jpeg_bytes(page_png)

    client = _get_gemini_client()

    prompt = f"""You are Maestro's vision specialist inspecting a construction plan page.

PAGE: {page_name}

MISSION: {mission}

Inspect the page carefully. Report your findings with specific details:
- Exact dimensions, notes, and callouts you can read
- Locations of relevant items (describe position on the page)
- Any text, labels, or annotations visible
- Confidence level for each finding

Be precise and thorough. The superintendent needs accurate information."""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Content(
                parts=[
                    types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
                    types.Part.from_text(text=prompt),
                ]
            )
        ],
        config=types.GenerateContentConfig(
            temperature=0,
            thinking_config=types.ThinkingConfig(thinking_level="high"),
        ),
    )

    # Extract text from response
    result_text = ""
    if response.candidates:
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                result_text += part.text

    # Save trace
    page_dir = Path(page.get("path", ""))
    trace = {
        "tool": "gemini_vision_agent",
        "page": page_name,
        "mission": mission,
        "model": GEMINI_MODEL,
        "result": result_text[:2000],
    }
    try:
        with (page_dir / "gemini_vision_trace.json").open("w", encoding="utf-8") as f:
            json.dump(trace, f, indent=2)
    except OSError:
        pass

    return result_text or "No response from Gemini."
