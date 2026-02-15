# repository.py — CRUD operations for Maestro's database
#
# The tools call these functions instead of reading/writing JSON files.
# Each function is a clean unit of work with its own session scope.
#
# Organized by domain:
#   - Projects
#   - Workspaces (+ pages + notes)
#   - Schedule events
#   - Conversation (messages + state)
#   - Experience log

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from .models import (
    ConversationState,
    ExperienceLog,
    Message,
    Project,
    ScheduleEvent,
    Workspace,
    WorkspaceNote,
    WorkspacePage,
)
from .session import get_session


# ---------------------------------------------------------------------------
# WebSocket emitters (lazy import to avoid circular deps)
# ---------------------------------------------------------------------------

def _emit_ws(fn_name, *args, **kwargs):
    """Best-effort WebSocket emit. No-op if websocket module not available."""
    try:
        from maestro.api.websocket import (
            emit_message,
            emit_workspace_change,
            emit_schedule_change,
            emit_compaction,
            emit_engine_switch,
        )
        fn = {
            "message": emit_message,
            "workspace": emit_workspace_change,
            "schedule": emit_schedule_change,
            "compaction": emit_compaction,
            "engine_switch": emit_engine_switch,
        }.get(fn_name)
        if fn:
            fn(*args, **kwargs)
    except Exception:
        pass  # Best effort — never crash the caller


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.isoformat()


# ===================================================================
# Projects
# ===================================================================

def get_or_create_project(name: str, path: str | None = None) -> dict[str, Any]:
    """Get existing project by name or create a new one."""
    with get_session() as s:
        project = s.query(Project).filter(Project.name == name).first()
        if not project:
            project = Project(
                id=uuid.uuid4().hex[:12],
                name=name,
                path=path,
            )
            s.add(project)
            s.flush()
        return {
            "id": project.id,
            "name": project.name,
            "path": project.path,
            "created_at": _iso(project.created_at),
        }


def get_project(project_id: str) -> dict[str, Any] | None:
    with get_session() as s:
        p = s.query(Project).get(project_id)
        if not p:
            return None
        return {"id": p.id, "name": p.name, "path": p.path, "created_at": _iso(p.created_at)}


# ===================================================================
# Workspaces
# ===================================================================

def list_workspaces(project_id: str) -> list[dict[str, Any]]:
    with get_session() as s:
        workspaces = (
            s.query(Workspace)
            .filter(Workspace.project_id == project_id)
            .order_by(Workspace.created_at)
            .all()
        )
        return [
            {
                "slug": w.slug,
                "title": w.title,
                "description": w.description,
                "page_count": len(w.pages),
                "status": w.status,
                "created": _iso(w.created_at),
                "updated": _iso(w.updated_at),
            }
            for w in workspaces
        ]


def get_workspace(project_id: str, slug: str) -> dict[str, Any] | None:
    """Get full workspace state by slug."""
    with get_session() as s:
        w = (
            s.query(Workspace)
            .filter(and_(Workspace.project_id == project_id, Workspace.slug == slug))
            .first()
        )
        if not w:
            return None
        return {
            "metadata": {
                "title": w.title,
                "slug": w.slug,
                "description": w.description,
                "created": _iso(w.created_at),
                "updated": _iso(w.updated_at),
                "status": w.status,
            },
            "pages": [
                {
                    "page_name": p.page_name,
                    "reason": p.reason,
                    "added_by": p.added_by,
                    "added_at": _iso(p.added_at),
                    "regions_of_interest": json.loads(p.regions_of_interest or "[]"),
                }
                for p in w.pages
            ],
            "notes": [
                {
                    "text": n.text,
                    "source": n.source,
                    "source_page": n.source_page,
                    "added_at": _iso(n.added_at),
                }
                for n in w.notes
            ],
        }


