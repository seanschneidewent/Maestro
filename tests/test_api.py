# test_api.py — Tests for the REST API routes
#
# Uses FastAPI's TestClient (no real server needed).
# In-memory SQLite, mock project data.
#
# Run: python tests/test_api.py

import sys
import os
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
MAESTRO_DIR = str(Path(__file__).resolve().parent.parent / "maestro")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, MAESTRO_DIR)
os.environ["DATABASE_URL"] = "sqlite://"

from maestro.db import session as db_session
from maestro.db import repository as repo

# Use shared in-memory SQLite (same DB across all connections)
db_session.configure("sqlite:///file::memory:?cache=shared&uri=true")
db_session.init_db()

# Seed data
p = repo.get_or_create_project("CFA Love Field", "/data/cfa")
PID = p["id"]

# Workspaces
repo.create_workspace(PID, "Foundation & Framing", "Grade beams + framing", "foundation_framing")
repo.create_workspace(PID, "Kitchen Rough-In", "All kitchen MEP", "kitchen_rough_in")
repo.add_page(PID, "foundation_framing", "S-101")
repo.add_page(PID, "foundation_framing", "S-102")
repo.add_description(PID, "foundation_framing", "S-101", "Structural foundation")
repo.add_note(PID, "foundation_framing", "Pipe sleeves missing from structural sheets", source_page="VC-201")
repo.add_note(PID, "foundation_framing", "Epoxy anchor inspection required")

_highlight = repo.add_highlight(PID, "foundation_framing", "S-101", "Find pipe sleeves")
HIGHLIGHT_ID = _highlight["highlight"]["id"] if isinstance(_highlight, dict) else -1
repo.complete_highlight(
    HIGHLIGHT_ID,
    [{"x": 0.15, "y": 0.2, "width": 0.12, "height": 0.08}],
)

# Schedule
repo.add_event(PID, "Foundation Pour", "2026-02-20", event_type="milestone")
repo.add_event(PID, "Kitchen Rough-In Start", "2026-03-01", end="2026-03-15", event_type="phase")

# Conversation
repo.get_or_create_conversation(PID)
repo.add_message(PID, "user", "What about the foundation?")
repo.add_message(PID, "assistant", "The foundation shows post-tensioned grade beams.")
repo.add_message(PID, "user", "Any coordination issues?")
repo.add_message(PID, "assistant", "Yes - pipe sleeves through grade beams not on structural.")
repo.update_conversation_state(PID, summary="Discussed foundation. Found pipe sleeve gap.", increment_exchanges=True)
repo.update_conversation_state(PID, increment_exchanges=True)

# Mock project (knowledge store)
MOCK_PROJECT = {
    "name": "CFA Love Field",
    "pages": {
        "S-101 Structural Foundation Plan": {
            "discipline": "Structural",
            "sheet_reflection": "Post-tensioned grade beam foundation with 3000 PSI concrete.",
            "index": {"materials": ["concrete", "rebar", "post-tension cables"]},
            "cross_references": ["A-101", "VC-201"],
            "pointers": {
                "ptr_001": {"label": "Grade Beam Detail", "content_markdown": "24x36 grade beam with #5 rebar at 12\" OC"},
                "ptr_002": {"label": "Footing Schedule", "content_markdown": "F1: 36x36x18, F2: 48x48x24"},
            },
        },
        "A-201 Floor Plan": {
            "discipline": "Architectural",
            "sheet_reflection": "Main floor plan showing kitchen, dining, and service areas.",
            "index": {"areas": ["kitchen", "dining", "drive-through"]},
            "cross_references": ["S-101", "M-301"],
            "pointers": {
                "ptr_010": {"label": "Kitchen Layout", "content_markdown": "Walk-in cooler 10x12, freezer 8x10"},
            },
        },
        "M-301 HVAC Plan": {
            "discipline": "Mechanical",
            "sheet_reflection": "Rooftop units and ductwork distribution.",
            "index": {"equipment": ["RTU-1", "RTU-2", "MAU-1"]},
            "cross_references": ["A-201"],
            "pointers": {},
        },
    },
}

# Mock conversation object
class MockConversation:
    engine_name = "opus"
    tool_definitions = [{"name": f"tool_{i}"} for i in range(29)]
    def get_stats(self):
        return {
            "engine": "opus",
            "context_limit": 1000000,
            "estimated_tokens": 5000,
            "usage_pct": "0.5%",
            "messages_in_memory": 4,
        }

