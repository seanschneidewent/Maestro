# heartbeat.py — Maestro's proactive engine
#
# The heartbeat is Maestro's inner life. Every interval, it wakes up and
# decides what to do based on a simple priority cascade:
#
#   URGENT → TARGETED → CURIOUS → BORED
#
# Urgent:   Schedule event within 48h → review related pages, check for conflicts
# Targeted: Open work in workspaces → deepen, cross-reference, find gaps
# Curious:  Thin experience areas → explore pages in weak disciplines
# Bored:    Nothing pressing → wander, cross-reference, find surprises
#
# The heartbeat uses the exact same tools Maestro uses in conversation.
# Discoveries are stored as workspace notes or experience updates.
# Messages to the super only happen when something is genuinely worth sharing.
#
# Configuration:
#   Work hours (7am-6pm):  every 30 minutes
#   Off hours (6pm-10pm):  every 60 minutes
#   Overnight (10pm-7am):  silent (no heartbeats)

from __future__ import annotations

import json
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any

HEARTBEAT_STATE_PATH = Path(__file__).resolve().parents[2] / "workspaces" / "heartbeat_state.json"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WORK_HOURS = (7, 18)       # 7am - 6pm
OFF_HOURS = (18, 22)       # 6pm - 10pm
SILENT_HOURS = (22, 7)     # 10pm - 7am

WORK_INTERVAL_MIN = 30
OFF_INTERVAL_MIN = 60

# How many days ahead to check for targeted heartbeats
SCHEDULE_LOOKAHEAD_DAYS = 2

# Boredom streak thresholds — the longer the streak, the more adventurous
BOREDOM_ADVENTUROUS_THRESHOLD = 3   # After 3 bored heartbeats, start cross-referencing
BOREDOM_DEEP_DIVE_THRESHOLD = 5     # After 5, do deep vision inspections


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def _load_state() -> dict[str, Any]:
    """Load heartbeat state from disk."""
    if not HEARTBEAT_STATE_PATH.exists():
        return _default_state()
    try:
        data = json.loads(HEARTBEAT_STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _default_state()
        return data
    except (json.JSONDecodeError, OSError):
        return _default_state()


def _save_state(state: dict[str, Any]) -> None:
    """Save heartbeat state to disk."""
    HEARTBEAT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = HEARTBEAT_STATE_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=True)
    tmp.replace(HEARTBEAT_STATE_PATH)


def _default_state() -> dict[str, Any]:
    return {
        "last_heartbeat": "",
        "boredom_streak": 0,
        "pages_visited": {},
        "last_schedule_check": "",
        "discoveries": [],
    }


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def is_silent_hours() -> bool:
    """Check if we're in silent hours (no heartbeats)."""
    hour = datetime.now().hour
    # Silent hours wrap around midnight: 22-23 and 0-6
    return hour >= SILENT_HOURS[0] or hour < SILENT_HOURS[1]


def is_work_hours() -> bool:
    """Check if we're in work hours."""
    hour = datetime.now().hour
    return WORK_HOURS[0] <= hour < WORK_HOURS[1]


def get_interval_minutes() -> int:
    """Get the current heartbeat interval based on time of day."""
    if is_silent_hours():
        return 0  # No heartbeats
    if is_work_hours():
        return WORK_INTERVAL_MIN
    return OFF_INTERVAL_MIN


def should_heartbeat(state: dict[str, Any]) -> bool:
    """Check if enough time has passed since the last heartbeat."""
    if is_silent_hours():
        return False

    interval = get_interval_minutes()
    if interval == 0:
        return False

    last = state.get("last_heartbeat", "")
    if not last:
        return True

    try:
        last_dt = datetime.strptime(last, "%Y-%m-%dT%H:%M:%S")
        elapsed = (datetime.now() - last_dt).total_seconds() / 60
        return elapsed >= interval
    except ValueError:
        return True


# ---------------------------------------------------------------------------
# Heartbeat decision engine
# ---------------------------------------------------------------------------

