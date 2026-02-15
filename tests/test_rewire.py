# test_rewire.py — Tests for the rewired tools layer
#
# Verifies that workspaces.py, schedule.py, learning.py, and registry.py
# all work correctly through the DB repository instead of JSON files.
#
# Uses in-memory SQLite. No side effects.
#
# Run: python tests/test_rewire.py

import sys
import os
import atexit
import tempfile
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
MAESTRO_DIR = str(Path(__file__).resolve().parent.parent / "maestro")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, MAESTRO_DIR)  # Match server.py convention for bare imports
os.environ["DATABASE_URL"] = "sqlite://"

from maestro.db.models import Base
from maestro.db.session import engine, get_session, init_db
from maestro.db import repository as repo

Base.metadata.create_all(engine)

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


# Create a project for all tests
p = repo.get_or_create_project("CFA Love Field", "/data/cfa")
PID = p["id"]

# Build a mock project dict (simulates in-memory knowledge store)
MOCK_PROJECT = {
    "project_name": "CFA Love Field",
    "pages": {
        "S-101 Structural Foundation Plan": {"path": "/fake"},
        "S-102 Structural Framing Plan": {"path": "/fake"},
        "A-201 Floor Plan": {"path": "/fake"},
        "A-202 Reflected Ceiling Plan": {"path": "/fake"},
        "M-301 HVAC Plan": {"path": "/fake"},
        "P-401 Plumbing Plan": {"path": "/fake"},
        "VC-201 Vapor Mitigation Plan": {"path": "/fake"},
    },
}


# ===================================================================
print("\n== WORKSPACES (rewired) ==")
# ===================================================================

from maestro.tools.workspaces import (
    init_workspaces,
    create_workspace,
    list_workspaces,
    get_workspace,
    add_page,
    remove_page,
    add_note,
)
from maestro.tools import workspaces as workspaces_module

_workspace_tmp = tempfile.TemporaryDirectory()
_orig_workspaces_dir = workspaces_module.WORKSPACES_DIR
_orig_workspaces_index_path = workspaces_module.WORKSPACES_INDEX_PATH
workspaces_module.WORKSPACES_DIR = Path(_workspace_tmp.name) / "workspaces"
workspaces_module.WORKSPACES_INDEX_PATH = workspaces_module.WORKSPACES_DIR / "workspaces.json"


def _cleanup_workspace_tempdir() -> None:
    workspaces_module.WORKSPACES_DIR = _orig_workspaces_dir
    workspaces_module.WORKSPACES_INDEX_PATH = _orig_workspaces_index_path
    _workspace_tmp.cleanup()


atexit.register(_cleanup_workspace_tempdir)

init_workspaces(MOCK_PROJECT)

# --- create_workspace ---
print("\n  -- create_workspace --")
w = create_workspace("Foundation & Framing", "Grade beams, footings, steel framing")
test("create returns dict", isinstance(w, dict))
test("slug generated", w.get("slug") == "foundation_framing")
test("title preserved", w.get("title") == "Foundation & Framing")
test("page_count starts 0", w.get("page_count") == 0)
test("status active", w.get("status") == "active")

# Idempotent
w2 = create_workspace("Foundation & Framing", "different desc")
test("idempotent same slug", w2.get("slug") == "foundation_framing")

# Validation
test("empty title rejected", isinstance(create_workspace("", "desc"), str))
test("empty desc rejected", isinstance(create_workspace("Title", ""), str))

# Create more workspaces
create_workspace("Kitchen Rough-In", "All kitchen MEP coordination")
create_workspace("Walk-In Cooler", "Cooler and freezer scope")

# --- list_workspaces ---
print("\n  -- list_workspaces --")
ws = list_workspaces()
test("returns list", isinstance(ws, list))
test("count = 3", len(ws) == 3)
titles = {w["title"] for w in ws}
test("all titles present", titles == {"Foundation & Framing", "Kitchen Rough-In", "Walk-In Cooler"})

# --- get_workspace ---
print("\n  -- get_workspace --")
# Exact slug
ws_full = get_workspace("foundation_framing")
test("exact slug works", isinstance(ws_full, dict) and "metadata" in ws_full)
test("has pages list", isinstance(ws_full.get("pages"), list))
test("has notes list", isinstance(ws_full.get("notes"), list))

