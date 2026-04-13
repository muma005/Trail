"""
Context switch cost manager.
Phase 6.5: Tracks and retrieves penalty minutes for switching between projects.
"""
import logging
from typing import Optional

from src.models.database.base import SessionLocal
from src.models.database.models import SwitchCost

logger = logging.getLogger(__name__)

DEFAULT_PENALTY_MINUTES = 10


def get_switch_penalty(from_project_id: str, to_project_id: str) -> int:
    """
    Get the penalty minutes for switching between two projects.
    Falls back to default if no specific cost is recorded.

    Args:
        from_project_id: Source project UUID
        to_project_id: Destination project UUID

    Returns:
        Penalty minutes
    """
    if from_project_id == to_project_id:
        return 0  # No penalty for staying on same project

    db = SessionLocal()
    try:
        record = (
            db.query(SwitchCost)
            .filter(
                SwitchCost.from_project_id == from_project_id,
                SwitchCost.to_project_id == to_project_id,
            )
            .first()
        )
        return record.penalty_minutes if record else DEFAULT_PENALTY_MINUTES
    except Exception as e:
        logger.warning(f"Failed to get switch penalty: {e}")
        return DEFAULT_PENALTY_MINUTES
    finally:
        db.close()


def set_switch_cost(from_project_id: str, to_project_id: str, penalty_minutes: int) -> None:
    """
    Set or update the switch penalty between two projects.

    Args:
        from_project_id: Source project UUID
        to_project_id: Destination project UUID
        penalty_minutes: Penalty in minutes
    """
    from datetime import datetime

    db = SessionLocal()
    try:
        record = (
            db.query(SwitchCost)
            .filter(
                SwitchCost.from_project_id == from_project_id,
                SwitchCost.to_project_id == to_project_id,
            )
            .first()
        )

        if record:
            record.penalty_minutes = penalty_minutes
            record.sample_count += 1
            record.updated_at = datetime.utcnow()
        else:
            record = SwitchCost(
                from_project_id=from_project_id,
                to_project_id=to_project_id,
                penalty_minutes=penalty_minutes,
                sample_count=1,
            )
            db.add(record)

        db.commit()
        logger.info(
            f"Switch cost set: {from_project_id[:8]} → {to_project_id[:8]} = {penalty_minutes} min"
        )
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
