from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from knowledge.gemini_service import _extract_json_from_text

load_dotenv()

LEARNING_MODEL = "gpt-5.2"
REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "generate_patches.txt"
VALID_OPERATIONS = {"set", "append_unique"}


def _get_client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _load_prompt() -> str:
    if not PROMPT_PATH.exists():
        return "Generate safe patch proposals as JSON."
    return PROMPT_PATH.read_text(encoding="utf-8")


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)
    tmp_path.replace(path)


def _read_json_default(path: Path, default: Any) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return copy.deepcopy(default)
    return data


def _resolve_target_path(target: str) -> Path:
    raw = str(target).strip()
    path = Path(raw)
    if path.is_absolute():
        return path
    if raw.startswith("identity/") or raw.startswith("experience/"):
        return (REPO_ROOT / "maestro" / raw).resolve()
    return (REPO_ROOT / raw).resolve()


def _is_denylisted(path: Path) -> bool:
    if path.suffix.lower() == ".py":
        return True
    if path.name == "soul.json" and "identity" in path.parts and "experience" in path.parts:
        return True
    return False


def _is_allowed_target(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except Exception:
        return False

    tools_path = (REPO_ROOT / "maestro/identity/experience/tools.json").resolve()
    patterns_path = (REPO_ROOT / "maestro/identity/experience/patterns.json").resolve()
    disciplines_root = (REPO_ROOT / "maestro/identity/experience/disciplines").resolve()
    knowledge_store_root = (REPO_ROOT / "knowledge_store").resolve()

    if resolved == tools_path or resolved == patterns_path:
        return True

    if disciplines_root in resolved.parents and resolved.suffix == ".json":
        return True

    if knowledge_store_root in resolved.parents and resolved.name in {"pass1.json", "pass2.json"}:
        return True

    return False


def _parse_path(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    for segment in str(path).strip().split("."):
        if not segment:
            continue
        for match in re.finditer(r"([^\[\]]+)|\[(\d+)\]", segment):
            key = match.group(1)
            idx = match.group(2)
            if key is not None and key != "":
                tokens.append(key)
            elif idx is not None:
                tokens.append(int(idx))
    return tokens


def _get_value(data: Any, tokens: list[str | int]) -> tuple[Any, bool]:
    current = data
    for token in tokens:
        if isinstance(token, int):
            if not isinstance(current, list) or token < 0 or token >= len(current):
                return None, False
            current = current[token]
            continue
        if not isinstance(current, dict) or token not in current:
            return None, False
        current = current[token]
    return copy.deepcopy(current), True


def _ensure_parent(data: Any, tokens: list[str | int]) -> tuple[Any, str | int | None]:
    if not tokens:
        return None, None

    current = data
    for idx, token in enumerate(tokens[:-1]):
        next_token = tokens[idx + 1]
        if isinstance(token, int):
            if not isinstance(current, list):
                return None, None
            while token >= len(current):
                current.append({} if isinstance(next_token, str) else [])
            if current[token] is None:
                current[token] = {} if isinstance(next_token, str) else []
            current = current[token]
        else:
            if not isinstance(current, dict):
                return None, None
            if token not in current or current[token] is None:
                current[token] = {} if isinstance(next_token, str) else []
            current = current[token]

    return current, tokens[-1]


def _set_value(data: Any, path: str, value: Any) -> tuple[bool, str]:
    tokens = _parse_path(path)
    parent, leaf = _ensure_parent(data, tokens)
    if parent is None or leaf is None:
        return False, "invalid_path_for_set"

    if isinstance(leaf, int):
        if not isinstance(parent, list):
            return False, "set_target_not_list"
        while leaf >= len(parent):
            parent.append(None)
        parent[leaf] = value
        return True, "set_ok"

    if not isinstance(parent, dict):
        return False, "set_target_not_dict"
    parent[leaf] = value
    return True, "set_ok"


def _append_unique(data: Any, path: str, value: Any) -> tuple[bool, str]:
    tokens = _parse_path(path)
    parent, leaf = _ensure_parent(data, tokens)
    if parent is None or leaf is None:
        return False, "invalid_path_for_append"

    target: Any
    if isinstance(leaf, int):
        if not isinstance(parent, list):
            return False, "append_target_not_list_parent"
        while leaf >= len(parent):
            parent.append([])
        if not isinstance(parent[leaf], list):
            parent[leaf] = []
        target = parent[leaf]
    else:
        if not isinstance(parent, dict):
            return False, "append_target_not_dict_parent"
        if leaf not in parent or not isinstance(parent[leaf], list):
            parent[leaf] = []
        target = parent[leaf]

    if value in target:
        return False, "append_duplicate"
    target.append(value)
    return True, "append_ok"


def _validate_patch_candidates(raw_patches: Any) -> list[dict[str, Any]]:
    patches: list[dict[str, Any]] = []
    if not isinstance(raw_patches, list):
        return patches

    for idx, raw in enumerate(raw_patches, start=1):
        if not isinstance(raw, dict):
            continue
        target = str(raw.get("target", "")).strip()
        operation = str(raw.get("operation", "")).strip().lower()
        path = str(raw.get("path", "")).strip()
        if not target or operation not in VALID_OPERATIONS or not path:
            continue

        patches.append(
            {
                "patch_id": str(raw.get("patch_id", f"p_{idx:03d}")).strip() or f"p_{idx:03d}",
                "type": str(raw.get("type", "unknown")).strip() or "unknown",
                "target": target,
                "operation": operation,
                "path": path,
                "value": raw.get("value"),
                "reason": str(raw.get("reason", "")).strip(),
                "claim_id": str(raw.get("claim_id", "")).strip(),
            }
        )
    return patches


def generate_patch_candidates(
    job: dict[str, Any],
    claims: list[dict[str, Any]],
    verifications: list[dict[str, Any]],
    scores: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    prompt = _load_prompt()
    payload = {
        "job_type": job.get("type", "unknown"),
        "claims": claims,
        "verification_results": verifications,
        "scores": scores,
    }

    try:
        response = _get_client().chat.completions.create(
            model=LEARNING_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        "Generate patch proposals. Return JSON only.\n\n"
                        f"{json.dumps(payload, indent=2, ensure_ascii=True)}"
                    ),
                },
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        parsed = _extract_json_from_text(raw)
        patches = _validate_patch_candidates(parsed.get("patches", []))
    except Exception as exc:
        errors.append(f"patch_generation_error: {type(exc).__name__}: {exc}")
        patches = []

    return patches, errors


def generate_and_apply_patches(
    job: dict[str, Any],
    claims: list[dict[str, Any]],
    verifications: list[dict[str, Any]],
    scores: list[dict[str, Any]],
    mode: str | None = None,
) -> dict[str, Any]:
    patch_mode = (mode or os.getenv("MAESTRO_LEARNING_PATCH_MODE", "shadow")).strip().lower()
    if patch_mode not in {"shadow", "live"}:
        patch_mode = "shadow"

    proposed, errors = generate_patch_candidates(job, claims, verifications, scores)
    proposed_with_metadata: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []

    for patch in proposed:
        target_path = _resolve_target_path(str(patch.get("target", "")))
        denied = _is_denylisted(target_path)
        allowed = _is_allowed_target(target_path)
        json_data = _read_json_default(target_path, {}) if target_path.exists() else {}

        tokens = _parse_path(str(patch.get("path", "")))
        old_value, existed = _get_value(json_data, tokens)

        enriched = dict(patch)
        enriched["target_resolved"] = str(target_path)
        enriched["allowed"] = allowed
        enriched["denied"] = denied
        enriched["old_value"] = old_value if existed else None
        enriched["mode"] = patch_mode
        proposed_with_metadata.append(enriched)

        if denied:
            errors.append(f"patch_denied: {patch.get('patch_id')} target is denylisted")
            continue
        if not allowed:
            errors.append(f"patch_disallowed: {patch.get('patch_id')} target is not in allowlist")
            continue
        if patch_mode != "live":
            continue

        operation = str(patch.get("operation", "")).strip().lower()
        target_data = _read_json_default(target_path, {})
        if operation == "set":
            ok, message = _set_value(target_data, str(patch.get("path", "")), patch.get("value"))
        elif operation == "append_unique":
            ok, message = _append_unique(target_data, str(patch.get("path", "")), patch.get("value"))
        else:
            ok, message = False, "unknown_operation"

        if not ok:
            errors.append(f"patch_apply_failed: {patch.get('patch_id')} {message}")
            continue

        _write_json_atomic(target_path, target_data)
        applied_patch = dict(enriched)
        applied_patch["applied"] = True
        applied_patch["apply_message"] = message
        applied.append(applied_patch)

    return {
        "mode": patch_mode,
        "proposed": proposed_with_metadata,
        "applied": applied,
        "errors": errors,
    }
