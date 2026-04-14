"""
Work Planner — main orchestrator.
Phase 6: Coordinates scheduling, task breaking, and timeline generation.
Phase 10: Integrates global scheduler for cross-project orchestration.
"""
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from src.services.work_planner.daily_generator import generate_daily_plan
from src.services.work_planner.global_scheduler import get_global_scheduler
from src.services.work_planner.scheduler import allocate_hours
from src.services.work_planner.user_profile import UserProfile

logger = logging.getLogger(__name__)


def get_today_plan(detailed: bool = False, use_global: bool = False) -> Dict[str, Any]:
    """
    Get the work plan for today.

    Args:
        detailed: Whether to include detailed timeline
        use_global: Whether to use global scheduler (cross-project)

    Returns:
        Plan dict with allocations and optionally timeline
    """
    if use_global:
        scheduler = get_global_scheduler()
        scheduler.build_graph()
        return scheduler.generate_leveled_plan(start_date=date.today(), days_ahead=1)
    return generate_daily_plan(target_date=date.today(), detailed=detailed)


def get_weekly_plan(start_date: Optional[date] = None) -> List[Dict[str, Any]]:
    """Generate a 5-day work plan."""
    if start_date is None:
        start_date = date.today()

    plans = []
    for i in range(5):
        day = start_date
        plan = generate_daily_plan(target_date=day, detailed=False)
        plans.append(plan)

    return plans


def get_critical_path() -> List[Dict[str, Any]]:
    """
    Get the critical path across all active projects.

    Returns:
        List of task dicts on the critical path.
    """
    scheduler = get_global_scheduler()
    scheduler.build_graph()
    return scheduler.compute_critical_path()


def get_global_backlog(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get the global backlog - next N tasks to work on across all projects.

    Args:
        limit: Number of tasks to return

    Returns:
        List of task dicts ordered by global priority.
    """
    scheduler = get_global_scheduler()
    scheduler.build_graph()
    return scheduler.get_global_backlog(limit=limit)


def get_leveled_plan(days_ahead: int = 14) -> Dict[str, Any]:
    """
    Generate a resource-leveled plan for the next N days.

    Args:
        days_ahead: Number of days to plan

    Returns:
        Dict with daily assignments and utilization stats.
    """
    scheduler = get_global_scheduler()
    scheduler.build_graph()
    return scheduler.generate_leveled_plan(days_ahead=days_ahead)
