from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from openai import OpenAI
from PIL import Image

from knowledge.gemini_service import _collect_response, _extract_json_from_text, _save_trace

load_dotenv()

LEARNING_MODEL = "gpt-5.2"
VISION_MODEL = "gemini-3-flash-preview"
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "build_missions.txt"


def _get_openai_client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


_gemini_client: genai.Client | None = None

def _get_gemini_client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def _load_prompt() -> str:
    if not PROMPT_PATH.exists():
        return "Build one mission per source page from the claim list."
    return PROMPT_PATH.read_text(encoding="utf-8")


def _normalize_page_token(value: str) -> str:
    return (
        str(value)
        .lower()
        .replace(".", "_")
        .replace("-", "_")
        .replace(" ", "_")
        .strip("_")
    )


def _validate_missions(raw_missions: Any, claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    missions: list[dict[str, Any]] = []
    if not isinstance(raw_missions, list):
        return missions

    claim_ids = {str(item.get("claim_id", "")).strip() for item in claims if isinstance(item, dict)}
    for idx, item in enumerate(raw_missions, start=1):
        if not isinstance(item, dict):
            continue
        target_page = str(item.get("target_page", "")).strip()
        instruction = str(item.get("instruction", "")).strip()
        if not target_page or not instruction:
            continue

        raw_claim_ids = item.get("claim_ids", [])
        if not isinstance(raw_claim_ids, list):
            raw_claim_ids = []
        cleaned_claim_ids = [str(c).strip() for c in raw_claim_ids if str(c).strip() in claim_ids]
        if not cleaned_claim_ids:
            continue

        expected = item.get("expected_values", {})
        if not isinstance(expected, dict):
            expected = {}

        missions.append(
            {
                "mission_id": str(item.get("mission_id", f"m_{idx:03d}")).strip() or f"m_{idx:03d}",
                "claim_ids": cleaned_claim_ids,
                "target_page": target_page,
                "instruction": instruction,
                "expected_values": expected,
            }
        )
    return missions


def _fallback_grouped_missions(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for claim in claims:
        source_page = str(claim.get("source_page", "")).strip()
        if not source_page:
            continue
        grouped.setdefault(source_page, []).append(claim)

    missions: list[dict[str, Any]] = []
    for idx, (page, page_claims) in enumerate(sorted(grouped.items()), start=1):
        expected: dict[str, str] = {}
        for claim in page_claims:
            claim_id = str(claim.get("claim_id", "")).strip()
            if claim_id:
                expected[claim_id] = str(claim.get("text", "")).strip()
        missions.append(
            {
                "mission_id": f"m_{idx:03d}",
                "claim_ids": [str(item.get("claim_id", "")).strip() for item in page_claims if item.get("claim_id")],
                "target_page": page,
                "instruction": (
                    "Verify each claim against the page. Quote evidence text and dimensions if visible. "
                    "If not found, say not found."
                ),
                "expected_values": expected,
            }
        )
    return missions


def build_missions(job: dict[str, Any], claims: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not claims:
        return [], ["mission_build_skipped: no claims"]

    prompt = _load_prompt()
    user_payload = {
        "job_type": job.get("type", "unknown"),
        "claims": claims,
    }

    try:
        response = _get_openai_client().chat.completions.create(
            model=LEARNING_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        "Build page-batched missions from the claims below. Return JSON only.\n\n"
                        f"{json.dumps(user_payload, indent=2, ensure_ascii=True)}"
                    ),
                },
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        parsed = _extract_json_from_text(raw)
        missions = _validate_missions(parsed.get("missions", []), claims)
    except Exception as exc:
        errors.append(f"mission_builder_error: {type(exc).__name__}: {exc}")
        missions = []

    if not missions:
        fallback = _fallback_grouped_missions(claims)
        if fallback:
            errors.append("mission_builder_fallback: generated deterministic missions")
            missions = fallback

    if not missions:
        errors.append("mission_builder_empty: no missions generated")
    return missions, errors


def _resolve_project_page(project: dict[str, Any], target_page: str) -> dict[str, Any] | None:
    pages = project.get("pages", {})
    if not isinstance(pages, dict):
        return None

    if target_page in pages:
        return pages[target_page]

    norm_target = _normalize_page_token(target_page)
    if not norm_target:
        return None

    candidates: list[dict[str, Any]] = []
    for page_name, page in pages.items():
        norm_name = _normalize_page_token(page_name)
        if norm_name == norm_target or norm_name.startswith(norm_target) or norm_target in norm_name:
            if isinstance(page, dict):
                candidates.append(page)

    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        return candidates[0]
    return None


def verify_mission(
    mission: dict[str, Any],
    project: dict[str, Any] | None,
    trace_directory: Path,
    gemini_client: genai.Client | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "mission_id": mission.get("mission_id"),
        "claim_ids": mission.get("claim_ids", []),
        "target_page": mission.get("target_page", ""),
        "instruction": mission.get("instruction", ""),
        "expected_values": mission.get("expected_values", {}),
    }

    if not project:
        result["verification_status"] = "error"
        result["error"] = "No project loaded. Run ingest before learning verification."
        return result

    page = _resolve_project_page(project, str(mission.get("target_page", "")))
    if not page:
        result["verification_status"] = "error"
        result["error"] = f"Target page not found: {mission.get('target_page', '')}"
        return result

    page_path = Path(str(page.get("path", "")))
    page_png = page_path / "page.png"
    if not page_png.exists():
        result["verification_status"] = "error"
        result["error"] = f"Page image not found: {page_png}"
        return result

    prompt = (
        "You are verifying construction-plan claims.\n"
        f"MISSION: {mission.get('instruction', '')}\n"
        f"EXPECTED: {json.dumps(mission.get('expected_values', {}), ensure_ascii=True)}\n\n"
        "Return concise findings with evidence quotes, values found, and any conflicts."
    )

    # Convert to JPEG at 50% scale for fast Gemini processing
    # (7MB PNGs with thinking=high take 5+ min; 1.3MB JPEGs take 12s with same quality)
    try:
        img = Image.open(page_png)
        img_half = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
        buf = io.BytesIO()
        img_half.convert("RGB").save(buf, format="JPEG", quality=80)
        image_bytes = buf.getvalue()
        image_mime = "image/jpeg"
        print(f"    [Learning Vision] JPEG {len(image_bytes)//1024}KB from {page_png.name}")
    except Exception as exc:
        image_bytes = page_png.read_bytes()
        image_mime = "image/png"
        print(f"    [Learning Vision] PNG fallback ({exc}) {len(image_bytes)//1024}KB")

    try:
        client = gemini_client or _get_gemini_client()
        response = client.models.generate_content(
            model=VISION_MODEL,
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_bytes(data=image_bytes, mime_type=image_mime),
                        types.Part.from_text(text=prompt),
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0,
                thinking_config=types.ThinkingConfig(thinking_level="high"),
            ),
        )
        collected = _collect_response(response)
    except Exception as exc:
        result["verification_status"] = "error"
        result["error"] = f"vision_error: {type(exc).__name__}: {exc}"
        return result

    trace_directory.mkdir(parents=True, exist_ok=True)
    prefix = f"mission_{result.get('mission_id', 'unknown')}"
    trace = _save_trace(collected["trace"], collected["images"], trace_directory, prefix=prefix)
    trace_path = trace_directory / f"{prefix}_trace.json"
    with trace_path.open("w", encoding="utf-8") as f:
        json.dump(trace, f, indent=2, ensure_ascii=True)

    result["verification_status"] = "ok"
    result["findings"] = collected.get("text", "")
    result["trace_path"] = str(trace_path)
    return result
