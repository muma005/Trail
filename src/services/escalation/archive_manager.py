"""
Archive manager for the Escalation Engine.
Phase 4: Archives abandoned projects.
"""
import logging
from datetime import datetime

from src.models.database.base import SessionLocal
from src.models.database.models import Project

logger = logging.getLogger(__name__)


def archive_project(project: Project, days_idle: int) -> None:
    """
    Archive a project that has exceeded the archive threshold.
    Sets status='archived' — project is excluded from CLI/dashboard/sync.

    Args:
        project: Project ORM instance
        days_idle: Number of days since last activity
    """
    db = SessionLocal()
    try:
        # Reload to ensure we have the session-bound instance
        fresh = db.query(Project).filter(Project.id == project.id).first()
        if fresh:
            fresh.status = "archived"
            db.commit()
            logger.warning(
                f"Project {fresh.project_key} archived after {days_idle} days idle."
            )
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


def resurrect_project(project_key: str) -> bool:
    """
    Manually resurrect an archived project.

    Args:
        project_key: Project key string

    Returns:
        True if found and updated
    """
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.project_key == project_key).first()
        if project and project.status == "archived":
            project.status = "active"
            db.commit()
            logger.info(f"Project {project_key} resurrected")
            return True
        return False
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