# Initialize API
from maestro.api.routes import api_router, init_api
init_api(project_id=PID, conversation=MockConversation(), project=MOCK_PROJECT)

# Create test app
from fastapi import FastAPI
from fastapi.testclient import TestClient

app = FastAPI()
app.include_router(api_router, prefix="/api")

# Need httpx for TestClient
try:
    client = TestClient(app)
except Exception:
    print("Installing httpx for TestClient...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx", "--quiet"])
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
print("\n== /api/health ==")
# ===================================================================

r = client.get("/api/health")
test("health 200", r.status_code == 200)
data = r.json()
test("health status ok", data["status"] == "ok")
test("health engine", data["engine"] == "opus")
test("health project_id", data["project_id"] == PID)
test("health tools count", data["tools"] == 29)

# ===================================================================
print("\n== /api/project ==")
# ===================================================================

r = client.get("/api/project")
test("project 200", r.status_code == 200)
data = r.json()
test("project name", data["name"] == "CFA Love Field")
test("project page_count", data["page_count"] == 3)
test("project pointer_count", data["pointer_count"] == 3)
test("project discipline_count", data["discipline_count"] == 3)
test("project engine", data["engine"] == "opus")

# ===================================================================
print("\n== /api/workspaces ==")
# ===================================================================

r = client.get("/api/workspaces")
test("workspaces 200", r.status_code == 200)
data = r.json()
test("workspaces is list", isinstance(data, list))
test("workspaces count", len(data) == 2)
test("workspace titles", {w["title"] for w in data} == {"Foundation & Framing", "Kitchen Rough-In"})

# ===================================================================
print("\n== /api/workspaces/:slug ==")
# ===================================================================

r = client.get("/api/workspaces/foundation_framing")
test("workspace by slug 200", r.status_code == 200)
data = r.json()
test("workspace metadata", data["metadata"]["title"] == "Foundation & Framing")
test("workspace pages", len(data["pages"]) == 2)
test("workspace notes", len(data["notes"]) == 2)
s101 = [p for p in data["pages"] if p["page_name"] == "S-101"][0]
test("workspace page has description", s101.get("description", "") == "Structural foundation")
test("workspace page has highlights", isinstance(s101.get("highlights", []), list))
test("workspace highlight has status", s101["highlights"][0]["status"] == "complete")
test("workspace highlight has bboxes", len(s101["highlights"][0]["bboxes"]) == 1)
test("note has text", data["notes"][0]["text"].startswith("Pipe sleeves"))

# Slug resolution (by title-ish)
r2 = client.get("/api/workspaces/kitchen_rough_in")
test("workspace slug resolve", r2.status_code == 200)

# Not found
r3 = client.get("/api/workspaces/nonexistent")
test("workspace 404", r3.status_code == 404)

# Workspace highlight endpoint removed
r4 = client.get(f"/api/workspaces/foundation_framing/highlight/{HIGHLIGHT_ID}")
test("workspace highlight route removed", r4.status_code == 404)

# ===================================================================
print("\n== /api/schedule ==")
# ===================================================================

r = client.get("/api/schedule")
test("schedule 200", r.status_code == 200)
data = r.json()
test("schedule has events", len(data["events"]) == 2)
test("schedule count", data["count"] == 2)

# Date filter
r2 = client.get("/api/schedule?from_date=2026-02-01&to_date=2026-02-28")
test("schedule date filter", len(r2.json()["events"]) == 1)

# Type filter
r3 = client.get("/api/schedule?event_type=milestone")
test("schedule type filter", len(r3.json()["events"]) == 1)

# Empty result
r4 = client.get("/api/schedule?from_date=2025-01-01&to_date=2025-12-31")
test("schedule empty", r4.json()["count"] == 0)

# ===================================================================
print("\n== /api/schedule/upcoming ==")
# ===================================================================

r = client.get("/api/schedule/upcoming?days=60")
test("upcoming 200", r.status_code == 200)
test("upcoming has days", r.json()["days"] == 60)

# ===================================================================
print("\n== /api/schedule/:event_id ==")
# ===================================================================

