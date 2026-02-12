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
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "score_results.txt"
VALID_SCORES = {"verified", "corrected", "enriched", "ungrounded", "conflict"}
_SOURCE_PRIORITY = {
    "detail": 5,
    "enlarged_plan": 4,
    "schedule": 3,
    "general_notes": 2,
    "spec": 1,
}


def _get_client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _load_prompt() -> str:
    if not PROMPT_PATH.exists():
        return "Score each claim using verified/corrected/enriched/ungrounded/conflict."
    return PROMPT_PATH.read_text(encoding="utf-8")


def _normalize_confidence(value: Any) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"high", "medium", "low"}:
        return normalized
    return "medium"


def _normalize_source_kind(value: str) -> str:
    token = (
        value.lower()
        .replace("-", "_")
        .replace(" ", "_")
        .replace("/", "_")
        .strip("_")
    )
    if "detail" in token:
        return "detail"
    if "enlarged" in token:
        return "enlarged_plan"
    if "schedule" in token:
        return "schedule"
    if "general_note" in token or "generalnotes" in token:
        return "general_notes"
    if "spec" in token:
        return "spec"
    return token or "unknown"


def _resolve_conflict_by_hierarchy(score: dict[str, Any]) -> None:
    if score.get("score") != "conflict":
        return
    candidates = score.get("conflict_candidates")
    if not isinstance(candidates, list) or not candidates:
        score["resolution"] = "source_hierarchy_unavailable"
        return

    best_candidate: dict[str, Any] | None = None
    best_rank = -1

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        source_kind = _normalize_source_kind(str(candidate.get("source", "")))
        rank = _SOURCE_PRIORITY.get(source_kind, 0)
        if rank > best_rank:
            best_rank = rank
            best_candidate = candidate

    if not best_candidate:
        score["resolution"] = "source_hierarchy_unavailable"
        return

    source_kind = _normalize_source_kind(str(best_candidate.get("source", "")))
    score["resolution"] = source_kind
    score["resolved_value"] = best_candidate.get("value")
    score["action_taken"] = (
        f"resolved_by_hierarchy:{source_kind}"
        if best_rank > 0
        else "resolved_by_hierarchy:unknown"
    )


def _validate_scores(raw_scores: Any, claim_ids: set[str]) -> list[dict[str, Any]]:
    scores: list[dict[str, Any]] = []
    if not isinstance(raw_scores, list):
        return scores

    for item in raw_scores:
        if not isinstance(item, dict):
            continue
        claim_id = str(item.get("claim_id", "")).strip()
        if not claim_id or claim_id not in claim_ids:
            continue
        score_value = str(item.get("score", "")).strip().lower()
        if score_value not in VALID_SCORES:
            continue

        score: dict[str, Any] = {
            "claim_id": claim_id,
            "score": score_value,
            "vision_found": str(item.get("vision_found", "")).strip(),
            "confidence": _normalize_confidence(item.get("confidence", "medium")),
            "rationale": str(item.get("rationale", "")).strip(),
            "action_taken": item.get("action_taken"),
        }
        if isinstance(item.get("conflict_candidates"), list):
            score["conflict_candidates"] = item["conflict_candidates"]

        _resolve_conflict_by_hierarchy(score)
        scores.append(score)
    return scores


def _fallback_scores(claims: list[dict[str, Any]], verifications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    verification_by_claim: dict[str, dict[str, Any]] = {}
    for verification in verifications:
        if not isinstance(verification, dict):
            continue
        for claim_id in verification.get("claim_ids", []):
            claim_key = str(claim_id).strip()
            if claim_key:
                verification_by_claim[claim_key] = verification

    scores: list[dict[str, Any]] = []
    for claim in claims:
        claim_id = str(claim.get("claim_id", "")).strip()
        if not claim_id:
            continue
        verification = verification_by_claim.get(claim_id, {})
        error = str(verification.get("error", "")).strip()
        if error:
            score_value = "ungrounded"
            confidence = "low"
            rationale = error
        else:
            score_value = "verified"
            confidence = "low"
            rationale = "fallback_scoring_no_model_decision"
        scores.append(
            {
                "claim_id": claim_id,
                "score": score_value,
                "vision_found": str(verification.get("findings", "")).strip()[:500],
                "confidence": confidence,
                "rationale": rationale,
                "action_taken": None,
            }
        )
    return scores


def score_claims(
    job: dict[str, Any],
    claims: list[dict[str, Any]],
    verifications: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not claims:
        return [], ["scoring_skipped: no claims"]

    claim_ids = {str(item.get("claim_id", "")).strip() for item in claims if isinstance(item, dict)}
    claim_ids.discard("")

    payload = {
        "job_type": job.get("type", "unknown"),
        "claims": claims,
        "verification_results": verifications,
    }

    prompt = _load_prompt()

    try:
        response = _get_client().chat.completions.create(
            model=LEARNING_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        "Score all claims and return JSON only.\n\n"
                        f"{json.dumps(payload, indent=2, ensure_ascii=True)}"
                    ),
                },
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        parsed = _extract_json_from_text(raw)
        scores = _validate_scores(parsed.get("scores", []), claim_ids)
    except Exception as exc:
        errors.append(f"scoring_model_error: {type(exc).__name__}: {exc}")
        scores = []

    if not scores:
        scores = _fallback_scores(claims, verifications)
        if scores:
            errors.append("scoring_fallback_used: deterministic fallback")

    if not scores:
        errors.append("scoring_empty: no scores produced")
    return scores, errors