# By title
ws_by_title = get_workspace("Kitchen Rough-In")
test("title resolution", isinstance(ws_by_title, dict) and ws_by_title["metadata"]["slug"] == "kitchen_rough_in")

# Slugified input
ws_slugified = get_workspace("Walk-In Cooler")
test("slugified resolution", isinstance(ws_slugified, dict) and ws_slugified["metadata"]["slug"] == "walk_in_cooler")

# Not found
test("not found returns str", isinstance(get_workspace("nonexistent"), str))

# --- add_page ---
print("\n  -- add_page --")
# Full page name
r = add_page("foundation_framing", "S-101 Structural Foundation Plan", "Foundation structural details")
test("add_page success", isinstance(r, dict) and r["page_count"] == 1)
test("resolved page name", r["page_name"] == "S-101 Structural Foundation Plan")

# Fuzzy match (prefix)
r2 = add_page("foundation_framing", "S-102", "Framing details")
test("fuzzy prefix match", isinstance(r2, dict) and r2["page_name"] == "S-102 Structural Framing Plan")
test("page_count = 2", r2["page_count"] == 2)

# Fuzzy match (substring)
r3 = add_page("foundation_framing", "Vapor Mitigation", "VC coordination")
test("substring match", isinstance(r3, dict) and r3["page_name"] == "VC-201 Vapor Mitigation Plan")

# Duplicate rejection
dup = add_page("foundation_framing", "S-101 Structural Foundation Plan", "dup")
test("duplicate rejected", isinstance(dup, str) and "already" in dup)

# Ambiguous match (A-20 matches both A-201 and A-202)
amb = add_page("foundation_framing", "A-20", "test")
test("ambiguous match flagged", isinstance(amb, str) and "ambiguous" in amb.lower())

# Page not found in project
nf = add_page("foundation_framing", "Z-999 Nonexistent Sheet", "test")
test("page not in project", isinstance(nf, str) and "not found" in nf.lower())

# Empty reason
test("empty reason rejected", isinstance(add_page("foundation_framing", "A-201", ""), str))

# Bad workspace
test("bad workspace", isinstance(add_page("nonexistent", "A-201", "reason"), str))

# By title resolution for workspace
r_title = add_page("Kitchen Rough-In", "P-401 Plumbing Plan", "Kitchen plumbing")
test("workspace by title", isinstance(r_title, dict) and r_title["workspace_slug"] == "kitchen_rough_in")

# --- remove_page ---
print("\n  -- remove_page --")
rm = remove_page("foundation_framing", "S-101 Structural Foundation Plan")
test("remove success", isinstance(rm, dict) and rm["removed"] == True)
test("page_count decremented", rm["page_count"] == 2)  # was 3 (S-101, S-102, VC-201), now 2

# Fuzzy remove
rm2 = remove_page("foundation_framing", "S-102")
test("fuzzy remove", isinstance(rm2, dict) and rm2["page_name"] == "S-102 Structural Framing Plan")

# Remove not found
test("remove not found", isinstance(remove_page("foundation_framing", "S-101"), str))

# Bad workspace
test("remove bad workspace", isinstance(remove_page("nonexistent", "S-101"), str))

# --- add_note ---
print("\n  -- add_note --")
n = add_note("foundation_framing", "3-inch pipe sleeves through grade beams not shown on structural", source_page="VC-201 Vapor Mitigation Plan")
test("add_note success", isinstance(n, dict) and n["note_count"] == 1)
test("source_page resolved", n["note"]["source_page"] == "VC-201 Vapor Mitigation Plan")

n2 = add_note("foundation_framing", "Epoxy anchor special inspection required")
test("note without source", isinstance(n2, dict) and n2["note"]["source_page"] is None)

# Fuzzy source page
n3 = add_note("foundation_framing", "HVAC duct routing check needed", source_page="M-301")
test("fuzzy source page", isinstance(n3, dict) and n3["note"]["source_page"] == "M-301 HVAC Plan")

# Bad source page
test("bad source page", isinstance(add_note("foundation_framing", "note", source_page="Z-999"), str))

