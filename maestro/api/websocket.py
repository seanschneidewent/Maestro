# websocket.py — Real-time push for Maestro's frontend
#
# WebSocket endpoint that pushes events to connected dashboards.
# The dashboard connects once and receives a stream of typed events.
#
# Event types:
#   message        — New conversation message (user or assistant)
#   heartbeat      — Heartbeat fired (mode, reason)
#   finding        — Maestro found something worth reporting
#   workspace      — Workspace state changed (page added, note added)
#   schedule       — Schedule event changed
#   compaction     — Conversation compacted
#   engine_switch  — Brain switched to different model
#   status         — Periodic status pulse (context usage, etc.)
#
# Usage in server.py:
#   from maestro.api.websocket import ws_router, broadcast
#   app.include_router(ws_router)
#
# To push from anywhere:
#   from maestro.api.websocket import broadcast
#   await broadcast({"type": "message", "role": "user", "content": "..."})
#
# Or synchronously (from heartbeat thread, etc.):
#   from maestro.api.websocket import broadcast_sync
#   broadcast_sync({"type": "message", "role": "user", "content": "..."})

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

ws_router = APIRouter()

# Connected clients
_clients: set[WebSocket] = set()
_event_loop: asyncio.AbstractEventLoop | None = None


# ===================================================================
# Connection manager
# ===================================================================

@ws_router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time dashboard updates."""
    global _event_loop
    await ws.accept()
    _clients.add(ws)
    _event_loop = asyncio.get_event_loop()

    # Send initial status on connect
    try:
        await ws.send_json({
            "type": "connected",
            "clients": len(_clients),
            "time": time.time(),
        })
    except Exception:
        pass

    try:
        # Keep connection alive — listen for pings/close
        while True:
            data = await ws.receive_text()
            # Client can send "ping" for keepalive
            if data == "ping":
                await ws.send_json({"type": "pong", "time": time.time()})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _clients.discard(ws)


# ===================================================================
# Broadcasting
# ===================================================================

async def broadcast(event: dict[str, Any]) -> None:
    """Push an event to all connected WebSocket clients."""
    if not _clients:
        return

    event["time"] = time.time()
    dead: list[WebSocket] = []

    for ws in _clients:
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)

    for ws in dead:
        _clients.discard(ws)


def broadcast_sync(event: dict[str, Any]) -> None:
    """Push an event from synchronous code (heartbeat thread, tool calls).

    Safe to call from any thread. No-op if no event loop or no clients.
    """
    if not _clients or not _event_loop:
        return

    try:
        asyncio.run_coroutine_threadsafe(broadcast(event), _event_loop)
    except Exception:
        pass  # Best effort — don't crash the caller


# ===================================================================
# Convenience emitters (called from conversation, heartbeat, tools)
# ===================================================================

def emit_message(role: str, content: str, message_id: int | None = None) -> None:
    """Emit a new conversation message."""
    broadcast_sync({
        "type": "message",
        "role": role,
        "content": content[:500],  # Preview for dashboard
        "message_id": message_id,
    })


def emit_heartbeat(mode: str, reason: str, should_message: bool = False) -> None:
    """Emit a heartbeat decision."""
    broadcast_sync({
        "type": "heartbeat",
        "mode": mode,
        "reason": reason,
        "should_message": should_message,
    })


def emit_finding(text: str, workspace_slug: str | None = None, source_page: str | None = None) -> None:
    """Emit a notable finding from heartbeat or conversation."""
    broadcast_sync({
        "type": "finding",
        "text": text[:500],
        "workspace_slug": workspace_slug,
        "source_page": source_page,
    })


def emit_workspace_change(action: str, workspace_slug: str, detail: str = "") -> None:
    """Emit a workspace state change (page_added, note_added, created)."""
    broadcast_sync({
        "type": "workspace",
        "action": action,
        "workspace_slug": workspace_slug,
        "detail": detail,
    })


def emit_schedule_change(action: str, event_id: str, title: str = "") -> None:
    """Emit a schedule change (added, updated, removed)."""
    broadcast_sync({
        "type": "schedule",
        "action": action,
        "event_id": event_id,
        "title": title,
    })


def emit_compaction(deleted_count: int, new_token_estimate: int, context_limit: int) -> None:
    """Emit a compaction event."""
    broadcast_sync({
        "type": "compaction",
        "deleted_messages": deleted_count,
        "estimated_tokens": new_token_estimate,
        "context_limit": context_limit,
    })


def emit_engine_switch(old_engine: str, new_engine: str) -> None:
    """Emit an engine switch event."""
    broadcast_sync({
        "type": "engine_switch",
        "old_engine": old_engine,
        "new_engine": new_engine,
    })


def emit_status(stats: dict[str, Any]) -> None:
    """Emit a periodic status pulse."""
    broadcast_sync({"type": "status", **stats})
