from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
STATUS_PATH = REPO_ROOT / "learning_status.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)
    tmp_path.replace(path)


def read_status() -> dict[str, Any] | None:
    if not STATUS_PATH.exists():
        return None
    try:
        data = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return copy.deepcopy(data)


def write_status(active: bool, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "active": bool(active),
        "message": str(message),
        "updated_at": _utc_now_iso(),
    }
    if isinstance(details, dict) and details:
        payload["details"] = details
    _write_json_atomic(STATUS_PATH, payload)
    return payload


def clear_status() -> None:
    if STATUS_PATH.exists():
        STATUS_PATH.unlink()
