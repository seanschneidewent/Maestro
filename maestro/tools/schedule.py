# schedule.py — Schedule management tools
#
# Rewired to use the database layer (maestro.db.repository) instead of
# direct JSON file I/O. Same tool interface to the AI.
#
# Events use iCal-compatible fields so future export to Google Calendar,
# Procore, or P6 is straightforward.

from __future__ import annotations

from datetime import datetime
from typing import Any

from maestro.db import repository as repo

_project_id: str | None = None


def init_schedule(project_id: str | None = None) -> None:
    """Initialize schedule module with the DB project id."""
    global _project_id
    _project_id = project_id


def _require_project_id() -> str | None:
    if not _project_id:
        return None
    return _project_id


def _parse_date(date_str: str) -> datetime | None:
    """Parse a date or datetime string."""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Tools — all DB-backed via repository
# ---------------------------------------------------------------------------

def list_events(
    from_date: str | None = None,
    to_date: str | None = None,
    event_type: str | None = None,
) -> list[dict[str, Any]] | str:
    """List all events, optionally filtered by date range or type."""
    pid = _require_project_id()
    if not pid:
        return "No project loaded."

    events = repo.list_events(pid, from_date=from_date, to_date=to_date, event_type=event_type)
    if not events:
        return "No events on the schedule."
    return events


def get_event(event_id: str) -> dict[str, Any] | str:
    """Get details for a specific event."""
    pid = _require_project_id()
    if not pid:
        return "No project loaded."

    event = repo.get_event(pid, event_id)
    if not event:
        return f"Event '{event_id}' not found."
    return event


def add_event(
    title: str,
    start: str,
    end: str | None = None,
    event_type: str = "phase",
    notes: str = "",
) -> dict[str, Any] | str:
    """Add a new event to the schedule."""
    pid = _require_project_id()
    if not pid:
        return "No project loaded."

    clean_title = title.strip() if isinstance(title, str) else ""
    if not clean_title:
        return "Event title is required."

    start_dt = _parse_date(start)
    if not start_dt:
        return f"Invalid start date: '{start}'. Use YYYY-MM-DD format."

    if end:
        end_dt = _parse_date(end)
        if not end_dt:
            return f"Invalid end date: '{end}'. Use YYYY-MM-DD format."

    return repo.add_event(pid, clean_title, start, end=end, event_type=event_type, notes=notes)


def update_event(
    event_id: str,
    title: str | None = None,
    start: str | None = None,
    end: str | None = None,
    event_type: str | None = None,
    notes: str | None = None,
) -> dict[str, Any] | str:
    """Update an existing event."""
    pid = _require_project_id()
    if not pid:
        return "No project loaded."

    # Validate dates if provided
    if start is not None and not _parse_date(start):
        return f"Invalid start date: '{start}'."
    if end is not None and not _parse_date(end):
        return f"Invalid end date: '{end}'."
    if title is not None and not title.strip():
        return "Event title cannot be empty."

    return repo.update_event(pid, event_id, title=title, start=start, end=end, type=event_type, notes=notes)


def remove_event(event_id: str) -> dict[str, Any] | str:
    """Remove an event from the schedule."""
    pid = _require_project_id()
    if not pid:
        return "No project loaded."
    return repo.remove_event(pid, event_id)


def upcoming(days: int | str = 7) -> list[dict[str, Any]] | str:
    """Quick view of events in the next N days."""
    pid = _require_project_id()
    if not pid:
        return "No project loaded."

    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 7

    events = repo.upcoming_events(pid, days=days)
    if not events:
        return f"Nothing on the schedule for the next {days} days."
    return events


# ---------------------------------------------------------------------------
# Tool definitions + function map — unchanged interface
# ---------------------------------------------------------------------------

schedule_tool_definitions = [
    {
        "name": "list_events",
        "description": "View schedule events, optionally filtered by date range or type",
        "params": {
            "from_date": {"type": "string", "description": "Start of range (YYYY-MM-DD)", "required": False},
            "to_date": {"type": "string", "description": "End of range (YYYY-MM-DD)", "required": False},
            "event_type": {"type": "string", "description": "Filter by type", "required": False},
        },
    },
    {
        "name": "get_event",
        "description": "Get details for a specific event",
        "params": {"event_id": {"type": "string", "required": True}},
    },
    {
        "name": "add_event",
        "description": "Add a new event to the schedule",
        "params": {
            "title": {"type": "string", "required": True},
            "start": {"type": "string", "description": "Start date (YYYY-MM-DD)", "required": True},
            "end": {"type": "string", "description": "End date", "required": False},
            "event_type": {"type": "string", "description": "milestone, phase, inspection, delivery, meeting", "required": False},
            "notes": {"type": "string", "required": False},
        },
    },
    {
        "name": "update_event",
        "description": "Modify an existing event",
        "params": {
            "event_id": {"type": "string", "required": True},
            "title": {"type": "string", "required": False},
            "start": {"type": "string", "required": False},
            "end": {"type": "string", "required": False},
            "event_type": {"type": "string", "required": False},
            "notes": {"type": "string", "required": False},
        },
    },
    {
        "name": "remove_event",
        "description": "Delete an event from the schedule",
        "params": {"event_id": {"type": "string", "required": True}},
    },
    {
        "name": "upcoming",
        "description": "Quick view of events in the next N days",
        "params": {"days": {"type": "integer", "description": "Days ahead (default 7)", "required": False}},
    },
]

schedule_tool_functions = {
    "list_events": list_events,
    "get_event": get_event,
    "add_event": add_event,
    "update_event": update_event,
    "remove_event": remove_event,
    "upcoming": upcoming,
}
