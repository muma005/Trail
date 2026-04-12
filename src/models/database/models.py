"""
SQLAlchemy ORM models for Trail Phase 0.
Defines the database schema in Python code.
"""
import uuid
from datetime import datetime, time

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import UUID

from src.models.database.base import Base


def generate_uuid():
    """Generate a random UUID string for primary keys."""
    return str(uuid.uuid4())


class Project(Base):
    """
    Core identity: one project = one GitHub repo + one Notion database.
    Both github_repo_url and notion_database_id have UNIQUE constraints
    to prevent cross-pollution.
    """
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_key = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    github_repo_url = Column(Text, unique=True, nullable=False)
    notion_database_id = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Project(key={self.project_key}, name={self.name})>"


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
