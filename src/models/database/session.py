"""
Database session management and initialization utilities.
Provides functions to create tables and manage sessions.
"""
from contextlib import contextmanager
from typing import List

from sqlalchemy import inspect

from src.models.database.base import Base, SessionLocal, engine
from src.utils.exceptions.base import DatabaseError


def init_db() -> None:
    """
    Create all tables that don't exist yet.
    Safe to call multiple times — won't overwrite existing data.
    """
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        raise DatabaseError(f"Failed to initialize database: {e}")


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    return inspect(engine).has_table(table_name)


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
