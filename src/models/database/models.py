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


class UserTimeOff(Base):
    """
    Phase 6.5: Tracks user holidays, PTO, and non-working days.
    """
    __tablename__ = "user_time_off"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    user_id = Column(UUID(as_uuid=False), default=generate_uuid)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(String(100), nullable=True)
    is_working = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<UserTimeOff({self.start_date} to {self.end_date})>"


class SwitchCost(Base):
    """
    Phase 6.5: Context switch penalties between project pairs.
    """
    __tablename__ = "switch_costs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    from_project_id = Column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )
    to_project_id = Column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )
    penalty_minutes = Column(Integer, default=10)
    sample_count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SwitchCost(from={self.from_project_id}, to={self.to_project_id}, penalty={self.penalty_minutes})>"


class PlannedTaskVerification(Base):
    """
    Phase 7: Tracks planned vs actual verification for each task.
    """
    __tablename__ = "planned_task_verification"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    daily_plan_id = Column(
        UUID(as_uuid=False),
        ForeignKey("daily_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    task_id = Column(
        UUID(as_uuid=False),
        ForeignKey("notion_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    expected_commit_sha = Column(String(40), nullable=True)
    expected_status_change = Column(String(50), nullable=True)
    actual_commit_sha = Column(String(40), nullable=True)
    actual_status = Column(String(50), nullable=True)
    verified_at = Column(DateTime, default=datetime.utcnow)
    was_completed = Column(Boolean, default=False)
    partial_progress_percentage = Column(Numeric(5, 2), nullable=True)
    remaining_estimate_minutes = Column(Integer, nullable=True)
    detection_method = Column(String(50), nullable=True)  # commits, status, subtasks, llm
    missed_reason = Column(Text, nullable=True)
    reassigned_to_plan_id = Column(
        UUID(as_uuid=False),
        ForeignKey("daily_plans.id"),
        nullable=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PlannedTaskVerification(task={self.task_id}, completed={self.was_completed}, progress={self.partial_progress_percentage})>"


class UntrackedSession(Base):
    """
    Phase 7.5: Detected work periods without corresponding commits.
    """
    __tablename__ = "untracked_sessions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_id = Column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    resolved = Column(Boolean, default=False)
    assigned_task_id = Column(
        UUID(as_uuid=False),
        ForeignKey("notion_tasks.id"),
        nullable=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<UntrackedSession(project={self.project_id}, duration={self.duration_minutes}min, resolved={self.resolved})>"


class TimeLog(Base):
    """
    Phase 7.5: Manual or auto-detected work sessions.
    """
    __tablename__ = "time_logs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    project_id = Column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    task_id = Column(
        UUID(as_uuid=False),
        ForeignKey("notion_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id = Column(UUID(as_uuid=False), default=generate_uuid)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    task_type = Column(String(50), default="manual")  # manual, untracked, prompted
    source = Column(String(50), default="manual")  # manual, prompted, auto-detected
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TimeLog(project={self.project_id}, duration={self.duration_minutes}min, source={self.source})>"


class LearnedPattern(Base):
    """
    Phase 8: Stores learned patterns for personalization.
    Pattern types: duration_multiplier, focus_peak_hour, empty_promise_multiplier.
    """
    __tablename__ = "learned_patterns"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    user_id = Column(UUID(as_uuid=False), default=generate_uuid)
    pattern_type = Column(String(50), nullable=False)
    # Using generic Text for context; actual JSON stored as string for SQLite compat
    context = Column(Text, nullable=True)
    value = Column(Numeric(10, 4), nullable=False)
    confidence = Column(Numeric(5, 4), default=0)
    sample_count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<LearnedPattern(type={self.pattern_type}, value={self.value}, samples={self.sample_count})>"


class Conversation(Base):
    """
    Phase 9: Stores conversation messages for the AI Brain.
    Includes vector embeddings for semantic memory retrieval.
    """
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    user_id = Column(UUID(as_uuid=False), default=generate_uuid)
    session_id = Column(UUID(as_uuid=False), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    # Stored as JSON string for cross-database compatibility
    tool_calls = Column(Text, nullable=True)
    tool_call_id = Column(String(100), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    # Vector embedding stored as byte array or text representation
    embedding_text = Column("embedding", Text, nullable=True)

    def __repr__(self):
        return f"<Conversation(session={self.session_id[:8]}, role={self.role}, content={self.content[:30]})>"


class UserAchievement(Base):
    """
    Phase 9.5: Stores user gamification data - points, streaks, badges.
    """
    __tablename__ = "user_achievements"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    user_id = Column(UUID(as_uuid=False), default=generate_uuid)
    achievement_type = Column(String(50), nullable=False)  # streak, badge, points
    achievement_name = Column(String(100), nullable=False)
    value = Column(Integer, default=0)
    earned_at = Column(DateTime, default=datetime.utcnow)
    # Stored as text for cross-database compatibility (column name is 'metadata' in DB)
    achievement_metadata = Column("metadata", Text, nullable=True)

    def __repr__(self):
        return f"<UserAchievement(type={self.achievement_type}, name={self.achievement_name}, value={self.value})>"


class BudgetTracking(Base):
    """
    Phase 9.5: Tracks LLM API spending for budget alerts.
    """
    __tablename__ = "budget_tracking"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    user_id = Column(UUID(as_uuid=False), default=generate_uuid)
    cost = Column(Numeric(10, 4), nullable=False)
    model = Column(String(100), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    description = Column(Text, nullable=True)

    def __repr__(self):
        return f"<BudgetTracking(cost={self.cost}, model={self.model})>"
