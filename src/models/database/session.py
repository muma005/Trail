"""
Database session management and initialization utilities.
Phase 0: Project CRUD, sync logging, user preferences
Phase 1: Commit storage, project lookup by key, last_synced_at updates
Phase 1.5: Scope filtering, orphan queries
Phase 2: Notion task storage, commit-task links
Phase 2.5: Dependencies, sub-tasks, task details
"""
import logging
from contextlib import contextmanager
from datetime import datetime, time
from typing import Any, Dict, List, Optional

from sqlalchemy import inspect, text

from src.models.database.base import Base, SessionLocal, engine
from src.utils.exceptions.base import DatabaseError

logger = logging.getLogger(__name__)


def init_db() -> None:
    """
    Create all tables that don't exist yet.
    Safe to call multiple times — won't overwrite existing data.
    Also runs Phase 1 migration (adds columns if missing).
    """
    try:
        Base.metadata.create_all(bind=engine)
        _run_phase1_migration()
    except Exception as e:
        raise DatabaseError(f"Failed to initialize database: {e}")


def _run_phase1_migration() -> None:
    """
    Add Phase 1 + 2 + 2.5 columns/tables that may not exist from Phase 0.
    Uses raw SQL with existence checks for idempotency.
    """
    migration_sql = """
    -- Add last_synced_at to projects if missing
    ALTER TABLE projects ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMP;

    -- Create commits table if not exists
    CREATE TABLE IF NOT EXISTS commits (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        commit_sha VARCHAR(40) UNIQUE NOT NULL,
        author_name VARCHAR(255),
        author_email VARCHAR(255),
        commit_date TIMESTAMP NOT NULL,
        message TEXT NOT NULL,
        files_changed JSONB,
        lines_added INTEGER DEFAULT 0,
        lines_deleted INTEGER DEFAULT 0,
        parsed_task_id VARCHAR(100),
        needs_classification BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT NOW()
    );

    -- Create project_scopes table if not exists
    CREATE TABLE IF NOT EXISTS project_scopes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        scope_type VARCHAR(20) NOT NULL CHECK (scope_type IN ('branch', 'path')),
        scope_value TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (project_id, scope_type, scope_value)
    );

    -- Phase 2: notion_tasks table
    CREATE TABLE IF NOT EXISTS notion_tasks (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        notion_page_id VARCHAR(100) UNIQUE NOT NULL,
        title TEXT,
        status VARCHAR(50),
        priority VARCHAR(20),
        mooscow VARCHAR(20),
        due_date DATE,
        completed_at TIMESTAMP,
        progress_percentage INT,
        estimated_minutes INT,
        actual_minutes INT,
        tags TEXT[],
        parent_task_id UUID REFERENCES notion_tasks(id),
        size_tag VARCHAR(10),
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );

    -- Phase 2: commit_task_links table
    CREATE TABLE IF NOT EXISTS commit_task_links (
        commit_id UUID NOT NULL REFERENCES commits(id) ON DELETE CASCADE,
        task_id UUID NOT NULL REFERENCES notion_tasks(id) ON DELETE CASCADE,
        confidence DECIMAL(3,2),
        is_suggestion BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (commit_id, task_id)
    );

    -- Phase 2.5: task_dependencies table
    CREATE TABLE IF NOT EXISTS task_dependencies (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        task_id UUID NOT NULL REFERENCES notion_tasks(id) ON DELETE CASCADE,
        depends_on_task_id UUID REFERENCES notion_tasks(id),
        depends_on_project_id UUID REFERENCES projects(id),
        dependency_type VARCHAR(50) DEFAULT 'blocks',
        created_at TIMESTAMP DEFAULT NOW(),
        CHECK (depends_on_task_id IS NOT NULL OR depends_on_project_id IS NOT NULL)
    );

    -- Phase 2.5: sub_tasks table
    CREATE TABLE IF NOT EXISTS sub_tasks (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        parent_task_id UUID NOT NULL REFERENCES notion_tasks(id) ON DELETE CASCADE,
        title TEXT,
        is_completed BOOLEAN DEFAULT FALSE,
        estimated_minutes INT,
        order_index INT,
        created_at TIMESTAMP DEFAULT NOW()
    );

    -- Add Phase 1.5 columns to commits if table already existed
    ALTER TABLE commits ADD COLUMN IF NOT EXISTS parsed_task_id VARCHAR(100);
    ALTER TABLE commits ADD COLUMN IF NOT EXISTS needs_classification BOOLEAN DEFAULT FALSE;

    -- Ensure size_tag exists
    ALTER TABLE notion_tasks ADD COLUMN IF NOT EXISTS size_tag VARCHAR(10);

    -- Indexes
    CREATE INDEX IF NOT EXISTS idx_commits_project_id ON commits(project_id);
    CREATE INDEX IF NOT EXISTS idx_commits_commit_date ON commits(commit_date);
    CREATE INDEX IF NOT EXISTS idx_projects_last_synced ON projects(last_synced_at);
    CREATE INDEX IF NOT EXISTS idx_project_scopes_project_id ON project_scopes(project_id);
    CREATE INDEX IF NOT EXISTS idx_commits_needs_classification ON commits(needs_classification) WHERE needs_classification = TRUE;
    CREATE INDEX IF NOT EXISTS idx_commits_parsed_task_id ON commits(parsed_task_id);
    CREATE INDEX IF NOT EXISTS idx_notion_tasks_project_id ON notion_tasks(project_id);
    CREATE INDEX IF NOT EXISTS idx_notion_tasks_parent_id ON notion_tasks(parent_task_id);
    CREATE INDEX IF NOT EXISTS idx_notion_tasks_status ON notion_tasks(status);
    CREATE INDEX IF NOT EXISTS idx_commit_task_links_task_id ON commit_task_links(task_id);
    CREATE INDEX IF NOT EXISTS idx_commit_task_links_commit_id ON commit_task_links(commit_id);
    CREATE INDEX IF NOT EXISTS idx_task_dependencies_task_id ON task_dependencies(task_id);
    CREATE INDEX IF NOT EXISTS idx_task_dependencies_depends_on_id ON task_dependencies(depends_on_task_id);
    CREATE INDEX IF NOT EXISTS idx_sub_tasks_parent_id ON sub_tasks(parent_task_id);
    CREATE INDEX IF NOT EXISTS idx_notion_tasks_size_tag ON notion_tasks(size_tag);

    -- Phase 3: project_snapshots table
    CREATE TABLE IF NOT EXISTS project_snapshots (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        snapshot_date DATE NOT NULL,
        total_tasks INT DEFAULT 0,
        completed_tasks INT DEFAULT 0,
        in_progress_tasks INT DEFAULT 0,
        blocked_tasks INT DEFAULT 0,
        not_started_tasks INT DEFAULT 0,
        total_commits INT DEFAULT 0,
        lines_of_code_added INT DEFAULT 0,
        completion_percentage_simple DECIMAL(5,2),
        completion_percentage_weighted DECIMAL(5,2),
        metadata JSONB,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (project_id, snapshot_date)
    );

    CREATE INDEX IF NOT EXISTS idx_project_snapshots_project_date ON project_snapshots(project_id, snapshot_date);

    -- Phase 4: Abandonment thresholds and status
    ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS warning_days INT DEFAULT 7;
    ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS critical_days INT DEFAULT 14;
    ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS archive_days INT DEFAULT 21;
    ALTER TABLE projects ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active';
    ALTER TABLE projects ADD COLUMN IF NOT EXISTS last_commit_date TIMESTAMP;
    ALTER TABLE projects ADD COLUMN IF NOT EXISTS last_warning_notified_at TIMESTAMP;
    ALTER TABLE projects ADD COLUMN IF NOT EXISTS last_critical_notified_at TIMESTAMP;

    CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
    CREATE INDEX IF NOT EXISTS idx_projects_last_commit_date ON projects(last_commit_date);

    -- Phase 5: notion_commands table
    CREATE TABLE IF NOT EXISTS notion_commands (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
        page_id VARCHAR(100) NOT NULL,
        block_id VARCHAR(100) NOT NULL,
        command TEXT NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        response_block_id VARCHAR(100),
        error_message TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        processed_at TIMESTAMP,
        UNIQUE (page_id, block_id)
    );

    CREATE INDEX IF NOT EXISTS idx_notion_commands_status ON notion_commands(status);
    CREATE INDEX IF NOT EXISTS idx_notion_commands_project ON notion_commands(project_id);
    CREATE INDEX IF NOT EXISTS idx_notion_commands_page ON notion_commands(page_id);

    -- Phase 6: Planner preferences and constraints
    ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS max_parallel_projects INT DEFAULT 2;
    ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS constant_project_id UUID REFERENCES projects(id);
    ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS deep_work_minutes INT DEFAULT 120;
    ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS lunch_start TIME;
    ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS lunch_end TIME;

    CREATE TABLE IF NOT EXISTS project_constraints (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id UUID UNIQUE NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        estimated_remaining_hours DECIMAL(10,2) NOT NULL DEFAULT 0,
        deadline DATE,
        priority VARCHAR(20) DEFAULT 'Medium',
        is_constant BOOLEAN DEFAULT FALSE,
        updated_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS daily_plans (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
        plan_date DATE NOT NULL,
        allocated_minutes INT NOT NULL,
        tasks_planned JSONB,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (project_id, plan_date)
    );

    CREATE INDEX IF NOT EXISTS idx_project_constraints_project_id ON project_constraints(project_id);
    CREATE INDEX IF NOT EXISTS idx_project_constraints_deadline ON project_constraints(deadline);
    CREATE INDEX IF NOT EXISTS idx_daily_plans_date ON daily_plans(plan_date);
    """

    db = SessionLocal()
    try:
        for statement in migration_sql.strip().split(";"):
            statement = statement.strip()
            if statement:
                db.execute(text(statement))
        db.commit()
    except Exception:
        db.rollback()
        # Migration may fail if objects already exist — that's OK
        pass
    finally:
        db.close()


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    return inspect(engine).has_table(table_name)


