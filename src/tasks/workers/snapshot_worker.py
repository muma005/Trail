"""
Celery Beat worker for daily project snapshots.
Phase 3: Runs at midnight, calculates and stores progress for all active projects.
"""
import logging
from datetime import datetime

from src.config.settings import settings
from src.core.enrichment.progress_calculator import (
    calculate_simple_progress,
    calculate_weighted_progress,
    get_commit_stats,
)

logger = logging.getLogger(__name__)


def create_daily_snapshots() -> int:
    """
    Create progress snapshots for all active projects.
    Called by Celery Beat daily at 23:59.

    Returns:
        Number of projects snapped
    """
    from src.models.database.base import SessionLocal
    from src.models.database.models import Project, ProjectSnapshot
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    db = SessionLocal()
    try:
        projects = db.query(Project).filter(Project.status == "active").all()
        today = datetime.utcnow().date()
        count = 0

        for project in projects:
            try:
                # Calculate progress metrics
                simple = calculate_simple_progress(project.id)
                weighted = calculate_weighted_progress(project.id)
                commit_stats = get_commit_stats(project.id)

                # Build snapshot record
                snapshot_data = {
                    "project_id": project.id,
                    "snapshot_date": today,
                    "total_tasks": simple["total_tasks"],
                    "completed_tasks": simple["completed_tasks"],
                    "in_progress_tasks": simple["in_progress_tasks"],
                    "blocked_tasks": simple["blocked_tasks"],
                    "not_started_tasks": simple["not_started_tasks"],
                    "total_commits": commit_stats["total_commits"],
                    "lines_of_code_added": commit_stats["lines_added"],
                    "completion_percentage_simple": simple["completion_percentage"],
                    "completion_percentage_weighted": weighted["weighted_percentage"],
                    "metadata": {
                        "total_weight": weighted["total_weight"],
                        "completed_weight": weighted["completed_weight"],
                    },
                }

                # Upsert: ON CONFLICT (project_id, snapshot_date) DO UPDATE
                stmt = pg_insert(ProjectSnapshot).values(**snapshot_data)
                stmt = stmt.on_conflict_do_update(
                    constraint="project_snapshots_project_id_snapshot_date_key",
                    set_=dict(
                        total_tasks=stmt.excluded.total_tasks,
                        completed_tasks=stmt.excluded.completed_tasks,
                        in_progress_tasks=stmt.excluded.in_progress_tasks,
                        blocked_tasks=stmt.excluded.blocked_tasks,
                        not_started_tasks=stmt.excluded.not_started_tasks,
                        total_commits=stmt.excluded.total_commits,
                        lines_of_code_added=stmt.excluded.lines_of_code_added,
                        completion_percentage_simple=stmt.excluded.completion_percentage_simple,
                        completion_percentage_weighted=stmt.excluded.completion_percentage_weighted,
                        metadata=stmt.excluded.metadata,
                    ),
                )
                db.execute(stmt)
                count += 1
                logger.info(
                    f"Snapshot for {project.project_key}: "
                    f"{simple['completion_percentage']}% simple, "
                    f"{weighted['weighted_percentage']}% weighted"
                )
            except Exception as e:
                logger.error(f"Failed to snapshot project {project.project_key}: {e}")
                continue

        db.commit()
        logger.info(f"Created {count} daily snapshots")
        return count

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create daily snapshots: {e}")
        raise
    finally:
        db.close()
