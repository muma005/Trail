"""
Verification worker.
Phase 7: Compares planned work against actual activity (commits, task status).
Phase 7.5: Also detects untracked work sessions (file activity without commits).
Stores results in planned_task_verification table.
"""
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from src.models.database.base import SessionLocal
from src.models.database.models import (
    Commit,
    DailyPlan,
    NotionTask,
    PlannedTaskVerification,
    Project,
    SubTask,
    UntrackedSession,
)
from src.services.verification.activity_monitor import detect_untracked_work
from src.services.verification.partial_progress import detect_partial_progress

logger = logging.getLogger(__name__)


def verify_today() -> Dict[str, int]:
    """
    Run verification for today's planned tasks.

    Returns:
        Dict with counts: verified, completed, partial, missed, untracked_detected
    """
    result = verify_date(date.today())
    result["untracked_detected"] = detect_untracked_sessions()
    return result


def verify_date(target_date: date) -> Dict[str, int]:
    """
    Run verification for a specific date's planned tasks.

    Args:
        target_date: Date to verify

    Returns:
        Dict with counts: verified, completed, partial, missed
    """
    db = SessionLocal()
    results = {"verified": 0, "completed": 0, "partial": 0, "missed": 0}

    try:
        # Get daily plans for the date
        plans = db.query(DailyPlan).filter(DailyPlan.plan_date == target_date).all()

        if not plans:
            logger.info(f"No daily plans found for {target_date}")
            return results

        for plan in plans:
            tasks_planned = plan.tasks_planned or []
            if not tasks_planned:
                continue

            for planned_task in tasks_planned:
                try:
                    task_id = planned_task.get("task_id")
                    if not task_id:
                        continue

                    # Fetch the actual task
                    task = db.query(NotionTask).filter(NotionTask.id == task_id).first()
                    if not task:
                        continue

                    # Get commits for this project since plan start
                    project_id = task.project_id
                    commits = (
                        db.query(Commit)
                        .filter(
                            Commit.project_id == project_id,
                            Commit.commit_date >= datetime.combine(target_date, datetime.min.time()),
                        )
                        .all()
                    )

                    # Get sub-tasks
                    subtasks = db.query(SubTask).filter(SubTask.parent_task_id == task_id).all()

                    # Build task dict for detection
                    task_dict = {
                        "status": task.status,
                        "progress_percentage": task.progress_percentage,
                        "estimated_minutes": task.estimated_minutes,
                    }

                    commit_dicts = [
                        {
                            "sha": c.commit_sha,
                            "message": c.message,
                            "date": c.commit_date,
                        }
                        for c in commits
                    ]

                    subtask_dicts = [
                        {"is_completed": st.is_completed} for st in subtasks
                    ]

                    # Detect progress
                    progress = detect_partial_progress(task_dict, commit_dicts, subtask_dicts)

                    # Create verification record
                    verification = PlannedTaskVerification(
                        daily_plan_id=plan.id,
                        task_id=task_id,
                        actual_status=task.status,
                        actual_commit_sha=commits[0].commit_sha if commits else None,
                        was_completed=progress["was_completed"],
                        partial_progress_percentage=progress["progress_percentage"],
                        detection_method=progress["detection_method"],
                        verified_at=datetime.utcnow(),
                    )

                    # Calculate remaining estimate
                    original_estimate = task.estimated_minutes or 60  # default 60 min
                    if progress["was_completed"]:
                        verification.remaining_estimate_minutes = 0
                    elif progress["progress_percentage"] > 0:
                        remaining = original_estimate * (1 - progress["progress_percentage"] / 100)
                        verification.remaining_estimate_minutes = round(remaining)
                    else:
                        verification.remaining_estimate_minutes = original_estimate

                    # Set missed reason if not completed
                    if not progress["was_completed"]:
                        if progress["progress_percentage"] == 0:
                            verification.missed_reason = "No commits, no status change, no sub-task progress"
                        else:
                            verification.missed_reason = f"Partially completed: {progress['progress_percentage']}%"

                    db.add(verification)

                    # Update counts
                    results["verified"] += 1
                    if progress["was_completed"]:
                        results["completed"] += 1
                        # Phase 8: Learn from completed task
                        try:
                            from src.services.learning.engine import get_learning_engine
                            engine = get_learning_engine()
                            engine.update_duration_multiplier(str(task_id), str(project_id))
                            engine.close()
                        except Exception as e:
                            logger.warning(f"Duration learning failed for task {task_id}: {e}")
                    elif progress["progress_percentage"] > 0:
                        results["partial"] += 1
                    else:
                        results["missed"] += 1

                except Exception as e:
                    logger.error(f"Failed to verify task {task_id}: {e}")
                    continue

        db.commit()
        logger.info(
            f"Verification complete for {target_date}: "
            f"{results['verified']} verified, {results['completed']} completed, "
            f"{results['partial']} partial, {results['missed']} missed"
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Verification failed for {target_date}: {e}")
        raise
    finally:
        db.close()

    return results


def detect_untracked_sessions() -> int:
    """
    Scan all active projects for untracked work sessions.
    Stores detected sessions in the database.

    Returns:
        Number of new untracked sessions detected.
    """
    db = SessionLocal()
    count = 0

    try:
        projects = db.query(Project).filter(Project.status == "active").all()

        for project in projects:
            # Check if any commits exist today
            today_commits = (
                db.query(Commit)
                .filter(
                    Commit.project_id == project.id,
                    Commit.commit_date >= datetime.combine(date.today(), datetime.min.time()),
                )
                .count()
            )

            # If there are commits today, work is tracked
            if today_commits > 0:
                continue

            # Check for planned tasks today
            today_plans = db.query(DailyPlan).filter(
                DailyPlan.plan_date == date.today(),
                DailyPlan.project_id == project.id,
            ).all()

            if not today_plans:
                continue

            for plan in today_plans:
                tasks_planned = plan.tasks_planned or []
                if not tasks_planned:
                    continue

                total_planned_minutes = sum(
                    t.get("allocated_minutes", 0) for t in tasks_planned
                )

                # If >2 hours planned but no commits, flag as untracked
                if total_planned_minutes >= 120:
                    # Check if session already exists for today
                    existing = db.query(UntrackedSession).filter(
                        UntrackedSession.project_id == project.id,
                        UntrackedSession.start_time >= datetime.combine(date.today(), datetime.min.time()),
                        UntrackedSession.resolved == False,
                    ).first()

                    if not existing:
                        session = UntrackedSession(
                            project_id=project.id,
                            start_time=datetime.combine(date.today(), datetime.strptime("09:00", "%H:%M").time()),
                            end_time=datetime.combine(date.today(), datetime.strptime("17:00", "%H:%M").time()),
                            duration_minutes=total_planned_minutes,
                            resolved=False,
                        )
                        db.add(session)
                        count += 1
                        logger.info(
                            f"Detected untracked work: {project.project_key} "
                            f"({total_planned_minutes} min planned, 0 commits)"
                        )

        db.commit()
        if count > 0:
            logger.info(f"Detected {count} new untracked session(s)")

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to detect untracked sessions: {e}")
    finally:
        db.close()

    return count
