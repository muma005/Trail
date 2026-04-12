"""
SQLAlchemy ORM models for Trail.
Defines the database schema in Python code.
Phase 0: Core identity (projects, user_preferences, sync_logs)
Phase 1: GitHub sync (commits table, last_synced_at on projects)
Phase 1.5: Scope filtering (project_scopes), commit parsing (parsed_task_id, needs_classification)
"""
import uuid
from datetime import datetime, time
from typing import Any, Dict, List

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
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
    """
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_key = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    github_repo_url = Column(Text, unique=True, nullable=False)
    notion_database_id = Column(String(100), unique=True, nullable=False)
    last_synced_at = Column(DateTime, nullable=True)  # Phase 1: incremental sync
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
    Single-user for now but designed with multi-user in mind.
    """
    __tablename__ = "user_preferences"

    user_id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    work_start = Column(Time, default=time(9, 0))
    work_end = Column(Time, default=time(17, 0))
    timezone = Column(String(50), default="UTC")
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
