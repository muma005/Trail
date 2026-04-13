"""
SQLAlchemy ORM models for Trail.
Phase 0: Core identity (projects, user_preferences, sync_logs)
Phase 1: GitHub sync (commits, last_synced_at)
Phase 1.5: Scope filtering (project_scopes), commit parsing
Phase 2: Notion sync (notion_tasks, commit_task_links)
Phase 2.5: Dependencies (task_dependencies, sub_tasks, size_tag)
"""
import uuid
from datetime import datetime, time
from typing import Any, Dict, List

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from src.models.database.base import Base


def generate_uuid():
    """Generate a random UUID string for primary keys."""
    return str(uuid.uuid4())


class Project(Base):
    """
    Core identity: one project = one GitHub repo + one Notion database.
    Both github_repo_url and notion_database_id have UNIQUE constraints
    to prevent cross-pollution.
    last_synced_at tracks incremental sync progress.
    scopes relationship links to branch/path filters.
    Phase 4: status, last_commit_date, notification tracking for escalation.
    """
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_key = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    github_repo_url = Column(Text, unique=True, nullable=False)
    notion_database_id = Column(String(100), unique=True, nullable=False)
    last_synced_at = Column(DateTime, nullable=True)  # Phase 1: incremental sync
    # Phase 4: status and escalation tracking
    status = Column(String(20), default="active")  # active, archived, paused
    last_commit_date = Column(DateTime, nullable=True)
    last_warning_notified_at = Column(DateTime, nullable=True)
    last_critical_notified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Phase 1.5: scope filtering relationship
    scopes = relationship("ProjectScope", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project(key={self.project_key}, name={self.name})>"


class ProjectScope(Base):
    """
    Phase 1.5: Defines which branches and paths a project tracks.
    If no scopes exist for a project, all branches/paths are accepted.
    """
    __tablename__ = "project_scopes"
    __table_args__ = (
        CheckConstraint("scope_type IN ('branch', 'path')", name="chk_scope_type"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_id = Column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_type = Column(String(20), nullable=False)  # 'branch' or 'path'
    scope_value = Column(Text, nullable=False)       # e.g., 'main', 'src/auth/'
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    project = relationship("Project", back_populates="scopes")

    def __repr__(self):
        return f"<ProjectScope(project_id={self.project_id}, type={self.scope_type}, value={self.scope_value})>"


class Commit(Base):
    """
    GitHub commit record linked to a project.
    files_changed stored as JSONB for flexible schema.
    Phase 1.5: parsed_task_id and needs_classification for orphan detection.
    """
    __tablename__ = "commits"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_id = Column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    commit_sha = Column(String(40), unique=True, nullable=False)
    author_name = Column(String(255), nullable=True)
    author_email = Column(String(255), nullable=True)
    commit_date = Column(DateTime, nullable=False)
    message = Column(Text, nullable=False)
    files_changed = Column(JSONB, nullable=True)  # List of {filename, additions, deletions}
    lines_added = Column(Integer, default=0)
    lines_deleted = Column(Integer, default=0)
    # Phase 1.5: commit message parsing
    parsed_task_id = Column(String(100), nullable=True)
    needs_classification = Column(Integer, default=0)  # 0=False, 1=True (SQLite compat)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Commit(sha={self.commit_sha[:8]}, message={self.message[:30]})>"


class UserPreference(Base):
    """
    User work hours and timezone settings.
    Phase 4: abandonment thresholds for escalation engine.
    """
    __tablename__ = "user_preferences"

    user_id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    work_start = Column(Time, default=time(9, 0))
    work_end = Column(Time, default=time(17, 0))
    timezone = Column(String(50), default="UTC")
    # Phase 4: escalation thresholds
    warning_days = Column(Integer, default=7)
    critical_days = Column(Integer, default=14)
    archive_days = Column(Integer, default=21)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SyncLog(Base):
    """
    Audit trail for project creation and future sync operations.
    Records what happened, when, and whether it succeeded.
    """
    __tablename__ = "sync_logs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_id = Column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    sync_type = Column(String(20), nullable=False)  # 'project_creation', 'github', 'notion'
    status = Column(String(20), nullable=False)      # 'success', 'failed', 'partial'
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# -------------------------------------------------------------------------
# Phase 2: Notion sync & linking
# -------------------------------------------------------------------------

class NotionTask(Base):
    """
    Notion page/task synced from a project's Notion database.
    Bulk upserted on notion_page_id to ensure idempotency.
    """
    __tablename__ = "notion_tasks"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_id = Column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    notion_page_id = Column(String(100), unique=True, nullable=False)
    title = Column(Text, nullable=True)
    status = Column(String(50), nullable=True)
    priority = Column(String(20), nullable=True)
    mooscow = Column(String(20), nullable=True)
    due_date = Column(Date, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    progress_percentage = Column(Integer, nullable=True)
    estimated_minutes = Column(Integer, nullable=True)
    actual_minutes = Column(Integer, nullable=True)
    tags = Column(ARRAY(String), nullable=True)
    parent_task_id = Column(
        UUID(as_uuid=False),
        ForeignKey("notion_tasks.id"),
        nullable=True,
    )
    # Phase 2.5: size tag
    size_tag = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sub_tasks = relationship("SubTask", back_populates="parent_task", cascade="all, delete-orphan")
    dependencies = relationship("TaskDependency", foreign_keys="TaskDependency.task_id", back_populates="task", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<NotionTask(id={self.notion_page_id[:8]}, title={self.title})>"


class CommitTaskLink(Base):
    """
    Link between a commit and a Notion task.
    confidence=1.0 means exact match; <1.0 means suggestion.
    is_suggestion=True means pending user review.
    """
    __tablename__ = "commit_task_links"

    commit_id = Column(
        UUID(as_uuid=False),
        ForeignKey("commits.id", ondelete="CASCADE"),
        primary_key=True,
    )
    task_id = Column(
        UUID(as_uuid=False),
        ForeignKey("notion_tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    confidence = Column(Numeric(3, 2), nullable=True)
    is_suggestion = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<CommitTaskLink(commit={self.commit_id[:8]}, task={self.task_id[:8]}, conf={self.confidence})>"


# -------------------------------------------------------------------------
# Phase 2.5: Dependencies & Sub-tasks
# -------------------------------------------------------------------------

class TaskDependency(Base):
    """
    Task dependency: task A blocks/blocked-by task B.
    Supports cross-project dependencies via depends_on_project_id.
    """
    __tablename__ = "task_dependencies"
    __table_args__ = (
        CheckConstraint(
            "depends_on_task_id IS NOT NULL OR depends_on_project_id IS NOT NULL",
            name="chk_depends_not_null",
        ),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    task_id = Column(
        UUID(as_uuid=False),
        ForeignKey("notion_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    depends_on_task_id = Column(
        UUID(as_uuid=False),
        ForeignKey("notion_tasks.id"),
        nullable=True,
    )
    depends_on_project_id = Column(
        UUID(as_uuid=False),
        ForeignKey("projects.id"),
        nullable=True,
    )
    dependency_type = Column(String(50), default="blocks")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    task = relationship("NotionTask", foreign_keys=[task_id], back_populates="dependencies")

    def __repr__(self):
        return f"<TaskDependency(task={self.task_id[:8]}, type={self.dependency_type})>"


class SubTask(Base):
    """
    Sub-task parsed from Notion to_do blocks or child pages.
    Linked to a parent NotionTask.
    """
    __tablename__ = "sub_tasks"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    parent_task_id = Column(
        UUID(as_uuid=False),
        ForeignKey("notion_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = Column(Text, nullable=True)
    is_completed = Column(Boolean, default=False)
    estimated_minutes = Column(Integer, nullable=True)
    order_index = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    parent_task = relationship("NotionTask", back_populates="sub_tasks")

    def __repr__(self):
        return f"<SubTask(title={self.title}, done={self.is_completed})>"


class ProjectSnapshot(Base):
    """
    Phase 3: Daily progress snapshot for a project.
    Tracks task counts, commit counts, and completion percentages.
    """
    __tablename__ = "project_snapshots"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_id = Column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_date = Column(Date, nullable=False)
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    in_progress_tasks = Column(Integer, default=0)
    blocked_tasks = Column(Integer, default=0)
    not_started_tasks = Column(Integer, default=0)
    total_commits = Column(Integer, default=0)
    lines_of_code_added = Column(Integer, default=0)
    completion_percentage_simple = Column(Numeric(5, 2))
    completion_percentage_weighted = Column(Numeric(5, 2))
    snapshot_metadata = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ProjectSnapshot(project={self.project_id}, date={self.snapshot_date})>"


class NotionCommand(Base):
    """
    Phase 5: Stores @ai commands detected in Notion pages.
    Tracks processing status and response block ID.
    """
    __tablename__ = "notion_commands"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_id = Column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    page_id = Column(String(100), nullable=False)
    block_id = Column(String(100), nullable=False)
    command = Column(Text, nullable=False)
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    response_block_id = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)


class ProjectConstraint(Base):
    """
    Phase 6: Planning-specific data per project.
    Tracks remaining hours, deadline, priority, constant flag.
    """
    __tablename__ = "project_constraints"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_id = Column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    estimated_remaining_hours = Column(Numeric(10, 2), default=0, nullable=False)
    deadline = Column(Date, nullable=True)
    priority = Column(String(20), default="Medium")  # Critical, High, Medium, Low
    is_constant = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ProjectConstraint(project={self.project_id}, hours={self.estimated_remaining_hours})>"


class DailyPlan(Base):
    """
    Phase 6: Stores generated daily work plans.
    """
    __tablename__ = "daily_plans"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_id = Column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )
    plan_date = Column(Date, nullable=False)
    allocated_minutes = Column(Integer, nullable=False)
    tasks_planned = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DailyPlan(project={self.project_id}, date={self.plan_date})>"
