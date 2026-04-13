"""
Work Planner — main orchestrator.
Phase 6: Coordinates scheduling, task breaking, and timeline generation.
"""
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from src.services.work_planner.daily_generator import generate_daily_plan
from src.services.work_planner.scheduler import allocate_hours
from src.services.work_planner.user_profile import UserProfile

logger = logging.getLogger(__name__)


def get_today_plan(detailed: bool = False) -> Dict[str, Any]:
    """
    Get the work plan for today.

    Args:
        detailed: Whether to include detailed timeline

    Returns:
        Plan dict with allocations and optionally timeline
    """
    return generate_daily_plan(target_date=date.today(), detailed=detailed)


def get_weekly_plan(start_date: Optional[date] = None) -> List[Dict[str, Any]]:
    """
    Generate a 5-day work plan.

    Args:
        start_date: Starting date (default: today)

    Returns:
        List of daily plan dicts
    """
    if start_date is None:
        start_date = date.today()

    plans = []
    for i in range(5):
        day = start_date
        plan = generate_daily_plan(target_date=day, detailed=False)
        plans.append(plan)

    return plans
