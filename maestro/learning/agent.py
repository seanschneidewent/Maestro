from __future__ import annotations

import atexit
import json
import os
import re
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from knowledge.knowledge_v13 import load_project
from tools import workspaces

from . import claims, missions, patcher, queue, scorer, status

REPO_ROOT = Path(__file__).resolve().parents[2]
LEARNING_LOG_PATH = REPO_ROOT / "maestro/identity/experience/learning_log.json"

_WORKER_THREAD: threading.Thread | None = None
_MUTATING_WORKSPACE_TOOLS = {"create_workspace", "add_page", "remove_page", "add_note"}
_CORRECTION_PATTERNS = [
    re.compile(r"\bthat(?:'s| is)\s+wrong\b", re.IGNORECASE),
    re.compile(r"\byou(?:'re| are)\s+wrong\b", re.IGNORECASE),
    re.compile(r"\b(?:that(?:'s| is)\s+)?incorrect\b", re.IGNORECASE),
    re.compile(r"\bthat(?:'s| is)\s+not\s+correct\b", re.IGNORECASE),
    re.compile(r"\bcorrection\b", re.IGNORECASE),
    re.compile(r"^\s*no[, ]+\s+that(?:'s| is)\s+wrong\b", re.IGNORECASE),
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def learning_enabled() -> bool:
    raw = os.getenv("MAESTRO_LEARNING_ENABLED", "1").strip().lower()
    return raw not in {"0", "false", "off", "no"}


def is_explicit_correction(message: str) -> bool:
    text = str(message or "").strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in _CORRECTION_PATTERNS)


def extract_relevant_pages(tool_calls: list[dict[str, Any]]) -> list[str]:
    pages: set[str] = set()
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        args = call.get("args", {})
        result = call.get("result")

        if isinstance(args, dict):
            page_name = args.get("page_name")
            if isinstance(page_name, str) and page_name.strip():
                pages.add(page_name.strip())
            source_page = args.get("source_page")
            if isinstance(source_page, str) and source_page.strip():
                pages.add(source_page.strip())

        if isinstance(result, dict):
            maybe_page = result.get("page_name")
            if isinstance(maybe_page, str) and maybe_page.strip():
                pages.add(maybe_page.strip())
    return sorted(pages)


def mutated_workspace_slug_from_tool_call(
    tool_name: str,
    tool_args: dict[str, Any],
    tool_result: Any,
) -> str | None:
    if tool_name not in _MUTATING_WORKSPACE_TOOLS:
        return None
    if not isinstance(tool_result, dict):
        return None

    if tool_name == "create_workspace":
        slug = tool_result.get("slug")
    else:
        slug = tool_result.get("workspace_slug")
        if not slug:
            slug = tool_args.get("workspace_slug")

    if isinstance(slug, str) and slug.strip():
        return slug.strip()
    return None


def enqueue_workspace_job(
    *,
    workspace_slug: str,
    user_message: str,
    assistant_response: str,
    tool_calls: list[dict[str, Any]],
) -> Path | None:
    if not learning_enabled():
        return None

    snapshot = workspaces.get_workspace(workspace_slug)
    snapshot_payload: dict[str, Any]
    if isinstance(snapshot, dict):
        snapshot_payload = snapshot
    else:
        snapshot_payload = {"workspace_slug": workspace_slug, "error": str(snapshot)}

    return queue.enqueue_workspace_entry(
        workspace_slug=workspace_slug,
        workspace_snapshot=snapshot_payload,
        user_message=user_message,
        assistant_response=assistant_response,
        tool_calls=tool_calls,
        engine="opus",
    )


def enqueue_feedback_job(
    *,
    user_message: str,
    prior_assistant_response: str,
    prior_tool_calls: list[dict[str, Any]],
) -> Path | None:
    if not learning_enabled():
        return None

    return queue.enqueue_feedback_entry(
        user_message=user_message,
        prior_assistant_response=prior_assistant_response,
        prior_tool_calls=prior_tool_calls,
        relevant_pages=extract_relevant_pages(prior_tool_calls),
        engine="opus",
    )


def _read_log() -> list[dict[str, Any]]:
    if not LEARNING_LOG_PATH.exists():
        return []
    try:
        data = json.loads(LEARNING_LOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, list):
        return data
    return []


def _write_log(entries: list[dict[str, Any]]) -> None:
    LEARNING_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = LEARNING_LOG_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=True)
    tmp_path.replace(LEARNING_LOG_PATH)


def _append_log_entry(entry: dict[str, Any]) -> None:
    entries = _read_log()
    entries.append(entry)
    _write_log(entries)


def _score_counts(scores: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"verified": 0, "corrected": 0, "enriched": 0, "ungrounded": 0, "conflict": 0}
    for score in scores:
        key = str(score.get("score", "")).strip().lower()
        if key in counts:
            counts[key] += 1
    return counts