# Ambiguous source page
test("ambiguous source page", isinstance(add_note("foundation_framing", "note", source_page="A-20"), str))

# Empty note
test("empty note rejected", isinstance(add_note("foundation_framing", ""), str))

# Bad workspace
test("note bad workspace", isinstance(add_note("nonexistent", "note"), str))

# Verify notes persisted in get_workspace
ws_final = get_workspace("foundation_framing")
test("notes persisted", len(ws_final["notes"]) == 3)
test("note text correct", ws_final["notes"][0]["text"].startswith("3-inch pipe sleeves"))

# --- No project loaded ---
print("\n  -- no project edge cases --")
init_workspaces(None)
test("add_page no project", isinstance(add_page("foundation_framing", "S-101", "test"), str) and "No project" in add_page("foundation_framing", "S-101", "test"))
# Restore
init_workspaces(MOCK_PROJECT)


# ===================================================================
print("\n== SCHEDULE (rewired) ==")
# ===================================================================

from maestro.tools.schedule import (
    init_schedule,
    list_events,
    get_event,
    add_event,
    update_event,
    remove_event,
    upcoming,
)

init_schedule(project_id=PID)

print("\n  -- add_event --")
e1 = add_event("Foundation Pour", "2026-02-20", event_type="milestone")
test("add success", isinstance(e1, dict) and e1["id"].startswith("evt_"))
test("title", e1["title"] == "Foundation Pour")
test("type", e1["type"] == "milestone")
test("end defaults", e1["end"] == "2026-02-20")

e2 = add_event("Kitchen Rough-In", "2026-03-01", end="2026-03-15", event_type="phase", notes="All MEP trades")
test("add with end+notes", e2["end"] == "2026-03-15" and e2["notes"] == "All MEP trades")

e3 = add_event("Final Inspection", "2026-04-01", event_type="inspection")
test("add third event", isinstance(e3, dict))

# Validation
test("empty title", isinstance(add_event("", "2026-01-01"), str))
test("bad start date", isinstance(add_event("Test", "not-a-date"), str))
test("bad end date", isinstance(add_event("Test", "2026-01-01", end="not-a-date"), str))

print("\n  -- list_events --")
events = list_events()
test("list all", isinstance(events, list) and len(events) == 3)

events_feb = list_events(from_date="2026-02-01", to_date="2026-02-28")
test("date filter", isinstance(events_feb, list) and len(events_feb) == 1)

events_ms = list_events(event_type="milestone")
test("type filter", isinstance(events_ms, list) and len(events_ms) == 1)

events_combo = list_events(from_date="2026-03-01", to_date="2026-03-31", event_type="phase")
test("combo filter", isinstance(events_combo, list) and len(events_combo) == 1)

events_empty = list_events(from_date="2025-01-01", to_date="2025-12-31")
test("empty result", isinstance(events_empty, str) and "No events" in events_empty)

print("\n  -- get_event --")
got = get_event(e1["id"])
test("get by id", isinstance(got, dict) and got["title"] == "Foundation Pour")
test("get not found", isinstance(get_event("evt_fake"), str))

print("\n  -- update_event --")
upd = update_event(e1["id"], title="Foundation Pour - DELAYED", start="2026-02-25")
test("update success", isinstance(upd, dict) and upd["title"] == "Foundation Pour - DELAYED" and upd["start"] == "2026-02-25")

# Partial update — only notes
upd2 = update_event(e2["id"], notes="Updated: includes ductwork")
test("partial update", isinstance(upd2, dict) and upd2["notes"] == "Updated: includes ductwork" and upd2["title"] == "Kitchen Rough-In")

# Validation
test("update not found", isinstance(update_event("evt_fake", title="x"), str))
test("update bad date", isinstance(update_event(e1["id"], start="bad"), str))
test("update empty title", isinstance(update_event(e1["id"], title=""), str))

print("\n  -- remove_event --")
rm = remove_event(e3["id"])
test("remove success", isinstance(rm, dict) and rm["removed"] == e3["id"])
test("remove remaining", rm["remaining"] == 2)
test("remove not found", isinstance(remove_event("evt_fake"), str))

print("\n  -- upcoming --")
up = upcoming(days=60)
test("upcoming returns", isinstance(up, list) or isinstance(up, str))  # depends on date

