"""
Daily plan generator: converts allocated hours into a timeline with tasks.
Phase 6: Generates detailed day schedule with time blocks.
Phase 6.5: Respects calendar busy slots, switch costs, time-off.
"""
import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from src.models.database.base import SessionLocal
from src.models.database.models import NotionTask, Project
from src.services.task_breaker.breaker import break_into_work_units
from src.services.work_planner.holiday_manager import is_time_off
from src.services.work_planner.user_profile import UserProfile

logger = logging.getLogger(__name__)

PRIORITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def generate_daily_plan(
    target_date: Optional[date] = None,
    detailed: bool = False,
    busy_slots: Optional[List[Dict[str, Any]]] = None,
    with_deps: bool = False,
) -> Dict[str, Any]:
    """
    Generate a daily plan with optional detailed timeline.

    Args:
        target_date: Date to plan for (default: today)
        detailed: Whether to generate a full timeline with time blocks
        busy_slots: List of {start, end, summary} from calendar
        with_deps: Whether to show dependency resolution details

    Returns:
        Dict with allocation summary and optionally a timeline
    """
    if target_date is None:
        target_date = date.today()

    # Check for time-off
    time_off_record = is_time_off(target_date)
    if time_off_record:
        logger.info(f"{target_date} is a time-off day ({time_off_record.reason})")
        return {
            "date": target_date,
            "allocations": [],
            "timeline": [],
            "total_minutes": 0,
            "time_off": True,
            "reason": time_off_record.reason,
        }

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
        timeline = _generate_timeline(all_work_units, profile, target_date, busy_slots or [])

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
    busy_slots: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Generate a detailed timeline with time blocks.
    Deep work goes in the morning, shallow in the afternoon.
    Respects calendar busy slots and inserts switch cost buffers.
    """
    if busy_slots is None:
        busy_slots = []

    timeline = []

    # Separate deep and shallow work
    deep_units = [u for u in work_units if u["type"] == "deep"]
    shallow_units = [u for u in work_units if u["type"] == "shallow"]

    current_time = datetime.combine(target_date, profile.work_start)
    work_end = datetime.combine(target_date, profile.work_end)
    last_project = None

    def is_busy(t: datetime) -> Optional[Dict[str, Any]]:
        """Check if a time slot conflicts with a meeting."""
        for slot in busy_slots:
            start = slot["start"]
            end = slot["end"]
            if isinstance(start, str):
                start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            if isinstance(end, str):
                end = datetime.fromisoformat(end.replace("Z", "+00:00"))
            if start <= t < end:
                return slot
        return None

    def skip_busy(t: datetime) -> datetime:
        """Skip past any busy slot."""
        busy = is_busy(t)
        if busy:
            end = busy["end"]
            if isinstance(end, str):
                end = datetime.fromisoformat(end.replace("Z", "+00:00"))
            return end
        return t

    def add_switch_buffer(t: datetime, new_project: str) -> datetime:
        """Insert context switch buffer if switching projects."""
        from src.services.work_planner.context_switch import get_switch_penalty

        nonlocal last_project
        if last_project and last_project != new_project:
            # Find project IDs for penalty lookup
            penalty = 10  # default
            for unit in work_units:
                if unit.get("project_key") == new_project:
                    from src.models.database.base import SessionLocal
                    from src.models.database.models import Project
                    db = SessionLocal()
                    try:
                        proj = db.query(Project).filter(Project.project_key == new_project).first()
                        last_proj = db.query(Project).filter(Project.project_key == last_project).first()
                        if proj and last_proj:
                            penalty = get_switch_penalty(str(last_proj.id), str(proj.id))
                    finally:
                        db.close()
                    break

            buffer_end = t + timedelta(minutes=penalty)
            timeline.append({
                "start": t.strftime("%H:%M"),
                "end": buffer_end.strftime("%H:%M"),
                "type": "Switch",
                "project": "",
                "task": f"Context switch buffer ({penalty} min)",
                "minutes": penalty,
            })
            return buffer_end
        return t

    # Schedule deep work first (morning)
    for unit in deep_units:
        if current_time >= work_end:
            break

        current_time = _skip_lunch_if_needed(current_time, profile)
        current_time = skip_busy(current_time)

        # Add switch buffer
        current_time = add_switch_buffer(current_time, unit.get("project_key", ""))

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

        last_project = unit.get("project_key")
        current_time = end_time
        current_time += timedelta(minutes=5)

    # Lunch break
    if profile.lunch_start and profile.lunch_end:
        lunch_start = datetime.combine(target_date, profile.lunch_start)
        lunch_end = datetime.combine(target_date, profile.lunch_end)

        if current_time < lunch_start:
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
        current_time = skip_busy(current_time)

        # Add switch buffer
        current_time = add_switch_buffer(current_time, unit.get("project_key", ""))

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

        last_project = unit.get("project_key")
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