def decide_heartbeat_mode(
    schedule_events: list[dict[str, Any]],
    workspaces: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    state: dict[str, Any],
    project: dict[str, Any] | None,
) -> dict[str, Any]:
    """Decide what Maestro should do this heartbeat.

    Returns a decision dict:
        {
            "mode": "urgent" | "targeted" | "curious" | "bored",
            "reason": "why this mode was chosen",
            "target": what to focus on (pages, workspace, discipline, etc.),
            "should_message": whether to message the super
        }
    """
    # 1. URGENT — schedule events within 48 hours
    if schedule_events:
        return {
            "mode": "urgent",
            "reason": f"{len(schedule_events)} event(s) in the next {SCHEDULE_LOOKAHEAD_DAYS} days",
            "target": schedule_events,
            "should_message": True,
        }

    # 2. TARGETED — active workspaces with pages to review
    active_workspaces = [w for w in workspaces if w.get("status") == "active" and w.get("page_count", 0) > 0]
    if active_workspaces:
        # Pick the workspace updated least recently
        active_workspaces.sort(key=lambda w: w.get("updated", ""))
        target_workspace = active_workspaces[0]
        return {
            "mode": "targeted",
            "reason": f"Workspace '{target_workspace.get('title')}' has pages to review",
            "target": target_workspace,
            "should_message": False,  # Only message if something found
        }

    # 3. CURIOUS — known gaps or thin disciplines
    if gaps and isinstance(gaps, list):
        return {
            "mode": "curious",
            "reason": f"{len(gaps)} gap(s) to investigate",
            "target": gaps[:5],  # Focus on first 5
            "should_message": False,
        }

    # 4. BORED — nothing pressing, go explore
    boredom_streak = state.get("boredom_streak", 0) + 1
    target = _pick_boredom_target(state, project)

    return {
        "mode": "bored",
        "reason": f"Nothing pressing. Boredom streak: {boredom_streak}",
        "target": target,
        "should_message": False,
        "boredom_streak": boredom_streak,
    }