up_zero = upcoming(days=0)
test("upcoming 0 days", isinstance(up_zero, str) or isinstance(up_zero, list))

up_bad = upcoming(days="not_a_number")
test("upcoming bad input defaults", isinstance(up_bad, str) or isinstance(up_bad, list))

# No project_id
print("\n  -- no pid edge cases --")
init_schedule(project_id=None)
test("list no pid", isinstance(list_events(), str))
test("add no pid", isinstance(add_event("Test", "2026-01-01"), str))
test("get no pid", isinstance(get_event("evt_x"), str))
test("update no pid", isinstance(update_event("evt_x", title="x"), str))
test("remove no pid", isinstance(remove_event("evt_x"), str))
test("upcoming no pid", isinstance(upcoming(), str))
init_schedule(project_id=PID)  # restore


# ===================================================================
print("\n== LEARNING (rewired audit log) ==")
# ===================================================================

from maestro.db.models import ExperienceLog

# Clear any prior log entries from earlier tests
with get_session() as s:
    s.query(ExperienceLog).delete()

from maestro.tools.learning import _log_change

_log_change("update_experience", {"file": "patterns.json", "field": "common_gaps", "result": "OK: appended"})
_log_change("update_knowledge", {"page": "S-101", "field": "cross_references", "result": "OK: added"})
_log_change("update_tool_description", {"tool_name": "search", "result": "OK: updated tips"})

with get_session() as s:
    entries = s.query(ExperienceLog).order_by(ExperienceLog.id).all()
    test("3 log entries", len(entries) == 3)
    test("first tool name", entries[0].tool == "update_experience")
    test("details is JSON", "patterns.json" in entries[0].details)
    test("third tool name", entries[2].tool == "update_tool_description")


# ===================================================================
print("\n== REGISTRY INTEGRATION ==")
# ===================================================================

from maestro.tools.registry import build_tool_registry

defs, funcs = build_tool_registry(MOCK_PROJECT, project_id=PID)

test("definitions is list", isinstance(defs, list))
test("28 tool definitions", len(defs) == 28, f"got {len(defs)}")
test("functions is dict", isinstance(funcs, dict))
test("28 tool functions", len(funcs) == 28, f"got {len(funcs)}")

# Check all definition names have matching functions
def_names = {d["name"] for d in defs}
func_names = set(funcs.keys())
test("all defs have funcs", def_names == func_names, f"missing: {def_names - func_names}, extra: {func_names - def_names}")

# Key tools present
for tool_name in ["create_workspace", "list_workspaces", "add_page", "add_note",
                   "list_events", "add_event", "upcoming",
                   "search", "see_page", "gemini_vision_agent",
                   "update_experience", "update_knowledge"]:
    test(f"tool '{tool_name}' registered", tool_name in func_names)

# Call workspace tool through registry
result = funcs["list_workspaces"]()
test("registry list_workspaces works", isinstance(result, list) and len(result) == 3)

# Call schedule tool through registry
result = funcs["list_events"]()
test("registry list_events works", isinstance(result, list))


# ===================================================================
print("\n== CONVERSATION (rewired to DB) ==")
# ===================================================================

# Test conversation DB operations directly (not full Conversation class
# since that requires real API keys and project loading)

print("\n  -- message flow --")
# Simulate a conversation
repo.get_or_create_conversation(PID)

m1 = repo.add_message(PID, "user", "What's the foundation look like?")
m2 = repo.add_message(PID, "assistant", "The foundation plan shows post-tensioned grade beams...")
m3 = repo.add_message(PID, "user", "Are there pipe sleeves?")
m4 = repo.add_message(PID, "assistant", "Yes, VC sheets show 3-inch sleeves through grade beams.")
m5 = repo.add_message(PID, "user", "What about the pour date?")
m6 = repo.add_message(PID, "assistant", "Foundation pour is scheduled for Feb 25.")

test("6 messages stored", repo.count_messages(PID) == 6)

# Get recent (simulating what conversation.py does for API calls)
recent = repo.get_recent_messages(PID, count=4)
test("recent = last 4", len(recent) == 4 and recent[0]["id"] == m3)

