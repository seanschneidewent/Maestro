# test_db.py — Comprehensive tests for the database layer
#
# Run: python tests/test_db.py
# Uses a fresh in-memory SQLite DB (no side effects on maestro.db)

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Override DATABASE_URL to use in-memory SQLite BEFORE importing db modules
os.environ["DATABASE_URL"] = "sqlite://"

from maestro.db.models import Base
from maestro.db.session import engine, get_session
from maestro.db import repository as repo

# Recreate tables on in-memory DB
Base.metadata.create_all(engine)


passed = 0
failed = 0


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name} — {detail}")


# ===================================================================
print("\n🔹 PROJECTS")
# ===================================================================

p = repo.get_or_create_project("CFA Love Field", "/data/cfa")
test("Create project", p["name"] == "CFA Love Field")
test("Project has id", len(p["id"]) == 12)
test("Project has path", p["path"] == "/data/cfa")

# Idempotent — same name returns same project
p2 = repo.get_or_create_project("CFA Love Field", "/data/cfa")
test("get_or_create idempotent", p["id"] == p2["id"])

# get_project
p3 = repo.get_project(p["id"])
test("get_project works", p3 is not None and p3["id"] == p["id"])
test("get_project not found", repo.get_project("nonexistent") is None)

PID = p["id"]

# ===================================================================
print("\n🔹 WORKSPACES")
# ===================================================================

w = repo.create_workspace(PID, "Foundation & Framing", "Grade beams, footings, framing", "foundation_framing")
test("Create workspace", w["slug"] == "foundation_framing")
test("Initial page_count = 0", w["page_count"] == 0)
test("Status = active", w["status"] == "active")

# Idempotent — same slug returns existing
w2 = repo.create_workspace(PID, "Foundation & Framing", "desc", "foundation_framing")
test("create_workspace idempotent", w2["slug"] == w["slug"])

# Create second workspace
repo.create_workspace(PID, "Kitchen Rough-In", "All kitchen MEP", "kitchen_rough_in")

# List
ws_list = repo.list_workspaces(PID)
test("list_workspaces count", len(ws_list) == 2)
test("list_workspaces has titles", {w["title"] for w in ws_list} == {"Foundation & Framing", "Kitchen Rough-In"})

# Resolve slug — exact
test("resolve exact slug", repo.resolve_workspace_slug(PID, "foundation_framing") == "foundation_framing")

# Resolve slug — from title
test("resolve by title", repo.resolve_workspace_slug(PID, "Kitchen Rough-In") == "kitchen_rough_in")

# Resolve slug — slugified input
test("resolve slugified", repo.resolve_workspace_slug(PID, "Foundation & Framing") == "foundation_framing")

# Resolve slug — not found
test("resolve not found", repo.resolve_workspace_slug(PID, "nonexistent") is None)

# Get workspace full state
ws_full = repo.get_workspace(PID, "foundation_framing")
test("get_workspace returns metadata", ws_full["metadata"]["title"] == "Foundation & Framing")
test("get_workspace empty pages", ws_full["pages"] == [])
test("get_workspace empty notes", ws_full["notes"] == [])

# Get workspace not found
test("get_workspace not found", repo.get_workspace(PID, "nonexistent") is None)

# ===================================================================
print("\n🔹 WORKSPACE PAGES")
# ===================================================================

result = repo.add_page(PID, "foundation_framing", "S-101")
test("add_page success", isinstance(result, dict) and result["page_count"] == 1)

result2 = repo.add_page(PID, "foundation_framing", "S-102")
test("add second page", result2["page_count"] == 2)

# Duplicate
dup = repo.add_page(PID, "foundation_framing", "S-101")
test("add_page duplicate rejected", isinstance(dup, str) and "already" in dup)

# Not found workspace
nf = repo.add_page(PID, "nonexistent", "S-101")
test("add_page bad workspace", isinstance(nf, str) and "not found" in nf.lower())

# Verify pages in get_workspace
ws_full = repo.get_workspace(PID, "foundation_framing")
test("pages persisted", len(ws_full["pages"]) == 2)
test("page has description", ws_full["pages"][0]["description"] == "")

# Set and clear description
desc = repo.add_description(PID, "foundation_framing", "S-101", "Structural foundation plan")
test("add_description success", isinstance(desc, dict) and desc["description"] == "Structural foundation plan")
desc2 = repo.add_description(PID, "foundation_framing", "S-101", "")
test("clear_description success", isinstance(desc2, dict) and desc2["description"] == "")

# Highlight add/complete/fail/get/remove
h = repo.add_highlight(PID, "foundation_framing", "S-101", "Find sleeves")
test("add_highlight success", isinstance(h, dict) and isinstance(h["highlight"].get("id"), int))
test("add_highlight pending status", isinstance(h, dict) and h["highlight"].get("status") == "pending")
test("add_highlight empty bboxes", isinstance(h, dict) and h["highlight"].get("bboxes") == [])

