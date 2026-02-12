from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from knowledge.gemini_service import _extract_json_from_text

load_dotenv()

LEARNING_MODEL = "gpt-5.2"
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "extract_claims.txt"


def _get_client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _load_prompt() -> str:
    if not PROMPT_PATH.exists():
        return "Extract verifiable claims as JSON."
    return PROMPT_PATH.read_text(encoding="utf-8")


def _normalize_priority(value: Any) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"high", "medium", "low"}:
        return normalized
    return "medium"


def _normalize_claim_type(value: Any) -> str:
    normalized = str(value).strip().lower()
    if normalized:
        return normalized
    return "unknown"


def _validate_claims(raw_claims: Any) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    if not isinstance(raw_claims, list):
        return claims

    for idx, item in enumerate(raw_claims, start=1):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue

        claim = {
            "claim_id": str(item.get("claim_id", f"c_{idx:03d}")).strip() or f"c_{idx:03d}",
            "text": text,
            "source_page": str(item.get("source_page", "")).strip(),
            "claim_type": _normalize_claim_type(item.get("claim_type", "unknown")),
            "verification_priority": _normalize_priority(item.get("verification_priority", "medium")),
            "source_anchor": str(item.get("source_anchor", "")).strip(),
        }
        claims.append(claim)
    return claims


def extract_claims(job: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Extract verifiable claims from a queued learning job.

    Returns:
      (claims, errors)
    """
    errors: list[str] = []
    prompt = _load_prompt()

    user_payload = {
        "job_type": job.get("type", "unknown"),
        "workspace_slug": job.get("workspace_slug"),
        "workspace_snapshot": job.get("workspace_snapshot"),
        "user_message": job.get("user_message", ""),
        "assistant_response": job.get("assistant_response", ""),
        "prior_assistant_response": job.get("prior_assistant_response", ""),
        "prior_tool_calls": job.get("prior_tool_calls", []),
        "relevant_pages": job.get("relevant_pages", []),
    }

    try:
        response = _get_client().chat.completions.create(
            model=LEARNING_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        "Extract claims from the following job context. "
                        "Return JSON only.\n\n"
                        f"{json.dumps(user_payload, indent=2, ensure_ascii=True)}"
                    ),
                },
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        parsed = _extract_json_from_text(raw)
    except Exception as exc:
        errors.append(f"claim_extraction_error: {type(exc).__name__}: {exc}")
        return [], errors

    claims = _validate_claims(parsed.get("claims", []))
    if not claims:
        errors.append("claim_extraction_empty: no valid claims extracted")
    return claims, errors
