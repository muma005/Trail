"""
Scheduling algorithm: time-weighted round robin.
Phase 6: Allocates daily hours across projects based on urgency, deadlines, and constraints.
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from src.models.database.base import SessionLocal
from src.models.database.models import Project, ProjectConstraint
from src.services.work_planner.user_profile import UserProfile

logger = logging.getLogger(__name__)

# Configurable constants (could be moved to user_preferences later)
CONSTANT_PROJECT_SHARE = 0.40  # 40% of day goes to constant project
MIN_CONSTANT_HOURS = 2.0  # Minimum hours for constant project even if 40% is less
PRIORITY_WEIGHTS = {"Critical": 4.0, "High": 3.0, "Medium": 2.0, "Low": 1.0}


def get_user_available_hours(profile: UserProfile) -> int:
    """
    Compute total available work minutes for the day.
    Excludes lunch and breaks.
    """
    return profile.total_work_minutes


def get_project_urgency(constraint: ProjectConstraint, current_date: date) -> float:
    """
    Calculate urgency: priority weight / max(1, days_until_deadline).
    Projects without deadlines get a baseline urgency of 0.1.
    """
    priority_weight = PRIORITY_WEIGHTS.get(constraint.priority, 2.0)

    if constraint.deadline:
        days_until = (constraint.deadline - current_date).days
        if days_until <= 0:
            # Overdue — highest urgency
            return priority_weight * 10.0
        urgency = priority_weight / max(1, days_until)
    else:
        urgency = priority_weight * 0.1  # Baseline for no deadline

    return urgency


def allocate_hours(
    current_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Allocate daily hours across projects using time-weighted round robin.

    Algorithm:
    1. Constant project gets max(40% of day, 2 hours) minimum
    2. Remaining hours distributed by urgency (deadline proximity + priority)
    3. Cap at max_parallel_projects per day
    4. Skip projects with no remaining hours

    Returns:
        List of dicts: {project_id, project_key, name, allocated_minutes, urgency}
    """
    if current_date is None:
        current_date = date.today()

    profile = UserProfile()
    profile.load()
    total_minutes = get_user_available_hours(profile)

    db = SessionLocal()
    try:
        # Get all active projects with constraints
        projects = (
            db.query(Project, ProjectConstraint)
            .outerjoin(ProjectConstraint, Project.id == ProjectConstraint.project_id)
            .filter(Project.status == "active")
            .all()
        )

        if not projects:
            logger.info("No active projects to schedule")
            return []

        # Build constraint lookup
        constraints = {}
        for proj, constraint in projects:
            if constraint and constraint.estimated_remaining_hours > 0:
                constraints[proj.id] = {
                    "project": proj,
                    "constraint": constraint,
                    "urgency": get_project_urgency(constraint, current_date),
                    "remaining_hours": float(constraint.estimated_remaining_hours),
                }

        if not constraints:
            logger.info("No projects with remaining hours")
            return []

        # Identify constant project
        constant_project_id = profile.constant_project_id
        constant_alloc = 0

        if constant_project_id and constant_project_id in constraints:
            # Constant project gets max(40% of day, min 2 hours)
            constant_share = max(
                total_minutes * CONSTANT_PROJECT_SHARE,
                MIN_CONSTANT_HOURS * 60,
            )
            # Cap at remaining hours
            constant_remaining = constraints[constant_project_id]["remaining_hours"] * 60
            constant_alloc = min(constant_share, constant_remaining)

        # Remaining minutes for other projects
        remaining_minutes = total_minutes - constant_alloc
        remaining_projects = {
            pid: data
            for pid, data in constraints.items()
            if pid != constant_project_id
        }

        # Sort by urgency, take top N
        max_parallel = profile.max_parallel_projects
        scheduled_projects = []

        # Add constant project first
        if constant_project_id and constant_alloc > 0:
            const_data = constraints[constant_project_id]
            scheduled_projects.append({
                "project_id": constant_project_id,
                "project_key": const_data["project"].project_key,
                "name": const_data["project"].name,
                "allocated_minutes": round(constant_alloc),
                "urgency": const_data["urgency"],
                "is_constant": True,
            })

        # Allocate remaining by urgency
        sorted_projects = sorted(
            remaining_projects.items(),
            key=lambda x: x[1]["urgency"],
            reverse=True,
        )

        slots_left = max_parallel - len(scheduled_projects)
        if slots_left <= 0 or not sorted_projects:
            # Only constant project today
            return scheduled_projects

        # Take top N by urgency
        top_projects = sorted_projects[:slots_left]

        # Calculate total urgency for proportional distribution
        total_urgency = sum(data["urgency"] for _, data in top_projects)

        for pid, data in top_projects:
            if total_urgency > 0:
                proportion = data["urgency"] / total_urgency
            else:
                proportion = 1.0 / len(top_projects)

            alloc = remaining_minutes * proportion
            # Cap at remaining hours
            remaining_mins = data["remaining_hours"] * 60
            alloc = min(alloc, remaining_mins)

            # Phase 8: Apply learned project multiplier (empty promise detection)
            try:
                from src.services.learning.engine import get_learning_engine
                engine = get_learning_engine()
                multiplier = engine.get_project_multiplier(str(pid))
                engine.close()
                alloc *= multiplier
            except Exception:
                pass  # Keep original allocation if learning fails

            scheduled_projects.append({
                "project_id": pid,
                "project_key": data["project"].project_key,
                "name": data["project"].name,
                "allocated_minutes": round(alloc),
                "urgency": data["urgency"],
                "is_constant": False,
            })

        total_allocated = sum(p["allocated_minutes"] for p in scheduled_projects)
        logger.info(
            f"Allocated {total_allocated}/{total_minutes} minutes across "
            f"{len(scheduled_projects)} projects"
        )

        return scheduled_projects

    finally:
        db.close()
