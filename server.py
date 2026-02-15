# server.py — Maestro's entry point
#
# The "mouth" — receives texts from supers via Sendblue webhook,
# routes them through the engine, sends responses back.
# Also runs heartbeats on a background timer.
#
# Usage:
#   python server.py                    # Interactive: asks for phone number
#   python server.py +16823521836       # Direct: starts with that number
#   python server.py +16823521836 gpt   # Specify engine

from __future__ import annotations

import asyncio
import os
import sys
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request

# Set working directory to Maestro root (knowledge_store/ is relative to CWD)
MAESTRO_ROOT = Path(__file__).resolve().parent
os.chdir(MAESTRO_ROOT)

# Ensure maestro/ is on the import path
sys.path.insert(0, str(MAESTRO_ROOT / "maestro"))

from messaging.sendblue import send_message as sendblue_send, send_typing_indicator, format_for_imessage
from messaging.conversation import Conversation
from engine.heartbeat import run_heartbeat, record_heartbeat, _load_state
from tools.schedule import upcoming as schedule_upcoming
from tools.workspaces import list_workspaces
from maestro.api.routes import api_router, init_api
from maestro.api.websocket import ws_router, emit_message, emit_heartbeat, emit_finding, emit_status


# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

conversation: Conversation | None = None
super_phone: str = ""
heartbeat_thread: threading.Thread | None = None
heartbeat_stop = threading.Event()


# ---------------------------------------------------------------------------
# Safe printing (Windows encoding)
# ---------------------------------------------------------------------------

def _safe_print(text: str) -> None:
    """Print text safely on Windows (replace unencodable chars)."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


# ---------------------------------------------------------------------------
# Heartbeat background worker
# ---------------------------------------------------------------------------

def _heartbeat_loop():
    """Background thread that runs heartbeats on interval.

    Uses the heartbeat module's own timing logic (should_heartbeat)
    to decide when to fire. We just poll every 60s and let the
    heartbeat module decide if it's time.
    """
    global conversation, super_phone

    _safe_print("[Heartbeat] Background worker started")

    while not heartbeat_stop.is_set():
        heartbeat_stop.wait(60)  # Check every 60 seconds
        if heartbeat_stop.is_set():
            break

        if not conversation or not super_phone:
            continue

        try:
            # Gather inputs for the heartbeat decision
            schedule_events = []
            try:
                result = schedule_upcoming(days="2")
                if isinstance(result, list):
                    schedule_events = result
            except Exception:
                pass

            workspaces = []
            try:
                result = list_workspaces()
                if isinstance(result, list):
                    workspaces = result
            except Exception:
                pass

            gaps = []  # TODO: wire up check_gaps

            # Run the heartbeat decision
            decision = run_heartbeat(schedule_events, workspaces, gaps, conversation.project)

            if decision.get("mode") == "skip":
                continue

            mode = decision["mode"]
            prompt = decision.get("prompt", "")
            should_message = decision.get("should_message", False)

            _safe_print(f"\n[Heartbeat] Mode: {mode} | Reason: {decision.get('reason', '')}")
            emit_heartbeat(mode, decision.get("reason", ""), should_message)

            if not prompt:
                continue

            # Feed the heartbeat prompt through the engine (same thread)
            response = conversation.send(prompt)
            _safe_print(f"[Heartbeat] Response: {response[:200]}...")

            # Record the heartbeat
            record_heartbeat(_load_state(), decision)

            # Send to super if warranted
            if should_message and response and super_phone:
                formatted = format_for_imessage(response)
                text = f"[Maestro] {formatted}"
                sendblue_send(super_phone, text)
                _safe_print(f"[Heartbeat] Sent finding to {super_phone}")
                emit_finding(response)

        except Exception as exc:
            _safe_print(f"[Heartbeat] Error: {exc}")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start heartbeat worker on startup, stop on shutdown."""
    global heartbeat_thread
    heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
    heartbeat_thread.start()
    yield
    heartbeat_stop.set()
    if heartbeat_thread:
        heartbeat_thread.join(timeout=5)


app = FastAPI(title="Maestro", lifespan=lifespan)
app.include_router(api_router, prefix="/api")
app.include_router(ws_router)