def resolve_workspace_slug(project_id: str, raw_slug: str) -> str | None:
    """Resolve a workspace slug by exact match, slugified match, or title match."""
    import re

    def slugify(t: str) -> str:
        s = re.sub(r"[^a-z0-9]+", "_", t.lower())
        return re.sub(r"_+", "_", s).strip("_") or "workspace"

    with get_session() as s:
        workspaces = s.query(Workspace).filter(Workspace.project_id == project_id).all()

        # Exact slug match
        for w in workspaces:
            if w.slug == raw_slug.strip():
                return w.slug

        # Slugified match
        slugified = slugify(raw_slug)
        for w in workspaces:
            if w.slug == slugified:
                return w.slug

        # Title match (case-insensitive)
        for w in workspaces:
            if w.title.strip().lower() == raw_slug.strip().lower():
                return w.slug

        return None


def create_workspace(project_id: str, title: str, description: str, slug: str) -> dict[str, Any]:
    """Create a workspace or return existing one if slug matches."""
    with get_session() as s:
        existing = (
            s.query(Workspace)
            .filter(and_(Workspace.project_id == project_id, Workspace.slug == slug))
            .first()
        )
        if existing:
            return {
                "slug": existing.slug,
                "title": existing.title,
                "description": existing.description,
                "created": _iso(existing.created_at),
                "updated": _iso(existing.updated_at),
                "status": existing.status,
                "page_count": len(existing.pages),
            }

        w = Workspace(
            project_id=project_id,
            slug=slug,
            title=title,
            description=description,
        )
        s.add(w)
        s.flush()
        _emit_ws("workspace", "created", slug, detail=title)
        return {
            "slug": w.slug,
            "title": w.title,
            "description": w.description,
            "created": _iso(w.created_at),
            "updated": _iso(w.updated_at),
            "status": w.status,
            "page_count": 0,
        }


def add_page(project_id: str, slug: str, page_name: str, reason: str) -> dict[str, Any] | str:
    """Add a page reference to a workspace."""
    with get_session() as s:
        w = (
            s.query(Workspace)
            .filter(and_(Workspace.project_id == project_id, Workspace.slug == slug))
            .first()
        )
        if not w:
            return f"Workspace '{slug}' not found."

        # Check duplicate
        existing = (
            s.query(WorkspacePage)
            .filter(and_(WorkspacePage.workspace_id == w.id, WorkspacePage.page_name == page_name))
            .first()
        )
        if existing:
            return f"Page '{page_name}' is already in workspace '{slug}'."

        page = WorkspacePage(
            workspace_id=w.id,
            page_name=page_name,
            reason=reason,
        )
        s.add(page)
        w.updated_at = _utcnow()
        s.flush()

        page_count = s.query(WorkspacePage).filter(WorkspacePage.workspace_id == w.id).count()
        _emit_ws("workspace", "page_added", slug, detail=page_name)
        return {
            "workspace_slug": slug,
            "page_name": page_name,
            "reason": reason,
            "page_count": page_count,
        }


def remove_page(project_id: str, slug: str, page_name: str) -> dict[str, Any] | str:
    """Remove a page reference from a workspace."""
    with get_session() as s:
        w = (
            s.query(Workspace)
            .filter(and_(Workspace.project_id == project_id, Workspace.slug == slug))
            .first()
        )
        if not w:
            return f"Workspace '{slug}' not found."

        page = (
            s.query(WorkspacePage)
            .filter(and_(WorkspacePage.workspace_id == w.id, WorkspacePage.page_name == page_name))
            .first()
        )
        if not page:
            return f"Page '{page_name}' is not in workspace '{slug}'."

        s.delete(page)
        w.updated_at = _utcnow()
        s.flush()

        page_count = s.query(WorkspacePage).filter(WorkspacePage.workspace_id == w.id).count()
        _emit_ws("workspace", "page_removed", slug, detail=page_name)
        return {
            "workspace_slug": slug,
            "page_name": page_name,
            "page_count": page_count,
            "removed": True,
        }


