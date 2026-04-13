"""
Daily plan generator: converts allocated hours into a timeline with tasks.
Phase 6: Generates detailed day schedule with time blocks.
"""
import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from src.models.database.base import SessionLocal
from src.models.database.models import NotionTask, Project
from src.services.task_breaker.breaker import break_into_work_units
from src.services.work_planner.user_profile import UserProfile

logger = logging.getLogger(__name__)

PRIORITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def generate_daily_plan(
    target_date: Optional[date] = None,
    detailed: bool = False,
) -> Dict[str, Any]:
    """
    Generate a daily plan with optional detailed timeline.

    Args:
        target_date: Date to plan for (default: today)
        detailed: Whether to generate a full timeline with time blocks

    Returns:
        Dict with allocation summary and optionally a timeline
    """
    if target_date is None:
        target_date = date.today()

    # Get allocations from scheduler
    from src.services.work_planner.scheduler import allocate_hours

    allocations = allocate_hours(target_date)
    if not allocations:
        return {"date": target_date, "allocations": [], "timeline": [], "total_minutes": 0}

    profile = UserProfile()
    profile.load()

    # Fetch tasks for each allocated project
    all_work_units = []
    db = SessionLocal()
    try:
        for alloc in allocations:
            project_id = alloc["project_id"]
            allocated_minutes = alloc["allocated_minutes"]

            # Get incomplete tasks for this project
            tasks = (
                db.query(NotionTask)
                .filter(
                    NotionTask.project_id == project_id,
                    NotionTask.status.notin_(("Done", "Completed")),
                )
                .order_by(
                    # Priority first, then due date
                    NotionTask.priority,
                    NotionTask.due_date,
                )
                .all()
            )

            if not tasks:
                logger.warning(
                    f"Project {alloc['project_key']} has {allocated_minutes} min allocated "
                    f"but no incomplete tasks"
                )
                alloc["note"] = "No incomplete tasks"
                continue

            # Convert tasks to work units
            task_dicts = [
                {
                    "id": t.id,
                    "title": t.title,
                    "estimated_minutes": t.estimated_minutes,
                    "size_tag": t.size_tag,
                    "priority": t.priority,
                    "project_id": t.project_id,
                }
                for t in tasks
            ]

            work_units = break_into_work_units(
                task_dicts, allocated_minutes, profile.deep_work_minutes
            )

            for unit in work_units:
                unit["project_key"] = alloc["project_key"]
                unit["project_name"] = alloc["name"]
                unit["is_constant"] = alloc.get("is_constant", False)
            all_work_units.extend(work_units)

    finally:
        db.close()

    # Generate timeline if detailed
    timeline = []
    if detailed and all_work_units:
        timeline = _generate_timeline(all_work_units, profile, target_date)

    total_minutes = sum(a["allocated_minutes"] for a in allocations)

    return {
        "date": target_date,
        "allocations": allocations,
        "work_units": all_work_units,
        "timeline": timeline,
        "total_minutes": total_minutes,
        "available_minutes": profile.total_work_minutes,
    }


def _generate_timeline(
    work_units: List[Dict[str, Any]],
    profile: UserProfile,
    target_date: date,
) -> List[Dict[str, Any]]:
    """
    Generate a detailed timeline with time blocks.
    Deep work goes in the morning, shallow in the afternoon.
    """
    timeline = []

    # Separate deep and shallow work
    deep_units = [u for u in work_units if u["type"] == "deep"]
    shallow_units = [u for u in work_units if u["type"] == "shallow"]

    current_time = datetime.combine(target_date, profile.work_start)
    work_end = datetime.combine(target_date, profile.work_end)

    # Schedule deep work first (morning)
    for unit in deep_units:
        if current_time >= work_end:
            break

        # Check for lunch break
        current_time = _skip_lunch_if_needed(current_time, profile)

        duration = timedelta(minutes=unit["estimated_minutes"])
        end_time = current_time + duration

        if end_time > work_end:
            end_time = work_end

        timeline.append({
            "start": current_time.strftime("%H:%M"),
            "end": end_time.strftime("%H:%M"),
            "type": "Deep",
            "project": unit["project_key"],
            "task": unit["title"],
            "minutes": unit["estimated_minutes"],
        })

        current_time = end_time
        # Add 5-min break between units
        current_time += timedelta(minutes=5)

    # Lunch break
    if profile.lunch_start and profile.lunch_end:
        lunch_start = datetime.combine(target_date, profile.lunch_start)
        lunch_end = datetime.combine(target_date, profile.lunch_end)

        if current_time < lunch_start:
            # Add lunch gap
            timeline.append({
                "start": profile.lunch_start.strftime("%H:%M"),
                "end": profile.lunch_end.strftime("%H:%M"),
                "type": "Lunch",
                "project": "",
                "task": "",
                "minutes": 0,
            })
            current_time = max(current_time, lunch_end)

    # Schedule shallow work (afternoon)
    for unit in shallow_units:
        if current_time >= work_end:
            break

        current_time = _skip_lunch_if_needed(current_time, profile)

        duration = timedelta(minutes=unit["estimated_minutes"])
        end_time = current_time + duration

        if end_time > work_end:
            end_time = work_end

        timeline.append({
            "start": current_time.strftime("%H:%M"),
            "end": end_time.strftime("%H:%M"),
            "type": "Shallow",
            "project": unit["project_key"],
            "task": unit["title"],
            "minutes": unit["estimated_minutes"],
        })

        current_time = end_time
        current_time += timedelta(minutes=5)

    # Buffer/overflow
    if current_time < work_end:
        buffer_minutes = int((work_end - current_time).total_seconds() / 60)
        timeline.append({
            "start": current_time.strftime("%H:%M"),
            "end": work_end.strftime("%H:%M"),
            "type": "Buffer",
            "project": "",
            "task": "Overflow / unplanned work",
            "minutes": buffer_minutes,
        })

    return timeline


def _skip_lunch_if_needed(
    current_time: datetime, profile: UserProfile
) -> datetime:
    """Skip past lunch break if we've entered it."""
    if profile.lunch_start and profile.lunch_end:
        lunch_start = current_time.replace(
            hour=profile.lunch_start.hour,
            minute=profile.lunch_start.minute,
        )
        lunch_end = current_time.replace(
            hour=profile.lunch_end.hour,
            minute=profile.lunch_end.minute,
        )
        if lunch_start <= current_time < lunch_end:
            return current_time.replace(
                hour=profile.lunch_end.hour,
                minute=profile.lunch_end.minute,
            )
    return current_time