# -------------------------------------------------------------------------
# Phase 0: Project operations
# -------------------------------------------------------------------------

def get_all_projects() -> List:
    """Fetch all projects from the database, ordered by creation date."""
    from src.models.database.models import Project

    db = SessionLocal()
    try:
        return db.query(Project).order_by(Project.created_at.desc()).all()
    except Exception as e:
        raise DatabaseError(f"Failed to fetch projects: {e}")
    finally:
        db.close()


def get_project_by_key(project_key: str) -> Optional[Dict[str, Any]]:
    """
    Look up a project by its unique key.
    Returns project dict or None if not found.
    """
    from src.models.database.models import Project

    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.project_key == project_key).first()
        if not project:
            return None
        return {
            "id": project.id,
            "project_key": project.project_key,
            "name": project.name,
            "github_repo_url": project.github_repo_url,
            "notion_database_id": project.notion_database_id,
            "last_synced_at": project.last_synced_at,
            "created_at": project.created_at,
        }
    except Exception as e:
        raise DatabaseError(f"Failed to fetch project '{project_key}': {e}")
    finally:
        db.close()


def create_project(project_key: str, name: str, github_repo_url: str, notion_database_id: str) -> str:
    """
    Insert a new project into the database.
    Returns the project ID on success.
    Raises DuplicateProjectError if unique constraint is violated.
    """
    from psycopg2.errors import UniqueViolation
    from sqlalchemy.exc import IntegrityError

    from src.models.database.models import Project
    from src.utils.exceptions.base import DuplicateProjectError

    db = SessionLocal()
    try:
        project = Project(
            project_key=project_key,
            name=name,
            github_repo_url=github_repo_url,
            notion_database_id=notion_database_id,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project.id
    except IntegrityError as e:
        db.rollback()
        # Determine which constraint was violated
        if isinstance(e.orig, UniqueViolation):
            diag = e.orig.diag
            if "github_repo_url" in (diag.constraint_name or ""):
                raise DuplicateProjectError(
                    f"A project with GitHub URL '{github_repo_url}' already exists."
                )
            elif "notion_database_id" in (diag.constraint_name or ""):
                raise DuplicateProjectError(
                    f"A project with Notion database '{notion_database_id}' already exists."
                )
            elif "project_key" in (diag.constraint_name or ""):
                raise DuplicateProjectError(
                    f"A project with key '{project_key}' already exists."
                )
            else:
                raise DuplicateProjectError(
                    "A project with one of these values already exists."
                )
        raise DatabaseError(f"Database error: {e}")
    except Exception as e:
        db.rollback()
        raise DatabaseError(f"Failed to create project: {e}")
    finally:
        db.close()


def log_sync_event(project_id: str, sync_type: str, status: str, message: str) -> None:
    """Record a sync event in the sync_logs table."""
    from src.models.database.models import SyncLog

    db = SessionLocal()
    try:
        log = SyncLog(
            project_id=project_id,
            sync_type=sync_type,
            status=status,
            message=message,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        db.rollback()
        raise DatabaseError(f"Failed to log sync event: {e}")
    finally:
        db.close()


def upsert_user_preferences(work_start: str, work_end: str, timezone: str) -> None:
    """
    Insert or update user preferences.
    Since there's only one user for now, this creates or updates the single row.
    """
    from datetime import datetime

    from sqlalchemy.dialects.postgresql import insert

    from src.models.database.models import UserPreference

    db = SessionLocal()
    try:
        # Parse time strings (HH:MM format)
        start_parts = work_start.split(":")
        end_parts = work_end.split(":")
        start_time = time(int(start_parts[0]), int(start_parts[1]))
        end_time = time(int(end_parts[0]), int(end_parts[1]))

        stmt = insert(UserPreference).values(
            work_start=start_time,
            work_end=end_time,
            timezone=timezone,
        )
        # On conflict, update the values
        stmt = stmt.on_conflict_do_update(
            constraint="user_preferences_pkey",
            set_=dict(
                work_start=stmt.excluded.work_start,
                work_end=stmt.excluded.work_end,
                timezone=stmt.excluded.timezone,
                updated_at=datetime.utcnow(),
            ),
        )
        db.execute(stmt)
        db.commit()
    except Exception as e:
        db.rollback()
        raise DatabaseError(f"Failed to save user preferences: {e}")
    finally:
        db.close()


# -------------------------------------------------------------------------
# Phase 1: Commit operations
# -------------------------------------------------------------------------

def store_commits(project_id: str, commits: List[Dict[str, Any]]) -> int:
    """
    Bulk insert new commits into the database.
    Skips commits that already exist (by commit_sha).
    Returns the number of new commits inserted.

    Phase 1.5: Also stores parsed_task_id and needs_classification.
    """
    from psycopg2.extras import execute_values

    if not commits:
        return 0

    db = SessionLocal()
    try:
        # Use raw connection for bulk insert
        raw_conn = db.connection()
        cursor = raw_conn.cursor()

        insert_count = 0
        for commit in commits:
            try:
                # Check if commit already exists (by sha)
                cursor.execute("SELECT 1 FROM commits WHERE commit_sha = %s", (commit["sha"],))
                if cursor.fetchone():
                    continue  # Skip duplicate

                # Phase 1.5: extract task classification fields
                parsed_task_id = commit.get("parsed_task_id")
                needs_classification = commit.get("needs_classification", 0)

                # Insert new commit
                execute_values(
                    cursor,
                    """
                    INSERT INTO commits (
                        project_id, commit_sha, author_name, author_email,
                        commit_date, message, files_changed, lines_added, lines_deleted,
                        parsed_task_id, needs_classification
                    ) VALUES %s
                    """,
                    [(
                        project_id,
                        commit["sha"],
                        commit.get("author_name"),
                        commit.get("author_email"),
                        commit["date"],
                        commit["message"],
                        commit.get("files_changed"),
                        commit.get("lines_added", 0),
                        commit.get("lines_deleted", 0),
                        parsed_task_id,
                        needs_classification,
                    )],
                    template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                )
                insert_count += 1
            except Exception as e:
                # Log individual commit failures but continue
                pass

        raw_conn.commit()
        return insert_count

    except Exception as e:
        db.rollback()
        raise DatabaseError(f"Failed to store commits: {e}")
    finally:
        db.close()


def update_last_synced(project_id: str, last_commit_date: Optional[datetime]) -> None:
    """
    Update the last_synced_at timestamp for a project.
    Uses the latest commit date if provided, otherwise current time.
    """
    from datetime import datetime as dt

    from src.models.database.models import Project

    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.last_synced_at = last_commit_date or dt.utcnow()
            db.commit()
    except Exception as e:
        db.rollback()
        raise DatabaseError(f"Failed to update last_synced_at: {e}")
    finally:
        db.close()


def get_commit_count(project_id: str) -> int:
    """Get total number of commits stored for a project."""
    from src.models.database.models import Commit

    db = SessionLocal()
    try:
        return db.query(Commit).filter(Commit.project_id == project_id).count()
    except Exception as e:
        raise DatabaseError(f"Failed to count commits: {e}")
    finally:
        db.close()


def get_existing_commit_shas(project_id: str) -> set:
    """Get set of existing commit SHAs for a project (for duplicate checking)."""
    from src.models.database.models import Commit

    db = SessionLocal()
    try:
        results = db.query(Commit.commit_sha).filter(Commit.project_id == project_id).all()
        return {row[0] for row in results}
    except Exception as e:
        raise DatabaseError(f"Failed to fetch existing commits: {e}")
    finally:
        db.close()


# -------------------------------------------------------------------------
# Phase 1.5: Scope and orphan operations
# -------------------------------------------------------------------------

def save_project_scopes(project_id: str, branches: List[str], paths: List[str]) -> None:
    """
    Save branch and path scopes for a project.
    Replaces any existing scopes for this project.

    Args:
        project_id: Project UUID
        branches: List of branch names to track
        paths: List of path prefixes to track
    """
    from src.models.database.models import ProjectScope

    db = SessionLocal()
    try:
        # Delete existing scopes for this project
        db.query(ProjectScope).filter(ProjectScope.project_id == project_id).delete()

        # Insert new scopes
        for branch in branches:
            scope = ProjectScope(project_id=project_id, scope_type="branch", scope_value=branch)
            db.add(scope)
        for path in paths:
            scope = ProjectScope(project_id=project_id, scope_type="path", scope_value=path)
            db.add(scope)

        db.commit()
    except Exception as e:
        db.rollback()
        raise DatabaseError(f"Failed to save project scopes: {e}")
    finally:
        db.close()


def get_project_scopes(project_id: str) -> Dict[str, List[str]]:
    """
    Get all scopes for a project.

    Returns:
        Dict with 'branches' and 'paths' keys, each containing a list of values.
        Empty lists mean no filtering (accept all).
    """
    from src.models.database.models import ProjectScope

    db = SessionLocal()
    try:
        scopes = db.query(ProjectScope).filter(ProjectScope.project_id == project_id).all()
        branches = [s.scope_value for s in scopes if s.scope_type == "branch"]
        paths = [s.scope_value for s in scopes if s.scope_type == "path"]
        return {"branches": branches, "paths": paths}
    except Exception as e:
        raise DatabaseError(f"Failed to fetch project scopes: {e}")
    finally:
        db.close()


def get_orphan_commits(project_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get commits that need classification (no parsed task ID).
    """
    from src.models.database.models import Commit, Project

    db = SessionLocal()
    try:
        query = (
            db.query(Commit, Project.name, Project.project_key)
            .join(Project, Commit.project_id == Project.id)
            .filter(Commit.needs_classification == 1)
            .order_by(Commit.commit_date.desc())
        )
        if project_key:
            query = query.filter(Project.project_key == project_key)
        results = query.all()
        return [
            {
                "sha": commit.commit_sha,
                "date": commit.commit_date,
                "message": commit.message[:60] + ("..." if len(commit.message) > 60 else ""),
                "project_name": proj_name,
                "project_key": proj_key,
            }
            for commit, proj_name, proj_key in results
        ]
    except Exception as e:
        raise DatabaseError(f"Failed to fetch orphan commits: {e}")
    finally:
        db.close()


# -------------------------------------------------------------------------
# Phase 2: Notion task storage & linking
# -------------------------------------------------------------------------

def store_notion_tasks(project_id: str, tasks: List[Dict[str, Any]]) -> int:
    """
    Bulk upsert Notion tasks into the database.
    Uses ON CONFLICT (notion_page_id) DO UPDATE for idempotency.
    Returns the number of tasks inserted or updated.
    """
    from psycopg2.extras import execute_values

    if not tasks:
        return 0

    db = SessionLocal()
    try:
        raw_conn = db.connection()
        cursor = raw_conn.cursor()

        upsert_count = 0
        for task in tasks:
            try:
                # Upsert using execute_values
                execute_values(
                    cursor,
                    """
                    INSERT INTO notion_tasks (
                        project_id, notion_page_id, title, status, priority,
                        mooscow, due_date, completed_at, progress_percentage,
                        estimated_minutes, actual_minutes, tags
                    ) VALUES %s
                    ON CONFLICT (notion_page_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        status = EXCLUDED.status,
                        priority = EXCLUDED.priority,
                        mooscow = EXCLUDED.mooscow,
                        due_date = EXCLUDED.due_date,
                        completed_at = EXCLUDED.completed_at,
                        progress_percentage = EXCLUDED.progress_percentage,
                        estimated_minutes = EXCLUDED.estimated_minutes,
                        actual_minutes = EXCLUDED.actual_minutes,
                        tags = EXCLUDED.tags,
                        updated_at = NOW()
                    """,
                    [(
                        project_id,
                        task["notion_page_id"],
                        task.get("title"),
                        task.get("status"),
                        task.get("priority"),
                        task.get("mooscow"),
                        task.get("due_date"),
                        task.get("completed_at"),
                        task.get("progress_percentage"),
                        task.get("estimated_minutes"),
                        task.get("actual_minutes"),
                        task.get("tags"),
                    )],
                    template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                )
                upsert_count += 1
            except Exception as e:
                logger.warning(f"Failed to upsert task {task.get('notion_page_id', 'unknown')}: {e}")

        raw_conn.commit()
        return upsert_count

    except Exception as e:
        db.rollback()
        raise DatabaseError(f"Failed to store Notion tasks: {e}")
    finally:
        db.close()


def get_notion_tasks(project_id: str) -> List[Dict[str, Any]]:
    """Fetch all Notion tasks for a project."""
    from src.models.database.models import NotionTask

    db = SessionLocal()
    try:
        tasks = db.query(NotionTask).filter(NotionTask.project_id == project_id).all()
        return [
            {
                "id": t.id,
                "notion_page_id": t.notion_page_id,
                "title": t.title,
                "status": t.status,
                "priority": t.priority,
                "due_date": t.due_date,
                "estimated_minutes": t.estimated_minutes,
                "size_tag": t.size_tag,
            }
            for t in tasks
        ]
    except Exception as e:
        raise DatabaseError(f"Failed to fetch Notion tasks: {e}")
    finally:
        db.close()


def create_commit_link(commit_id: str, task_id: str, confidence: float, is_suggestion: bool = False) -> None:
    """
    Create or update a commit-task link.
    Uses ON CONFLICT DO UPDATE to avoid duplicates.
    """
    from src.models.database.models import CommitTaskLink

    db = SessionLocal()
    try:
        existing = db.query(CommitTaskLink).filter_by(commit_id=commit_id, task_id=task_id).first()
        if existing:
            # Only upgrade if new confidence is higher
            if float(confidence) > float(existing.confidence or 0):
                existing.confidence = confidence
                existing.is_suggestion = is_suggestion
        else:
            link = CommitTaskLink(
                commit_id=commit_id,
                task_id=task_id,
                confidence=confidence,
                is_suggestion=is_suggestion,
            )
            db.add(link)
        db.commit()
    except Exception as e:
        db.rollback()
        raise DatabaseError(f"Failed to create commit-task link: {e}")
    finally:
        db.close()


def get_link_suggestions(project_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get pending commit-task link suggestions (confidence < 1.0).
    Optionally filtered by project key.
    """
    from src.models.database.models import Commit, CommitTaskLink, NotionTask, Project

    db = SessionLocal()
    try:
        query = (
            db.query(Commit, CommitTaskLink, NotionTask, Project.project_key)
            .join(CommitTaskLink, Commit.id == CommitTaskLink.commit_id)
            .join(NotionTask, CommitTaskLink.task_id == NotionTask.id)
            .join(Project, Commit.project_id == Project.id)
            .filter(CommitTaskLink.confidence < 1.0)
            .order_by(CommitTaskLink.confidence.desc())
        )

        if project_key:
            query = query.filter(Project.project_key == project_key)

        results = query.all()
        return [
            {
                "commit_sha": c.commit_sha,
                "commit_message": c.message[:60],
                "task_title": t.title or "Untitled",
                "task_id": t.notion_page_id,
                "confidence": float(link.confidence),
                "project_key": pk,
            }
            for c, link, t, pk in results
        ]
    except Exception as e:
        raise DatabaseError(f"Failed to fetch link suggestions: {e}")
    finally:
        db.close()


def accept_suggestion(commit_sha: str, task_notion_page_id: str) -> bool:
    """
    Accept a link suggestion: set confidence to 1.0, is_suggestion=False.
    Returns True if updated, False if not found.
    """
    from src.models.database.models import Commit, CommitTaskLink, NotionTask

    db = SessionLocal()
    try:
        commit = db.query(Commit).filter(Commit.commit_sha == commit_sha).first()
        task = db.query(NotionTask).filter(NotionTask.notion_page_id == task_notion_page_id).first()

        if not commit or not task:
            return False

        link = db.query(CommitTaskLink).filter_by(commit_id=commit.id, task_id=task.id).first()
        if link:
            link.confidence = 1.0
            link.is_suggestion = False
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        raise DatabaseError(f"Failed to accept suggestion: {e}")
    finally:
        db.close()


def ignore_suggestion(commit_sha: str, task_notion_page_id: str) -> bool:
    """Delete a link suggestion (user rejected it)."""
    from src.models.database.models import Commit, CommitTaskLink, NotionTask

    db = SessionLocal()
    try:
        commit = db.query(Commit).filter(Commit.commit_sha == commit_sha).first()
        task = db.query(NotionTask).filter(NotionTask.notion_page_id == task_notion_page_id).first()

        if not commit or not task:
            return False

        link = db.query(CommitTaskLink).filter_by(commit_id=commit.id, task_id=task.id).first()
        if link:
            db.delete(link)
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        raise DatabaseError(f"Failed to ignore suggestion: {e}")
    finally:
        db.close()


# -------------------------------------------------------------------------
# Phase 2.5: Dependencies, sub-tasks, task details
# -------------------------------------------------------------------------

def store_dependencies(dependencies: List[Dict[str, Any]]) -> int:
    """
    Bulk insert task dependencies. Skips duplicates.
    Returns number of dependencies stored.
    """
    from src.models.database.models import TaskDependency

    db = SessionLocal()
    try:
        count = 0
        for dep in dependencies:
            existing = db.query(TaskDependency).filter_by(
                task_id=dep["task_id"],
                depends_on_task_id=dep.get("depends_on_task_id"),
                dependency_type=dep.get("dependency_type", "blocks"),
            ).first()
            if not existing:
                task_dep = TaskDependency(
                    task_id=dep["task_id"],
                    depends_on_task_id=dep.get("depends_on_task_id"),
                    depends_on_project_id=dep.get("depends_on_project_id"),
                    dependency_type=dep.get("dependency_type", "blocks"),
                )
                db.add(task_dep)
                count += 1
        db.commit()
        return count
    except Exception as e:
        db.rollback()
        raise DatabaseError(f"Failed to store dependencies: {e}")
    finally:
        db.close()


def store_subtasks(parent_task_id: str, subtasks: List[Dict[str, Any]]) -> int:
    """
    Bulk insert sub-tasks for a parent task.
    Replaces existing sub-tasks for idempotency.
    Returns number of sub-tasks stored.
    """
    from src.models.database.models import SubTask

    db = SessionLocal()
    try:
        # Delete existing sub-tasks for this parent
        db.query(SubTask).filter(SubTask.parent_task_id == parent_task_id).delete()

        for i, sub in enumerate(subtasks):
            st = SubTask(
                parent_task_id=parent_task_id,
                title=sub.get("title"),
                is_completed=sub.get("is_completed", False),
                estimated_minutes=sub.get("estimated_minutes"),
                order_index=sub.get("order_index", i),
            )
            db.add(st)

        db.commit()
        return len(subtasks)
    except Exception as e:
        db.rollback()
        raise DatabaseError(f"Failed to store sub-tasks: {e}")
    finally:
        db.close()


def update_task_size_tags(task_sizes: Dict[str, str]) -> int:
    """
    Bulk update size_tag for tasks.
    task_sizes: {task_id: size_tag}
    Returns number of tasks updated.
    """
    from src.models.database.models import NotionTask

    db = SessionLocal()
    try:
        count = 0
        for task_id, size_tag in task_sizes.items():
            task = db.query(NotionTask).filter(NotionTask.id == task_id).first()
            if task and task.size_tag != size_tag:
                task.size_tag = size_tag
                count += 1
        db.commit()
        return count
    except Exception as e:
        db.rollback()
        raise DatabaseError(f"Failed to update size tags: {e}")
    finally:
        db.close()


def get_task_details(task_id_or_page_id: str) -> Optional[Dict[str, Any]]:
    """
    Get full task details including sub-tasks and dependencies.
    Accepts either local task UUID or Notion page ID.
    """
    from src.models.database.models import NotionTask, SubTask, TaskDependency

    db = SessionLocal()
    try:
        task = (
            db.query(NotionTask)
            .filter(
                (NotionTask.id == task_id_or_page_id) |
                (NotionTask.notion_page_id == task_id_or_page_id)
            )
            .first()
        )
        if not task:
            return None

        subtasks = db.query(SubTask).filter(
            SubTask.parent_task_id == task.id
        ).order_by(SubTask.order_index).all()

        deps = db.query(TaskDependency).filter(
            TaskDependency.task_id == task.id
        ).all()

        return {
            "id": task.id,
            "notion_page_id": task.notion_page_id,
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
            "due_date": task.due_date,
            "progress_percentage": task.progress_percentage,
            "estimated_minutes": task.estimated_minutes,
            "size_tag": task.size_tag,
            "sub_tasks": [
                {"title": st.title, "is_completed": st.is_completed}
                for st in subtasks
            ],
            "dependencies": [
                {"depends_on": d.depends_on_task_id, "type": d.dependency_type}
                for d in deps
            ],
        }
    except Exception as e:
        raise DatabaseError(f"Failed to fetch task details: {e}")
    finally:
        db.close()
