"""
Progress calculation functions.
Phase 3: Simple and weighted progress for projects based on tasks and commits.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Priority weights for weighted progress calculation
PRIORITY_WEIGHTS = {
    "Critical": 3.0,
    "High": 2.0,
    "Medium": 1.0,
    "Low": 0.5,
}

# Status mappings
STATUS_DONE = {"Done", "Completed", "Complete"}
STATUS_IN_PROGRESS = {"In Progress", "In progress", "Started"}
STATUS_BLOCKED = {"Blocked", "Waiting"}


def calculate_simple_progress(project_id: str) -> Dict[str, Any]:
    """
    Calculate simple progress: completed tasks / total tasks.

    Returns:
        Dict with total_tasks, completed_tasks, in_progress, blocked,
        not_started, completion_percentage.
    """
    from src.models.database.base import SessionLocal
    from src.models.database.models import NotionTask

    db = SessionLocal()
    try:
        tasks = db.query(NotionTask).filter(NotionTask.project_id == project_id).all()

        total = len(tasks)
        completed = sum(1 for t in tasks if t.status in STATUS_DONE)
        in_progress = sum(1 for t in tasks if t.status in STATUS_IN_PROGRESS)
        blocked = sum(1 for t in tasks if t.status in STATUS_BLOCKED)
        not_started = total - completed - in_progress - blocked

        percentage = round((completed / total * 100), 2) if total > 0 else 0.0

        return {
            "total_tasks": total,
            "completed_tasks": completed,
            "in_progress_tasks": in_progress,
            "blocked_tasks": blocked,
            "not_started_tasks": not_started,
            "completion_percentage": percentage,
        }
    except Exception as e:
        logger.error(f"Failed to calculate simple progress: {e}")
        return {"total_tasks": 0, "completed_tasks": 0, "completion_percentage": 0.0}
    finally:
        db.close()


def calculate_weighted_progress(project_id: str) -> Dict[str, Any]:
    """
    Calculate weighted progress based on task priorities.
    Critical=3, High=2, Medium=1, Low=0.5.

    Returns:
        Dict with total_weight, completed_weight, weighted_percentage.
    """
    from src.models.database.base import SessionLocal
    from src.models.database.models import NotionTask

    db = SessionLocal()
    try:
        tasks = db.query(NotionTask).filter(NotionTask.project_id == project_id).all()

        total_weight = 0.0
        completed_weight = 0.0

        for task in tasks:
            weight = PRIORITY_WEIGHTS.get(task.priority, 1.0)  # Default to Medium
            total_weight += weight
            if task.status in STATUS_DONE:
                completed_weight += weight

        percentage = round((completed_weight / total_weight * 100), 2) if total_weight > 0 else 0.0

        return {
            "total_weight": round(total_weight, 1),
            "completed_weight": round(completed_weight, 1),
            "weighted_percentage": percentage,
        }
    except Exception as e:
        logger.error(f"Failed to calculate weighted progress: {e}")
        return {"total_weight": 0.0, "completed_weight": 0.0, "weighted_percentage": 0.0}
    finally:
        db.close()


def get_commit_stats(project_id: str, since_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Get commit statistics for a project.

    Args:
        project_id: Project UUID
        since_date: Optional ISO date string to filter commits after

    Returns:
        Dict with total_commits, lines_added, lines_deleted, recent_commits (last 10).
    """
    from datetime import datetime

    from sqlalchemy import func

    from src.models.database.base import SessionLocal
    from src.models.database.models import Commit

    db = SessionLocal()
    try:
        query = db.query(Commit).filter(Commit.project_id == project_id)

        if since_date:
            try:
                since_dt = datetime.fromisoformat(since_date)
                query = query.filter(Commit.commit_date >= since_dt)
            except (ValueError, TypeError):
                pass

        total_commits = query.count()
        lines_added = query.with_entities(func.coalesce(func.sum(Commit.lines_added), 0)).scalar()
        lines_deleted = query.with_entities(func.coalesce(func.sum(Commit.lines_deleted), 0)).scalar()

        # Get last 10 commits for display
        recent = query.order_by(Commit.commit_date.desc()).limit(10).all()
        recent_commits = [
            {
                "sha": c.commit_sha[:8],
                "message": c.message[:50],
                "date": c.commit_date.strftime("%Y-%m-%d") if c.commit_date else "N/A",
                "author": c.author_name,
            }
            for c in recent
        ]

        return {
            "total_commits": total_commits,
            "lines_added": lines_added,
            "lines_deleted": lines_deleted,
            "recent_commits": recent_commits,
        }
    except Exception as e:
        logger.error(f"Failed to get commit stats: {e}")
        return {"total_commits": 0, "lines_added": 0, "lines_deleted": 0, "recent_commits": []}
    finally:
        db.close()
