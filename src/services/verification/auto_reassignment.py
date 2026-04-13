"""
Auto-reassignment engine.
Phase 7: Estimates remaining work, updates backlog, reschedules tasks, sends proposals.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from src.models.database.base import SessionLocal
from src.models.database.models import (
    DailyPlan,
    NotionTask,
    PlannedTaskVerification,
    ProjectConstraint,
)
from src.services.work_planner.scheduler import allocate_hours

logger = logging.getLogger(__name__)


def estimate_remaining(original_estimate_minutes: int, partial_percentage: float) -> int:
    """
    Estimate remaining minutes for a partially completed task.

    Args:
        original_estimate_minutes: Original task estimate
        partial_percentage: Progress percentage (0-100)

    Returns:
        Remaining minutes
    """
    if partial_percentage >= 100:
        return 0
    if partial_percentage <= 0:
        return original_estimate_minutes
    remaining = original_estimate_minutes * (1 - partial_percentage / 100)
    return max(0, round(remaining))


def run_reassignment(
    target_date: Optional[date] = None,
    dry_run: bool = True,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Run the auto-reassignment process for verified tasks.

    Steps:
    1. Find all un-reassigned partial/missed verifications
    2. Estimate remaining work for each
    3. Update project constraints (add remaining hours back to backlog)
    4. Generate new plans for next N days with leftover tasks
    5. Create proposal for user (if not force)

    Args:
        target_date: Date to verify (default: today)
        dry_run: If True, preview changes without applying
        force: If True, apply changes without confirmation

    Returns:
        Dict with proposal details
    """
    if target_date is None:
        target_date = date.today()

    db = SessionLocal()
    try:
        # Find partial/missed verifications that haven't been reassigned
        verifications = (
            db.query(PlannedTaskVerification)
            .filter(
                PlannedTaskVerification.was_completed == False,
                PlannedTaskVerification.reassigned_to_plan_id.is_(None),
                PlannedTaskVerification.verified_at >= datetime.combine(target_date, datetime.min.time()),
            )
            .all()
        )

        if not verifications:
            return {"status": "no_tasks", "message": "No tasks to reassign"}

        proposals = []
        total_remaining_minutes = 0

        for v in verifications:
            task = db.query(NotionTask).filter(NotionTask.id == v.task_id).first()
            if not task:
                continue

            remaining = v.remaining_estimate_minutes or 0
            total_remaining_minutes += remaining

            proposals.append({
                "task_id": v.task_id,
                "task_title": task.title,
                "project_id": task.project_id,
                "progress": float(v.partial_progress_percentage or 0),
                "remaining_minutes": remaining,
            })

        # Update project constraints with remaining hours
        for proposal in proposals:
            remaining_hours = proposal["remaining_minutes"] / 60
            if remaining_hours > 0:
                constraint = (
                    db.query(ProjectConstraint)
                    .filter(ProjectConstraint.project_id == proposal["project_id"])
                    .first()
                )
                if constraint:
                    constraint.estimated_remaining_hours += remaining_hours
                else:
                    constraint = ProjectConstraint(
                        project_id=proposal["project_id"],
                        estimated_remaining_hours=remaining_hours,
                    )
                    db.add(constraint)

        # Generate new plan for tomorrow
        tomorrow = target_date + timedelta(days=1)
        new_allocations = allocate_hours(tomorrow)

        result = {
            "status": "dry_run" if dry_run else "applied",
            "tasks": proposals,
            "total_remaining_minutes": total_remaining_minutes,
            "new_allocations": new_allocations,
        }

        if not dry_run:
            db.commit()
            logger.info(f"Reassignment applied: {len(proposals)} tasks, {total_remaining_minutes} min")
        else:
            db.rollback()
            logger.info(f"Reassignment dry-run: {len(proposals)} tasks, {total_remaining_minutes} min")

        return result

    except Exception as e:
        db.rollback()
        logger.error(f"Reassignment failed: {e}")
        raise
    finally:
        db.close()
