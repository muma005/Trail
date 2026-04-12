"""
Database session management and initialization utilities.
Phase 0: Project CRUD, sync logging, user preferences
Phase 1: Commit storage, project lookup by key, last_synced_at updates
"""
from contextlib import contextmanager
from datetime import datetime, time
from typing import Any, Dict, List, Optional

from sqlalchemy import inspect, text

from src.models.database.base import Base, SessionLocal, engine
from src.utils.exceptions.base import DatabaseError


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
    Add Phase 1 + 1.5 columns/tables that may not exist from Phase 0.
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

    -- Add Phase 1.5 columns to commits if table already existed
    ALTER TABLE commits ADD COLUMN IF NOT EXISTS parsed_task_id VARCHAR(100);
    ALTER TABLE commits ADD COLUMN IF NOT EXISTS needs_classification BOOLEAN DEFAULT FALSE;

    -- Indexes
    CREATE INDEX IF NOT EXISTS idx_commits_project_id ON commits(project_id);
    CREATE INDEX IF NOT EXISTS idx_commits_commit_date ON commits(commit_date);
    CREATE INDEX IF NOT EXISTS idx_projects_last_synced ON projects(last_synced_at);
    CREATE INDEX IF NOT EXISTS idx_project_scopes_project_id ON project_scopes(project_id);
    CREATE INDEX IF NOT EXISTS idx_commits_needs_classification ON commits(needs_classification) WHERE needs_classification = TRUE;
    CREATE INDEX IF NOT EXISTS idx_commits_parsed_task_id ON commits(parsed_task_id);
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

    Args:
        project_key: If provided, filter to this project only.

    Returns:
        List of dicts with commit SHA, date, message (truncated), and project name.
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
