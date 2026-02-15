# models.py — SQLAlchemy models for Maestro
#
# Maps directly to the JSON structures in workspaces/, schedule.json,
# conversation.json, and experience/learning_log.json.
#
# Knowledge store stays as files (large, read-heavy, write-once after ingest).

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Project — one Maestro instance = one project
# ---------------------------------------------------------------------------

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(12), primary_key=True, default=_new_id)
    name = Column(String(255), nullable=False)
    path = Column(Text, nullable=True)  # filesystem path to knowledge_store
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    workspaces = relationship("Workspace", back_populates="project", cascade="all, delete-orphan")
    schedule_events = relationship("ScheduleEvent", back_populates="project", cascade="all, delete-orphan")
    conversation = relationship("ConversationState", back_populates="project", uselist=False, cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="project", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Workspace — focused scope of work (e.g. "Foundation & Framing")
# ---------------------------------------------------------------------------

class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(12), ForeignKey("projects.id"), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    status = Column(String(20), default="active")  # active | archived
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    project = relationship("Project", back_populates="workspaces")
    pages = relationship("WorkspacePage", back_populates="workspace", cascade="all, delete-orphan")
    notes = relationship("WorkspaceNote", back_populates="workspace", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# WorkspacePage — a knowledge-store page reference in a workspace
# ---------------------------------------------------------------------------

class WorkspacePage(Base):
    __tablename__ = "workspace_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    page_name = Column(String(255), nullable=False)
    reason = Column(Text, default="")
    added_by = Column(String(50), default="maestro")
    added_at = Column(DateTime(timezone=True), default=_utcnow)
    regions_of_interest = Column(Text, default="[]")  # JSON array stored as text

    # Relationships
    workspace = relationship("Workspace", back_populates="pages")


# ---------------------------------------------------------------------------
# WorkspaceNote — observation or finding attached to a workspace
# ---------------------------------------------------------------------------

class WorkspaceNote(Base):
    __tablename__ = "workspace_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    text = Column(Text, nullable=False)
    source = Column(String(50), default="maestro")
    source_page = Column(String(255), nullable=True)
    added_at = Column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    workspace = relationship("Workspace", back_populates="notes")


# ---------------------------------------------------------------------------
# ScheduleEvent — iCal-compatible event
# ---------------------------------------------------------------------------

class ScheduleEvent(Base):
    __tablename__ = "schedule_events"

    id = Column(String(20), primary_key=True)  # evt_XXXXXXXX format
    project_id = Column(String(12), ForeignKey("projects.id"), nullable=False)
    title = Column(String(255), nullable=False)
    start = Column(String(30), nullable=False)  # ISO date/datetime string
    end = Column(String(30), nullable=False)
    type = Column(String(50), default="phase")  # milestone, phase, inspection, delivery, meeting
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    project = relationship("Project", back_populates="schedule_events")


# ---------------------------------------------------------------------------
# Message — individual conversation message
# ---------------------------------------------------------------------------

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(12), ForeignKey("projects.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    project = relationship("Project", back_populates="messages")


# ---------------------------------------------------------------------------
# ConversationState — metadata for the single continuous conversation
# ---------------------------------------------------------------------------

class ConversationState(Base):
    __tablename__ = "conversation_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(12), ForeignKey("projects.id"), nullable=False, unique=True)
    summary = Column(Text, default="")
    total_exchanges = Column(Integer, default=0)
    compactions = Column(Integer, default=0)
    last_compaction = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    project = relationship("Project", back_populates="conversation")


# ---------------------------------------------------------------------------
# ExperienceLog — audit trail for learning tool changes
# ---------------------------------------------------------------------------

class ExperienceLog(Base):
    __tablename__ = "experience_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tool = Column(String(100), nullable=False)
    details = Column(Text, default="{}")  # JSON blob
    created_at = Column(DateTime(timezone=True), default=_utcnow)