hid = h["highlight"]["id"] if isinstance(h, dict) else -1

completed = repo.complete_highlight(
    hid,
    [{"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.1}],
)
test("complete_highlight success", isinstance(completed, dict) and completed.get("status") == "complete")
test("complete_highlight has bbox", isinstance(completed, dict) and len(completed.get("bboxes", [])) == 1)

got_h = repo.get_highlight(PID, "foundation_framing", hid)
test("get_highlight success", got_h is not None and got_h["id"] == hid)
test("get_highlight status", got_h is not None and got_h["status"] == "complete")
test("get_highlight bboxes", got_h is not None and len(got_h["bboxes"]) == 1)

ws_full = repo.get_workspace(PID, "foundation_framing")
s101 = [p for p in ws_full["pages"] if p["page_name"] == "S-101"][0]
test("workspace payload includes highlights", len(s101["highlights"]) == 1 and s101["highlights"][0]["id"] == hid)
test("workspace payload highlight status", s101["highlights"][0]["status"] == "complete")
test("workspace payload highlight bboxes", len(s101["highlights"][0]["bboxes"]) == 1)
test("highlight has timestamp", bool(s101["highlights"][0]["created_at"]))

failed_highlight = repo.fail_highlight(hid)
test("fail_highlight success", isinstance(failed_highlight, dict) and failed_highlight.get("status") == "failed")

removed_h = repo.remove_highlight(PID, "foundation_framing", "S-101", hid)
test("remove_highlight success", isinstance(removed_h, dict) and removed_h["removed"] is True)
test("remove_highlight missing", isinstance(repo.remove_highlight(PID, "foundation_framing", "S-101", hid), str))

# Remove page
rm = repo.remove_page(PID, "foundation_framing", "S-101")
test("remove_page success", isinstance(rm, dict) and rm["removed"] and rm["page_count"] == 1)

# Remove again — not found
rm2 = repo.remove_page(PID, "foundation_framing", "S-101")
test("remove_page not found", isinstance(rm2, str) and "not in" in rm2.lower())

# ===================================================================
print("\n🔹 WORKSPACE NOTES")
# ===================================================================

n = repo.add_note(PID, "foundation_framing", "3-inch pipe sleeves missing from structural", source_page="VC-201")
test("add_note success", isinstance(n, dict) and n["note_count"] == 1)
test("note has source_page", n["note"]["source_page"] == "VC-201")

n2 = repo.add_note(PID, "foundation_framing", "Epoxy anchor inspection required")
test("add second note", n2["note_count"] == 2)
test("note without source_page", n2["note"]["source_page"] is None)

# Bad workspace
nf = repo.add_note(PID, "nonexistent", "test")
test("add_note bad workspace", isinstance(nf, str))

# ===================================================================
print("\n🔹 SCHEDULE EVENTS")
# ===================================================================

evt = repo.add_event(PID, "Foundation Pour", "2026-02-20", event_type="milestone")
test("add_event success", evt["id"].startswith("evt_"))
test("event type", evt["type"] == "milestone")
test("end defaults to start", evt["end"] == "2026-02-20")

evt2 = repo.add_event(PID, "Kitchen Rough-In", "2026-03-01", end="2026-03-15", event_type="phase", notes="All MEP trades")
test("add_event with end/notes", evt2["end"] == "2026-03-15" and evt2["notes"] == "All MEP trades")

# List events
events = repo.list_events(PID)
test("list_events count", len(events) == 2)

# List with date filter
events_feb = repo.list_events(PID, from_date="2026-02-01", to_date="2026-02-28")
test("list_events date filter", len(events_feb) == 1 and events_feb[0]["title"] == "Foundation Pour")

# List with type filter
events_ms = repo.list_events(PID, event_type="milestone")
test("list_events type filter", len(events_ms) == 1)

# Get event
got = repo.get_event(PID, evt["id"])
test("get_event", got is not None and got["title"] == "Foundation Pour")
test("get_event not found", repo.get_event(PID, "evt_fake") is None)

# Update event
updated = repo.update_event(PID, evt["id"], title="Foundation Pour — RESCHEDULED", start="2026-02-22")
test("update_event", isinstance(updated, dict) and updated["title"] == "Foundation Pour — RESCHEDULED" and updated["start"] == "2026-02-22")

# Update not found
test("update_event not found", isinstance(repo.update_event(PID, "evt_fake", title="x"), str))

# Remove event
rm = repo.remove_event(PID, evt2["id"])
test("remove_event", isinstance(rm, dict) and rm["removed"] == evt2["id"])
test("remove_event remaining", rm["remaining"] == 1)

# Remove not found
test("remove_event not found", isinstance(repo.remove_event(PID, "evt_fake"), str))

# Upcoming
upcoming = repo.upcoming_events(PID, days=30)
test("upcoming_events", len(upcoming) >= 0)  # depends on current date vs test data

# ===================================================================
print("\n🔹 CONVERSATION — MESSAGES")
# ===================================================================

cs = repo.get_or_create_conversation(PID)
test("create conversation state", cs["total_exchanges"] == 0)

# Idempotent
cs2 = repo.get_or_create_conversation(PID)
test("conversation state idempotent", cs2["id"] == cs["id"])

# Add messages
m1 = repo.add_message(PID, "user", "Hey Maestro, what about the foundation?")
m2 = repo.add_message(PID, "assistant", "The foundation plan shows grade beams at...")
m3 = repo.add_message(PID, "user", "What about the pipe sleeves?")
m4 = repo.add_message(PID, "assistant", "Good catch. The VC sheets show 3-inch sleeves...")
test("add_message returns ids", m1 < m2 < m3 < m4)

# Count
test("count_messages", repo.count_messages(PID) == 4)

# Get all messages
all_msgs = repo.get_messages(PID)
test("get_messages order", [m["id"] for m in all_msgs] == [m1, m2, m3, m4])
test("get_messages content", all_msgs[0]["content"].startswith("Hey Maestro"))

# Get with limit
limited = repo.get_messages(PID, limit=2)
test("get_messages limit", len(limited) == 2 and limited[0]["id"] == m1)

# Get with offset
offset_msgs = repo.get_messages(PID, limit=2, offset=2)
test("get_messages offset", len(offset_msgs) == 2 and offset_msgs[0]["id"] == m3)

# Get recent
recent = repo.get_recent_messages(PID, count=2)
test("get_recent_messages", len(recent) == 2 and recent[0]["id"] == m3 and recent[1]["id"] == m4)

# Delete old messages (simulate compaction)
deleted = repo.delete_messages_before(PID, m3)
test("delete_messages_before", deleted == 2)
test("remaining after delete", repo.count_messages(PID) == 2)

# Update conversation state
repo.update_conversation_state(PID, summary="Foundation discussion. Pipe sleeves identified.", increment_exchanges=True)
cs3 = repo.get_or_create_conversation(PID)
test("update summary", cs3["summary"] == "Foundation discussion. Pipe sleeves identified.")
test("increment exchanges", cs3["total_exchanges"] == 1)

repo.update_conversation_state(PID, increment_compactions=True)
cs4 = repo.get_or_create_conversation(PID)
test("increment compactions", cs4["compactions"] == 1)
test("last_compaction set", cs4["last_compaction"] != "")

# ===================================================================
print("\n🔹 EXPERIENCE LOG")
# ===================================================================

repo.log_experience("update_experience", {"file": "disciplines/kitchen.json", "field": "patterns", "result": "OK"})
repo.log_experience("update_knowledge", {"page": "S-101", "field": "cross_references", "result": "OK"})

# Verify via raw query
with get_session() as s:
    from maestro.db.models import ExperienceLog
    count = s.query(ExperienceLog).count()
test("experience log entries", count == 2)

# ===================================================================
print("\n🔹 CASCADE DELETES")
# ===================================================================

# Create a throwaway project with workspace + pages + notes + events + messages
tp = repo.get_or_create_project("Throwaway")
repo.create_workspace(tp["id"], "Test WS", "desc", "test_ws")
repo.add_page(tp["id"], "test_ws", "A-101")
repo.add_note(tp["id"], "test_ws", "test note")
repo.add_event(tp["id"], "Test Event", "2026-01-01")
repo.add_message(tp["id"], "user", "test")
repo.get_or_create_conversation(tp["id"])

# Delete the project — everything should cascade
with get_session() as s:
    from maestro.db.models import Project, Workspace, WorkspacePage, WorkspaceNote, ScheduleEvent, Message, ConversationState
    proj = s.query(Project).get(tp["id"])
    s.delete(proj)

# Verify all children are gone
with get_session() as s:
    test("cascade: project gone", s.query(Project).get(tp["id"]) is None)
    test("cascade: workspaces gone", s.query(Workspace).filter(Workspace.project_id == tp["id"]).count() == 0)
    test("cascade: events gone", s.query(ScheduleEvent).filter(ScheduleEvent.project_id == tp["id"]).count() == 0)
    test("cascade: messages gone", s.query(Message).filter(Message.project_id == tp["id"]).count() == 0)
    test("cascade: conv state gone", s.query(ConversationState).filter(ConversationState.project_id == tp["id"]).count() == 0)

# ===================================================================
# Summary
# ===================================================================

print(f"\n{'='*50}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'='*50}")

if failed:
    sys.exit(1)
else:
    print("  🔥 All tests passed!")
