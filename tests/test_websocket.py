# test_websocket.py — Tests for WebSocket real-time push
#
# Uses FastAPI's TestClient WebSocket support.
#
# Run: python tests/test_websocket.py

import sys
import os
import time
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
MAESTRO_DIR = str(Path(__file__).resolve().parent.parent / "maestro")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, MAESTRO_DIR)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from maestro.api.websocket import (
    ws_router,
    broadcast_sync,
    emit_message,
    emit_heartbeat,
    emit_finding,
    emit_workspace_change,
    emit_schedule_change,
    emit_compaction,
    emit_engine_switch,
    emit_status,
    _clients,
)

app = FastAPI()
app.include_router(ws_router)
client = TestClient(app)

passed = 0
failed = 0


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} -- {detail}")


# ===================================================================
print("\n== WebSocket Connection ==")
# ===================================================================

with client.websocket_connect("/ws") as ws:
    # Should receive connected event
    data = ws.receive_json()
    test("connected event", data["type"] == "connected")
    test("connected has clients", data["clients"] == 1)
    test("connected has time", "time" in data)

    # Ping/pong
    ws.send_text("ping")
    pong = ws.receive_json()
    test("pong response", pong["type"] == "pong")
    test("pong has time", "time" in pong)


# ===================================================================
print("\n== Event Broadcasting ==")
# ===================================================================

with client.websocket_connect("/ws") as ws:
    # Consume the connected event
    ws.receive_json()

    # Test emit_message
    emit_message("user", "What about the foundation?", message_id=42)
    data = ws.receive_json()
    test("message type", data["type"] == "message")
    test("message role", data["role"] == "user")
    test("message content", "foundation" in data["content"])
    test("message id", data["message_id"] == 42)
    test("message has time", "time" in data)

    # Test emit_message (assistant)
    emit_message("assistant", "The grade beams show post-tensioned design.")
    data = ws.receive_json()
    test("assistant message", data["role"] == "assistant")

    # Test emit_heartbeat
    emit_heartbeat("targeted", "Active workspace: Foundation & Framing", should_message=True)
    data = ws.receive_json()
    test("heartbeat type", data["type"] == "heartbeat")
    test("heartbeat mode", data["mode"] == "targeted")
    test("heartbeat reason", "Foundation" in data["reason"])
    test("heartbeat should_message", data["should_message"] == True)

    # Test emit_finding
    emit_finding("3-inch pipe sleeves missing from structural sheets", workspace_slug="foundation_framing", source_page="VC-201")
    data = ws.receive_json()
    test("finding type", data["type"] == "finding")
    test("finding text", "pipe sleeves" in data["text"])
    test("finding workspace", data["workspace_slug"] == "foundation_framing")
    test("finding source", data["source_page"] == "VC-201")

    # Test emit_workspace_change
    emit_workspace_change("page_added", "foundation_framing", detail="Added S-103")
    data = ws.receive_json()
    test("workspace type", data["type"] == "workspace")
    test("workspace action", data["action"] == "page_added")
    test("workspace slug", data["workspace_slug"] == "foundation_framing")

    # Test emit_schedule_change
    emit_schedule_change("added", "evt_abc123", title="Foundation Pour")
    data = ws.receive_json()
    test("schedule type", data["type"] == "schedule")
    test("schedule action", data["action"] == "added")
    test("schedule event_id", data["event_id"] == "evt_abc123")

    # Test emit_compaction
    emit_compaction(deleted_count=15, new_token_estimate=25000, context_limit=1000000)
    data = ws.receive_json()
    test("compaction type", data["type"] == "compaction")
    test("compaction deleted", data["deleted_messages"] == 15)
    test("compaction tokens", data["estimated_tokens"] == 25000)

    # Test emit_engine_switch
    emit_engine_switch("opus", "gemini-flash")
    data = ws.receive_json()
    test("engine_switch type", data["type"] == "engine_switch")
    test("engine_switch old", data["old_engine"] == "opus")
    test("engine_switch new", data["new_engine"] == "gemini-flash")

    # Test emit_status
    emit_status({"engine": "opus", "usage_pct": "5.2%", "messages_in_memory": 20})
    data = ws.receive_json()
    test("status type", data["type"] == "status")
    test("status engine", data["engine"] == "opus")
    test("status usage", data["usage_pct"] == "5.2%")


# ===================================================================
print("\n== Multiple Clients ==")
# ===================================================================

with client.websocket_connect("/ws") as ws1:
    ws1.receive_json()  # connected
    with client.websocket_connect("/ws") as ws2:
        ws2.receive_json()  # connected

        emit_message("user", "Broadcast to all")

        d1 = ws1.receive_json()
        d2 = ws2.receive_json()
        test("client 1 receives", d1["type"] == "message")
        test("client 2 receives", d2["type"] == "message")
        test("same content", d1["content"] == d2["content"])


# ===================================================================
print("\n== Disconnection Cleanup ==")
# ===================================================================

# After all contexts exit, clients should be cleaned up
test("clients cleaned up", len(_clients) == 0, f"still {len(_clients)} connected")


# ===================================================================
# Summary
# ===================================================================

print(f"\n{'='*50}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'='*50}")

if failed:
    sys.exit(1)
else:
    print("  ALL WEBSOCKET TESTS PASSED!")