def add_note(project_id: str, slug: str, text: str, source_page: str | None = None) -> dict[str, Any] | str:
    """Add a note to a workspace."""
    with get_session() as s:
        w = (
            s.query(Workspace)
            .filter(and_(Workspace.project_id == project_id, Workspace.slug == slug))
            .first()
        )
        if not w:
            return f"Workspace '{slug}' not found."

        note = WorkspaceNote(
            workspace_id=w.id,
            text=text,
            source_page=source_page,
        )
        s.add(note)
        w.updated_at = _utcnow()
        s.flush()

        note_count = s.query(WorkspaceNote).filter(WorkspaceNote.workspace_id == w.id).count()
        _emit_ws("workspace", "note_added", slug, detail=text[:100])
        return {
            "workspace_slug": slug,
            "note": {
                "text": text,
                "source": "maestro",
                "source_page": source_page,
                "added_at": _iso(note.added_at),
            },
            "note_count": note_count,
        }


# ===================================================================
# Schedule Events
# ===================================================================

def _generate_event_id() -> str:
    return f"evt_{uuid.uuid4().hex[:8]}"


def list_events(
    project_id: str,
    from_date: str | None = None,
    to_date: str | None = None,
    event_type: str | None = None,
) -> list[dict[str, Any]]:
    with get_session() as s:
        q = s.query(ScheduleEvent).filter(ScheduleEvent.project_id == project_id)

        if from_date:
            q = q.filter(ScheduleEvent.end >= from_date)
        if to_date:
            q = q.filter(ScheduleEvent.start <= to_date)
        if event_type:
            q = q.filter(ScheduleEvent.type == event_type.lower())

        events = q.order_by(ScheduleEvent.start).all()
        return [
            {
                "id": e.id,
                "title": e.title,
                "start": e.start,
                "end": e.end,
                "type": e.type,
                "notes": e.notes,
                "created": _iso(e.created_at),
            }
            for e in events
        ]


def get_event(project_id: str, event_id: str) -> dict[str, Any] | None:
    with get_session() as s:
        e = s.query(ScheduleEvent).filter(
            and_(ScheduleEvent.project_id == project_id, ScheduleEvent.id == event_id)
        ).first()
        if not e:
            return None
        return {
            "id": e.id, "title": e.title, "start": e.start, "end": e.end,
            "type": e.type, "notes": e.notes, "created": _iso(e.created_at),
        }


def add_event(
    project_id: str,
    title: str,
    start: str,
    end: str | None = None,
    event_type: str = "phase",
    notes: str = "",
) -> dict[str, Any]:
    event_id = _generate_event_id()
    with get_session() as s:
        e = ScheduleEvent(
            id=event_id,
            project_id=project_id,
            title=title,
            start=start,
            end=end or start,
            type=event_type.strip().lower(),
            notes=notes.strip(),
        )
        s.add(e)
        s.flush()
        _emit_ws("schedule", "added", event_id, title=title)
        return {
            "id": e.id, "title": e.title, "start": e.start, "end": e.end,
            "type": e.type, "notes": e.notes, "created": _iso(e.created_at),
        }


def update_event(project_id: str, event_id: str, **kwargs: Any) -> dict[str, Any] | str:
    with get_session() as s:
        e = s.query(ScheduleEvent).filter(
            and_(ScheduleEvent.project_id == project_id, ScheduleEvent.id == event_id)
        ).first()
        if not e:
            return f"Event '{event_id}' not found."

        for field in ("title", "start", "end", "type", "notes"):
            if field in kwargs and kwargs[field] is not None:
                val = kwargs[field]
                if field == "type":
                    val = val.strip().lower()
                elif isinstance(val, str):
                    val = val.strip()
                setattr(e, field, val)

        s.flush()
        _emit_ws("schedule", "updated", event_id, title=e.title)
        return {
            "id": e.id, "title": e.title, "start": e.start, "end": e.end,
            "type": e.type, "notes": e.notes, "created": _iso(e.created_at),
        }


