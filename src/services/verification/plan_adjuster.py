"""
Plan adjuster for untracked work.
Phase 7.5: Updates project remaining hours and task estimates after logging untracked time.
"""
import logging
from decimal import Decimal
from typing import Optional

from src.models.database.base import SessionLocal
from src.models.database.models import (
    NotionTask,
    ProjectConstraint,
    TimeLog,
    UntrackedSession,
)

logger = logging.getLogger(__name__)


def log_time_entry(
    project_id: str,
    start_time,
    end_time,
    duration_minutes: int,
    source: str = "prompted",
    task_id: Optional[str] = None,
    notes: str = "Auto-detected untracked work",
) -> Optional[str]:
    """
    Create a time log entry for an untracked work session.

    Args:
        project_id: Project UUID
        start_time: Session start time
        end_time: Session end time
        duration_minutes: Session duration
        source: Source of the time log ('prompted', 'manual', 'auto-detected')
        task_id: Optional task UUID
        notes: Optional notes

    Returns:
        Time log ID, or None on failure.
    """
    db = SessionLocal()
    try:
        time_log = TimeLog(
            project_id=project_id,
            task_id=task_id,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            task_type="untracked",
            source=source,
            notes=notes,
        )
        db.add(time_log)
        db.commit()
        db.refresh(time_log)
        logger.info(
            f"Logged {duration_minutes} min for project {project_id[:8]} "
            f"(source={source})"
        )
        return time_log.id
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to log time entry: {e}")
        return None
    finally:
        db.close()


def adjust_remaining_hours(project_id: str, logged_minutes: int) -> bool:
    """
    Decrease a project's estimated remaining hours after logging untracked time.
    Ensures remaining hours don't go below zero.

    Args:
        project_id: Project UUID
        logged_minutes: Minutes of work that was actually done

    Returns:
        True if adjustment was made
    """
    db = SessionLocal()
    try:
        constraint = (
            db.query(ProjectConstraint)
            .filter(ProjectConstraint.project_id == project_id)
            .first()
        )

        if not constraint:
            # Create constraint if it doesn't exist
            constraint = ProjectConstraint(
                project_id=project_id,
                estimated_remaining_hours=0,
            )
            db.add(constraint)
            db.commit()
            return False

        logged_hours = Decimal(str(logged_minutes)) / Decimal("60")
        current_hours = constraint.estimated_remaining_hours or Decimal("0")
        new_hours = max(Decimal("0"), current_hours - logged_hours)

        if new_hours != current_hours:
            constraint.estimated_remaining_hours = new_hours
            db.commit()
            logger.info(
                f"Adjusted project {project_id[:8]} remaining hours: "
                f"{current_hours}h → {new_hours}h (logged {logged_minutes} min)"
            )
            return True

        return False

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to adjust remaining hours: {e}")
        return False
    finally:
        db.close()


def resolve_session(session_id: str, action: str, project_key: Optional[str] = None) -> bool:
    """
    Resolve an untracked session based on user response.

    Args:
        session_id: UntrackedSession UUID
        action: 'assign' or 'ignore'
        project_key: Project key if assigning

    Returns:
        True if resolved successfully
    """
    from datetime import datetime

    db = SessionLocal()
    try:
        session = db.query(UntrackedSession).filter(UntrackedSession.id == session_id).first()
        if not session:
            logger.warning(f"Untracked session {session_id} not found")
            return False

        if action == "ignore":
            session.resolved = True
            db.commit()
            logger.info(f"Session {session_id} marked as ignored")
            return True

        elif action == "assign" and project_key:
            # Find project by key
            from src.models.database.models import Project
            project = (
                db.query(Project)
                .filter(Project.project_key == project_key.upper())
                .first()
            )
            if not project:
                logger.warning(f"Project {project_key} not found for assignment")
                return False

            # Log time entry
            time_log = TimeLog(
                project_id=str(project.id),
                task_id=session.assigned_task_id,
                start_time=session.start_time,
                end_time=session.end_time,
                duration_minutes=session.duration_minutes,
                task_type="untracked",
                source="prompted",
                notes="Auto-detected untracked work (user-assigned)",
            )
            db.add(time_log)

            # Mark session resolved
            session.resolved = True

            # Adjust remaining hours
            logged_minutes = session.duration_minutes
            current_hours = Decimal(str(
                db.query(ProjectConstraint)
                .filter(ProjectConstraint.project_id == project.id)
                .first()
                .estimated_remaining_hours or 0
            ))
            logged_hours = Decimal(str(logged_minutes)) / Decimal("60")
            new_hours = max(Decimal("0"), current_hours - logged_hours)

            constraint = (
                db.query(ProjectConstraint)
                .filter(ProjectConstraint.project_id == project.id)
                .first()
            )
            if constraint:
                constraint.estimated_remaining_hours = new_hours
            else:
                constraint = ProjectConstraint(
                    project_id=project.id,
                    estimated_remaining_hours=0,
                )
                db.add(constraint)

            db.commit()
            logger.info(
                f"Session {session_id} assigned to {project_key} "
                f"({logged_minutes} min logged)"
            )
            return True

        return False

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to resolve session {session_id}: {e}")
        return False
    finally:
        db.close()
