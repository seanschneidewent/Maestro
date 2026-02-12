from __future__ import annotations

import copy
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
LEARNING_QUEUE_DIR = REPO_ROOT / "learning_queue"
PENDING_DIR = LEARNING_QUEUE_DIR / "pending"
PROCESSING_DIR = LEARNING_QUEUE_DIR / "processing"
DONE_DIR = LEARNING_QUEUE_DIR / "done"
LOCK_PATH = LEARNING_QUEUE_DIR / "worker.lock"

_LOCK_FD: int | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_id_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _slug_token(value: str, fallback: str = "job") -> str:
    token = re.sub(r"[^a-z0-9]+", "_", value.lower())
    token = re.sub(r"_+", "_", token).strip("_")
    return token or fallback


def _read_json_default(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return copy.deepcopy(default)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return copy.deepcopy(default)
    if isinstance(data, dict):
        return data
    return copy.deepcopy(default)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)
    tmp_path.replace(path)


def ensure_learning_dirs() -> None:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSING_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)


def build_job_id(entry_type: str, label: str) -> str:
    clean_type = _slug_token(entry_type, "job")
    clean_label = _slug_token(label, "item")
    return f"{_utc_id_timestamp()}_{clean_type}_{clean_label}"


def enqueue_workspace_entry(
    *,
    workspace_slug: str,
    workspace_snapshot: dict[str, Any] | None,
    user_message: str,
    assistant_response: str,
    tool_calls: list[dict[str, Any]],
    engine: str = "opus",
) -> Path:
    job_id = build_job_id("workspace", workspace_slug)
    payload: dict[str, Any] = {
        "id": job_id,
        "type": "workspace",
        "timestamp": _utc_now_iso(),
        "engine": engine,
        "workspace_slug": workspace_slug,
        "workspace_snapshot": workspace_snapshot or {},
        "user_message": user_message,
        "assistant_response": assistant_response,
        "tool_calls": tool_calls,
        "status": "pending",
    }
    return enqueue_entry(payload)


def enqueue_feedback_entry(
    *,
    user_message: str,
    prior_assistant_response: str,
    prior_tool_calls: list[dict[str, Any]],
    relevant_pages: list[str],
    engine: str = "opus",
) -> Path:
    job_id = build_job_id("feedback", "feedback")
    payload: dict[str, Any] = {
        "id": job_id,
        "type": "feedback",
        "timestamp": _utc_now_iso(),
        "engine": engine,
        "user_message": user_message,
        "prior_assistant_response": prior_assistant_response,
        "prior_tool_calls": prior_tool_calls,
        "relevant_pages": relevant_pages,
        "status": "pending",
    }
    return enqueue_entry(payload)


def enqueue_entry(entry: dict[str, Any]) -> Path:
    ensure_learning_dirs()
    payload = copy.deepcopy(entry)
    job_id = str(payload.get("id", "")).strip()
    if not job_id:
        label = str(payload.get("type", "job"))
        payload["id"] = build_job_id(label, label)
        job_id = str(payload["id"])
    path = PENDING_DIR / f"{job_id}.json"
    _write_json_atomic(path, payload)
    return path


def _unique_destination(directory: Path, file_name: str) -> Path:
    candidate = directory / file_name
    if not candidate.exists():
        return candidate
    stem = Path(file_name).stem
    suffix = Path(file_name).suffix
    idx = 1
    while True:
        candidate = directory / f"{stem}_{idx}{suffix}"
        if not candidate.exists():
            return candidate
        idx += 1


def recover_processing_to_pending() -> int:
    ensure_learning_dirs()
    recovered = 0
    for path in sorted(PROCESSING_DIR.glob("*.json"), key=lambda p: p.name.lower()):
        dest = _unique_destination(PENDING_DIR, path.name)
        path.replace(dest)
        recovered += 1
    return recovered


def claim_next_job() -> tuple[Path, dict[str, Any]] | None:
    ensure_learning_dirs()
    pending_files = sorted(PENDING_DIR.glob("*.json"), key=lambda p: p.name.lower())
    if not pending_files:
        return None

    pending_path = pending_files[0]
    processing_path = _unique_destination(PROCESSING_DIR, pending_path.name)
    pending_path.replace(processing_path)

    payload = _read_json_default(processing_path, {"id": processing_path.stem})
    payload["status"] = "processing"
    payload["processing_started_at"] = _utc_now_iso()
    _write_json_atomic(processing_path, payload)
    return processing_path, payload


def finalize_job(
    processing_path: Path,
    payload: dict[str, Any],
    *,
    status: str,
    result: dict[str, Any] | None = None,
    errors: list[str] | None = None,
) -> Path:
    ensure_learning_dirs()
    done_payload = copy.deepcopy(payload)
    done_payload["status"] = status
    if not done_payload.get("processing_started_at"):
        done_payload["processing_started_at"] = _utc_now_iso()
    done_payload["processing_finished_at"] = _utc_now_iso()
    if isinstance(result, dict):
        done_payload.update(result)
    if errors is not None:
        done_payload["errors"] = errors

    _write_json_atomic(processing_path, done_payload)
    done_path = _unique_destination(DONE_DIR, processing_path.name)
    processing_path.replace(done_path)
    return done_path


def acquire_worker_lock() -> bool:
    global _LOCK_FD
    ensure_learning_dirs()
    if _LOCK_FD is not None:
        return True
    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False

    payload = json.dumps({"pid": os.getpid(), "timestamp": _utc_now_iso()}, ensure_ascii=True)
    os.write(fd, payload.encode("utf-8"))
    _LOCK_FD = fd
    return True


def release_worker_lock() -> None:
    global _LOCK_FD
    if _LOCK_FD is not None:
        os.close(_LOCK_FD)
        _LOCK_FD = None
    if LOCK_PATH.exists():
        LOCK_PATH.unlink()