# Simulate compaction: delete old, update summary
deleted = repo.delete_messages_before(PID, m3)
test("compaction deleted 2", deleted == 2)
test("4 remaining", repo.count_messages(PID) == 4)

repo.update_conversation_state(
    PID,
    summary="Discussed foundation plan. Post-tensioned grade beams. Pipe sleeves confirmed on VC sheets.",
    increment_compactions=True,
)

state = repo.get_or_create_conversation(PID)
test("summary stored", "grade beams" in state["summary"])
test("compaction count", state["compactions"] == 1)
test("last_compaction set", state["last_compaction"] != "")

# Second round of messages
m7 = repo.add_message(PID, "user", "What trades need to coordinate?")
m8 = repo.add_message(PID, "assistant", "Structural, plumbing, and vapor mitigation all intersect at the grade beams.")
test("messages accumulate", repo.count_messages(PID) == 6)

# Increment exchanges
repo.update_conversation_state(PID, increment_exchanges=True)
repo.update_conversation_state(PID, increment_exchanges=True)
repo.update_conversation_state(PID, increment_exchanges=True)
state = repo.get_or_create_conversation(PID)
test("exchange count", state["total_exchanges"] == 3)

# Summary update (second compaction)
repo.update_conversation_state(
    PID,
    summary="Foundation: PT grade beams, 3\" pipe sleeves (VC), pour Feb 25. Coordination: structural + plumbing + VC.",
    increment_compactions=True,
)
state = repo.get_or_create_conversation(PID)
test("summary updated", "Coordination" in state["summary"])
test("compaction count = 2", state["compactions"] == 2)

print("\n  -- conversation token estimation --")
from maestro.messaging.conversation import _estimate_tokens, _estimate_messages_tokens, _needs_compaction

test("token estimate", _estimate_tokens("hello world") == 2)  # 11 chars / 4
test("empty = 0 tokens", _estimate_tokens("") == 0)

msgs = [{"content": "x" * 400}, {"content": "y" * 400}]
test("messages tokens", _estimate_messages_tokens(msgs) == 200)

# Content blocks (Anthropic format)
msgs_blocks = [{"content": [{"type": "text", "text": "hello"}]}]
test("block content tokens", _estimate_messages_tokens(msgs_blocks) > 0)

# Compaction threshold
test("under threshold", not _needs_compaction(1000, 500, 2000, 200000))
test("over threshold", _needs_compaction(50000, 30000, 60000, 200000))
test("at threshold", _needs_compaction(65000, 0, 65000, 200000))

print("\n  -- compaction text building --")
from maestro.messaging.conversation import _messages_to_text, _build_compaction_prompt

msgs_for_text = [
    {"role": "user", "content": "What about the foundation?"},
    {"role": "assistant", "content": "The grade beams are post-tensioned."},
]
text = _messages_to_text(msgs_for_text)
test("messages_to_text user", "Super: What about" in text)
test("messages_to_text assistant", "Maestro: The grade beams" in text)

prompt = _build_compaction_prompt("Previous: discussed kitchen", text)
test("compaction prompt has existing", "Previous: discussed kitchen" in prompt)
test("compaction prompt has new", "Super: What about" in prompt)

# Empty summary
prompt_no_summary = _build_compaction_prompt("", text)
test("compaction prompt no summary", "EXISTING SUMMARY" not in prompt_no_summary)


# ===================================================================
# Cross-domain: workspace + schedule in same project
# ===================================================================
print("\n== CROSS-DOMAIN INTEGRITY ==")

# Verify workspace and schedule data coexist correctly
ws_list = list_workspaces()
evt_list = list_events()
test("workspaces still there", isinstance(ws_list, list) and len(ws_list) == 3)
test("events still there", isinstance(evt_list, list) and len(evt_list) == 2)

# Messages still there
test("messages still there", repo.count_messages(PID) == 6)

# Get workspace with all its data
ws = get_workspace("foundation_framing")
test("workspace pages intact", len(ws["pages"]) == 1)  # VC-201 remains after removes
test("workspace notes intact", len(ws["notes"]) == 3)


# ===================================================================
# Summary
# ===================================================================

print(f"\n{'='*50}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'='*50}")

if failed:
    sys.exit(1)
else:
    print("  ALL REWIRE TESTS PASSED!")