def _pick_boredom_target(state: dict[str, Any], project: dict[str, Any] | None) -> dict[str, Any]:
    """Pick something interesting to explore when bored.

    Prefers pages that have been visited least, with more regions,
    and from disciplines that are underrepresented in experience.
    """
    if not project:
        return {"type": "no_project", "suggestion": "No project loaded"}

    pages = project.get("pages", {})
    if not pages:
        return {"type": "no_pages", "suggestion": "No pages to explore"}

    visited = state.get("pages_visited", {})
    boredom_streak = state.get("boredom_streak", 0)

    # Score each page — lower score = more interesting
    scored: list[tuple[str, int]] = []
    for page_name, page in pages.items():
        score = 0
        visit_info = visited.get(page_name, {})
        visit_count = visit_info.get("count", 0) if isinstance(visit_info, dict) else 0

        score += visit_count * 10           # Visited often = less interesting
        score += len(page.get("pointers", {}))  # Rich pages already explored
        score -= len([r for r in page.get("regions", []) if isinstance(r, dict) and r.get("id", "") not in page.get("pointers", {})]) * 5  # Missing pointers = interesting

        scored.append((page_name, score))

    # Sort by score (lowest = most interesting)
    scored.sort(key=lambda x: x[1])

    # Pick from bottom 20%
    pool_size = max(1, len(scored) // 5)
    pool = scored[:pool_size]
    chosen_name = random.choice(pool)[0]

    # If high boredom streak, add cross-referencing challenge
    if boredom_streak >= BOREDOM_ADVENTUROUS_THRESHOLD:
        # Pick a second page from a different discipline for cross-referencing
        chosen_discipline = pages[chosen_name].get("discipline", "")
        other_discipline_pages = [
            name for name, page in pages.items()
            if page.get("discipline", "") != chosen_discipline and name != chosen_name
        ]
        cross_ref = random.choice(other_discipline_pages) if other_discipline_pages else None

        return {
            "type": "cross_reference",
            "primary_page": chosen_name,
            "cross_ref_page": cross_ref,
            "suggestion": f"Explore {chosen_name} and look for connections to {cross_ref}",
        }

    return {
        "type": "explore",
        "page": chosen_name,
        "suggestion": f"Explore {chosen_name} — haven't visited much",
    }


def record_heartbeat(
    state: dict[str, Any],
    decision: dict[str, Any],
    pages_explored: list[str] | None = None,
) -> dict[str, Any]:
    """Update state after a heartbeat completes.

    Args:
        state: Current heartbeat state
        decision: The decision dict from decide_heartbeat_mode
        pages_explored: List of page names that were explored this heartbeat
    """
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    state["last_heartbeat"] = now

    # Update boredom streak
    if decision["mode"] == "bored":
        state["boredom_streak"] = decision.get("boredom_streak", state.get("boredom_streak", 0) + 1)
    else:
        state["boredom_streak"] = 0  # Reset on non-bored heartbeat

    # Track page visits
    if pages_explored:
        visited = state.get("pages_visited", {})
        for page_name in pages_explored:
            if page_name not in visited:
                visited[page_name] = {"count": 0, "last": ""}
            visited[page_name]["count"] = visited[page_name].get("count", 0) + 1
            visited[page_name]["last"] = now
        state["pages_visited"] = visited

    if decision["mode"] in ("urgent", "targeted"):
        state["last_schedule_check"] = now

    _save_state(state)
    return state


# ---------------------------------------------------------------------------
# Main heartbeat entry point
# ---------------------------------------------------------------------------

def run_heartbeat(
    schedule_events: list[dict[str, Any]],
    workspaces: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    project: dict[str, Any] | None,
) -> dict[str, Any]:
    """Run one heartbeat cycle.

    This is called by the engine/telegram/API layer on an interval.
    It decides what to do, but does NOT execute the tools directly —
    it returns a decision that the calling layer uses to drive Maestro's
    tools in context (so tool calls go through the same engine as conversations).

    Returns:
        {
            "mode": "urgent" | "targeted" | "curious" | "bored",
            "reason": str,
            "target": what to focus on,
            "should_message": bool,
            "prompt": str  # A prompt to feed to the engine
        }
    """
    state = _load_state()

    if not should_heartbeat(state):
        return {"mode": "skip", "reason": "Not time yet or silent hours"}

    decision = decide_heartbeat_mode(schedule_events, workspaces, gaps, state, project)

    # Build a prompt that the engine can process (same as a user message)
    prompt = _build_heartbeat_prompt(decision)
    decision["prompt"] = prompt

    return decision


def _build_heartbeat_prompt(decision: dict[str, Any]) -> str:
    """Build an internal prompt based on the heartbeat decision.

    This prompt gets fed to the engine just like a user message,
    so Maestro uses its normal tools to execute the heartbeat.
    """
    mode = decision["mode"]
    target = decision.get("target", {})

    if mode == "urgent":
        events = target if isinstance(target, list) else [target]
        event_list = "\n".join(f"- {e.get('title', '?')} ({e.get('start', '?')})" for e in events)
        return (
            f"HEARTBEAT — URGENT: These events are coming up soon:\n{event_list}\n\n"
            "Review the relevant pages for these events. Check for conflicts, gaps, "
            "or anything the superintendent should know before these happen. "
            "If you find something important, note it. Be thorough."
        )

    if mode == "targeted":
        workspace_title = target.get("title", "unknown") if isinstance(target, dict) else str(target)
        return (
            f"HEARTBEAT — TARGETED: Review workspace '{workspace_title}'.\n\n"
            "Look through the pages and notes. Are there open questions? "
            "Missing details? Cross-references to check? "
            "Deepen your understanding. Update your experience if you learn something."
        )

    if mode == "curious":
        gap_list = ""
        if isinstance(target, list):
            gap_list = "\n".join(f"- {g.get('type', '?')}: {g.get('page', g.get('detail', '?'))}" for g in target[:5])
        return (
            f"HEARTBEAT — CURIOUS: Found some gaps to investigate:\n{gap_list}\n\n"
            "Explore these gaps. Use vision if needed. "
            "Update the knowledge store if you find corrections. "
            "Update your experience with what you learn."
        )

    if mode == "bored":
        suggestion = target.get("suggestion", "Explore something new") if isinstance(target, dict) else "Explore something new"
        boredom_type = target.get("type", "explore") if isinstance(target, dict) else "explore"

        if boredom_type == "cross_reference":
            primary = target.get("primary_page", "")
            cross = target.get("cross_ref_page", "")
            return (
                f"HEARTBEAT — BORED (cross-reference mode): Explore {primary} "
                f"and look for connections to {cross}.\n\n"
                "Read both sheets. Look for shared materials, dimensions that should match, "
                "coordination points, or potential conflicts between these disciplines. "
                "If you find something interesting, note it as a workspace note. "
                "Update your experience."
            )

        page = target.get("page", "") if isinstance(target, dict) else ""
        return (
            f"HEARTBEAT — BORED: {suggestion}\n\n"
            f"Read the sheet summary for {page}. Look at the regions. "
            "Is anything surprising? Does anything connect to other work you know about? "
            "If you find something interesting, note it. Update your experience."
        )

    return "HEARTBEAT — Nothing to do."