events = client.get("/api/schedule").json()["events"]
eid = events[0]["id"]
r = client.get(f"/api/schedule/{eid}")
test("event by id 200", r.status_code == 200)
test("event title", r.json()["title"] == "Foundation Pour")

r2 = client.get("/api/schedule/evt_fake")
test("event 404", r2.status_code == 404)

# ===================================================================
print("\n== /api/conversation ==")
# ===================================================================

r = client.get("/api/conversation")
test("conversation 200", r.status_code == 200)
data = r.json()
test("conversation summary", "pipe sleeve" in data["summary"])
test("conversation exchanges", data["total_exchanges"] == 2)
test("conversation engine", data["engine"] == "opus")
test("conversation context_limit", data["context_limit"] == 1000000)

# ===================================================================
print("\n== /api/conversation/messages ==")
# ===================================================================

r = client.get("/api/conversation/messages")
test("messages 200", r.status_code == 200)
data = r.json()
test("messages count", data["count"] == 4)
test("messages total", data["total"] == 4)
test("messages ordered", data["messages"][0]["role"] == "user")
test("first message content", "foundation" in data["messages"][0]["content"].lower())

# Limit
r2 = client.get("/api/conversation/messages?limit=2")
test("messages limit", r2.json()["count"] == 2)

# Before (pagination)
last_id = data["messages"][-1]["id"]
r3 = client.get(f"/api/conversation/messages?before={last_id}")
test("messages before", r3.json()["count"] == 3)  # All except last

# ===================================================================
print("\n== /api/knowledge/disciplines ==")
# ===================================================================

r = client.get("/api/knowledge/disciplines")
test("disciplines 200", r.status_code == 200)
data = r.json()
test("3 disciplines", len(data["disciplines"]) == 3)
names = {d["name"] for d in data["disciplines"]}
test("discipline names", names == {"Structural", "Architectural", "MEP"})
structural = [d for d in data["disciplines"] if d["name"] == "Structural"][0]
test("structural count", structural["page_count"] == 1)
mep = [d for d in data["disciplines"] if d["name"] == "MEP"][0]
test(
    "mep has mechanical child",
    any(c["name"] == "Mechanical" and c["page_count"] == 1 for c in mep.get("children", [])),
)

# ===================================================================
print("\n== /api/knowledge/pages ==")
# ===================================================================

r = client.get("/api/knowledge/pages")
test("pages 200", r.status_code == 200)
data = r.json()
test("3 pages", data["count"] == 3)
test("page has fields", all(k in data["pages"][0] for k in ["page_name", "discipline", "pointer_count"]))

# Filter by discipline
r2 = client.get("/api/knowledge/pages?discipline=Structural")
test("pages filter", r2.json()["count"] == 1)

# ===================================================================
print("\n== /api/knowledge/pages/:name ==")
# ===================================================================

r = client.get("/api/knowledge/pages/S-101 Structural Foundation Plan")
test("page detail 200", r.status_code == 200)
data = r.json()
test("page name", data["page_name"] == "S-101 Structural Foundation Plan")
test("page discipline", data["discipline"] == "Structural")
test("page reflection", "grade beam" in data["sheet_reflection"].lower())
test("page pointers", data["pointer_count"] == 2)
test("pointer has label", data["pointers"][0]["label"] in ["Grade Beam Detail", "Footing Schedule"])

r2 = client.get("/api/knowledge/pages/Z-999 Fake")
test("page 404", r2.status_code == 404)

# ===================================================================
print("\n== /api/knowledge/search ==")
# ===================================================================

r = client.get("/api/knowledge/search?q=concrete")
test("search 200", r.status_code == 200)
data = r.json()
test("search has results", data["count"] >= 1)
test("search query echo", data["query"] == "concrete")

# Search pointers
r2 = client.get("/api/knowledge/search?q=grade beam")
test("search pointers", any(r["type"] == "pointer" for r in r2.json()["results"]))

# Search no results
r3 = client.get("/api/knowledge/search?q=xyznonexistent")
test("search empty", r3.json()["count"] == 0)

# Search across disciplines
r4 = client.get("/api/knowledge/search?q=kitchen")
test("search cross-discipline", r4.json()["count"] >= 1)


# ===================================================================
# Summary
# ===================================================================

print(f"\n{'='*50}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'='*50}")

if failed:
    sys.exit(1)
else:
    print("  ALL API TESTS PASSED!")