def run_learning_job(job: dict[str, Any], artifacts_dir: Path | None = None) -> dict[str, Any]:
    job_id = str(job.get("id", "unknown"))
    trace_dir = artifacts_dir or (queue.DONE_DIR / f"{job_id}_artifacts")

    claims_data: list[dict[str, Any]] = []
    mission_plan: list[dict[str, Any]] = []
    mission_results: list[dict[str, Any]] = []
    scores_data: list[dict[str, Any]] = []
    patches_proposed: list[dict[str, Any]] = []
    patches_applied: list[dict[str, Any]] = []
    errors: list[str] = []
    trace_paths: list[str] = []

    status.write_status(True, f"Extracting claims ({job_id})...")
    claims_data, claim_errors = claims.extract_claims(job)
    errors.extend(claim_errors)

    status.write_status(True, f"Building missions ({job_id})...")
    mission_plan, mission_errors = missions.build_missions(job, claims_data)
    errors.extend(mission_errors)

    project = load_project()

    for idx, mission in enumerate(mission_plan, start=1):
        status.write_status(
            True,
            f"Vision verifying {idx}/{len(mission_plan)} ({job_id})...",
            details={"target_page": mission.get("target_page", "")},
        )
        mission_result = missions.verify_mission(mission, project, trace_dir)
        mission_results.append(mission_result)
        trace_path = mission_result.get("trace_path")
        if isinstance(trace_path, str) and trace_path.strip():
            trace_paths.append(trace_path)
        if mission_result.get("error"):
            errors.append(str(mission_result["error"]))

    status.write_status(True, f"Scoring claims ({job_id})...")
    scores_data, scoring_errors = scorer.score_claims(job, claims_data, mission_results)
    errors.extend(scoring_errors)

    status.write_status(True, f"Generating patches ({job_id})...")
    patch_result = patcher.generate_and_apply_patches(job, claims_data, mission_results, scores_data)
    patches_proposed = patch_result.get("proposed", [])
    patches_applied = patch_result.get("applied", [])
    errors.extend(patch_result.get("errors", []))

    counts = _score_counts(scores_data)
    status.write_status(
        True,
        (
            f"Complete [ok] {counts['verified']} verified | {counts['corrected']} corrected | "
            f"{counts['enriched']} enriched | {counts['conflict']} conflict | {counts['ungrounded']} ungrounded"
        ),
    )

    return {
        "claims": claims_data,
        "mission_plan": mission_plan,
        "missions": mission_results,
        "scores": scores_data,
        "patches_proposed": patches_proposed,
        "patches_applied": patches_applied,
        "errors": errors,
        "trace_paths": trace_paths,
        "patch_mode": patch_result.get("mode", "shadow"),
    }


def _process_claimed_job(processing_path: Path, job: dict[str, Any]) -> None:
    job_id = str(job.get("id", processing_path.stem))
    result_payload: dict[str, Any]
    done_status = "done"
    errors: list[str]

    try:
        result_payload = run_learning_job(job)
        errors = [str(err) for err in result_payload.get("errors", [])]
    except Exception as exc:
        done_status = "error"
        tb = traceback.format_exc(limit=10)
        errors = [f"worker_exception: {type(exc).__name__}: {exc}", tb]
        result_payload = {
            "claims": [],
            "mission_plan": [],
            "missions": [],
            "scores": [],
            "patches_proposed": [],
            "patches_applied": [],
            "trace_paths": [],
            "errors": errors,
        }

    done_path = queue.finalize_job(
        processing_path,
        job,
        status=done_status,
        result=result_payload,
        errors=errors,
    )

    _append_log_entry(
        {
            "timestamp": _utc_now_iso(),
            "job_id": job_id,
            "job_type": job.get("type", "unknown"),
            "status": done_status,
            "done_path": str(done_path),
            "result": result_payload,
        }
    )
    status.clear_status()


def _worker_loop(poll_seconds: float) -> None:
    while True:
        claimed = queue.claim_next_job()
        if claimed is None:
            time.sleep(poll_seconds)
            continue
        processing_path, payload = claimed
        _process_claimed_job(processing_path, payload)


def _release_lock_at_exit() -> None:
    queue.release_worker_lock()


def start_worker_if_enabled() -> bool:
    global _WORKER_THREAD
    if not learning_enabled():
        return False

    if _WORKER_THREAD and _WORKER_THREAD.is_alive():
        return True

    if not queue.acquire_worker_lock():
        return False

    queue.recover_processing_to_pending()

    poll_raw = os.getenv("MAESTRO_LEARNING_POLL_SECONDS", "2").strip()
    try:
        poll_seconds = max(0.1, float(poll_raw))
    except ValueError:
        poll_seconds = 2.0

    thread = threading.Thread(
        target=_worker_loop,
        args=(poll_seconds,),
        name="maestro-learning-worker",
        daemon=True,
    )
    thread.start()
    _WORKER_THREAD = thread
    atexit.register(_release_lock_at_exit)
    return True