# Serve knowledge_store page images as static files
from fastapi.staticfiles import StaticFiles
_ks_path = MAESTRO_ROOT / "knowledge_store"
if _ks_path.exists():
    app.mount("/static/pages", StaticFiles(directory=str(_ks_path)), name="pages")


@app.post("/sendblue-webhook")
async def sendblue_webhook(request: Request):
    """Receive incoming iMessages from Sendblue."""
    body = await request.json()

    from_number = body.get("from_number", body.get("number", ""))
    content = body.get("content", "").strip()
    media_url = body.get("media_url")

    if not content and not media_url:
        return {"status": "ignored", "reason": "empty message"}

    if not from_number:
        return {"status": "ignored", "reason": "no sender"}

    # Ignore echoes of our own outbound messages
    from messaging.sendblue import FROM_NUMBER
    if from_number == FROM_NUMBER:
        return {"status": "ignored", "reason": "outbound echo"}

    # Only accept messages from the configured super
    if from_number != super_phone:
        return {"status": "ignored", "reason": "unknown number"}

    _safe_print(f"\n[iMessage] From {from_number}: {content[:100]}")

    if not conversation:
        return {"status": "error", "reason": "engine not initialized"}

    # Process in background so webhook returns fast
    asyncio.create_task(_handle_message(from_number, content))
    return {"status": "ok"}


async def _handle_message(from_number: str, content: str):
    """Handle an incoming message (runs in background)."""
    try:
        # Show typing indicator while Maestro thinks
        send_typing_indicator(from_number)
        emit_message("user", content)

        # Run the engine (blocking, so use thread)
        response = await asyncio.get_event_loop().run_in_executor(
            None, conversation.send, content
        )

        if response:
            formatted = format_for_imessage(response)
            sendblue_send(from_number, formatted)
            emit_message("assistant", response)
            _safe_print(f"[iMessage] Sent reply to {from_number}: {formatted[:100]}...")

    except Exception as exc:
        _safe_print(f"[iMessage] Error handling message from {from_number}: {exc}")
        try:
            sendblue_send(from_number, "Sorry, I hit an error processing that. Try again?")
        except Exception:
            pass


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "engine": conversation.engine_name if conversation else None,
        "super_phone": super_phone or None,
        "time": datetime.now().isoformat(),
    }


@app.get("/stats")
async def stats():
    """Conversation statistics — context usage, compaction history."""
    if not conversation:
        return {"status": "error", "reason": "engine not initialized"}
    return conversation.get_stats()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    global conversation, super_phone

    # Get phone number
    if len(sys.argv) > 1:
        super_phone = sys.argv[1]
    else:
        super_phone = input("Super's phone number (e.g. +16823521836): ").strip()

    if not super_phone.startswith("+"):
        super_phone = f"+1{super_phone}"

    # Pick engine
    engine_name = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"\nInitializing Maestro...")
    conversation = Conversation(engine_name)

    # Wire up API routes with runtime references
    init_api(
        project_id=conversation.project_id,
        conversation=conversation,
        project=conversation.project,
    )

    project_name = conversation.project["name"] if conversation.project else "No project"
    print(f"  Engine: {conversation.engine_name}")
    print(f"  Project: {project_name}")
    print(f"  Tools: {len(conversation.tool_definitions)}")
    print(f"  Super: {super_phone}")

    # Send intro message
    intro = (
        f"Hey — I'm Maestro. I'm reviewing the {project_name} plans right now. "
        "I'll text you when I find something worth knowing. "
        "You can also text me anytime with questions about the plans."
    )
    print(f"\nSending intro to {super_phone}...")
    try:
        sendblue_send(super_phone, intro)
        print("  [OK] Sent!")
    except Exception as exc:
        print(f"  [FAIL] Failed to send intro: {exc}")
        print("  (Continuing anyway — webhook will still work)")

    # Start server
    print(f"\nMaestro is live. Listening for texts...")
    print(f"  Webhook:    http://localhost:8000/sendblue-webhook")
    print(f"  API:        http://localhost:8000/api/health")
    print(f"  WebSocket:  ws://localhost:8000/ws")
    print(f"  Heartbeats running in background")
    print(f"\n  Press Ctrl+C to stop.\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