def remove_event(project_id: str, event_id: str) -> dict[str, Any] | str:
    with get_session() as s:
        e = s.query(ScheduleEvent).filter(
            and_(ScheduleEvent.project_id == project_id, ScheduleEvent.id == event_id)
        ).first()
        if not e:
            return f"Event '{event_id}' not found."
        title = e.title
        s.delete(e)
        s.flush()
        remaining = s.query(ScheduleEvent).filter(ScheduleEvent.project_id == project_id).count()
        _emit_ws("schedule", "removed", event_id, title=title)
        return {"removed": event_id, "remaining": remaining}


def upcoming_events(project_id: str, days: int = 7) -> list[dict[str, Any]]:
    today = datetime.now().strftime("%Y-%m-%d")
    future = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    return list_events(project_id, from_date=today, to_date=future)


# ===================================================================
# Conversation — Messages + State
# ===================================================================

def get_or_create_conversation(project_id: str) -> dict[str, Any]:
    """Get or create the conversation state for a project."""
    with get_session() as s:
        state = s.query(ConversationState).filter(ConversationState.project_id == project_id).first()
        if not state:
            state = ConversationState(project_id=project_id)
            s.add(state)
            s.flush()
        return {
            "id": state.id,
            "summary": state.summary or "",
            "total_exchanges": state.total_exchanges,
            "compactions": state.compactions,
            "last_compaction": _iso(state.last_compaction),
            "created_at": _iso(state.created_at),
        }


def add_message(project_id: str, role: str, content: str) -> int:
    """Add a message and return its id."""
    with get_session() as s:
        msg = Message(project_id=project_id, role=role, content=content)
        s.add(msg)
        s.flush()
        _emit_ws("message", role, content[:500] if isinstance(content, str) else "", message_id=msg.id)
        return msg.id


def get_messages(project_id: str, limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
    """Get messages ordered by creation time. Newest last."""
    with get_session() as s:
        q = (
            s.query(Message)
            .filter(Message.project_id == project_id)
            .order_by(Message.created_at)
        )
        if offset:
            q = q.offset(offset)
        if limit:
            q = q.limit(limit)
        return [
            {"id": m.id, "role": m.role, "content": m.content, "created_at": _iso(m.created_at)}
            for m in q.all()
        ]


def get_recent_messages(project_id: str, count: int = 20) -> list[dict[str, Any]]:
    """Get the N most recent messages."""
    with get_session() as s:
        # Subquery to get the last N by id desc, then re-order asc
        msgs = (
            s.query(Message)
            .filter(Message.project_id == project_id)
            .order_by(Message.id.desc())
            .limit(count)
            .all()
        )
        msgs.reverse()
        return [
            {"id": m.id, "role": m.role, "content": m.content, "created_at": _iso(m.created_at)}
            for m in msgs
        ]


def count_messages(project_id: str) -> int:
    with get_session() as s:
        return s.query(Message).filter(Message.project_id == project_id).count()


def delete_messages_before(project_id: str, message_id: int) -> int:
    """Delete messages older than the given id. Returns count deleted."""
    with get_session() as s:
        count = (
            s.query(Message)
            .filter(and_(Message.project_id == project_id, Message.id < message_id))
            .delete()
        )
        return count


def update_conversation_state(
    project_id: str,
    summary: str | None = None,
    increment_exchanges: bool = False,
    increment_compactions: bool = False,
) -> None:
    """Update conversation metadata."""
    with get_session() as s:
        state = s.query(ConversationState).filter(ConversationState.project_id == project_id).first()
        if not state:
            state = ConversationState(project_id=project_id)
            s.add(state)

        if summary is not None:
            state.summary = summary
        if increment_exchanges:
            state.total_exchanges = (state.total_exchanges or 0) + 1
        if increment_compactions:
            state.compactions = (state.compactions or 0) + 1
            state.last_compaction = _utcnow()

        s.flush()


# ===================================================================
# Experience Log
# ===================================================================

def log_experience(tool: str, details: dict[str, Any]) -> None:
    """Append to the experience audit trail."""
    with get_session() as s:
        entry = ExperienceLog(
            tool=tool,
            details=json.dumps(details, ensure_ascii=False),
        )
        s.add(entry)
