"""
Holiday and time-off manager.
Phase 6.5: Manages user_time_off records, checks if dates are blocked.
"""
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from src.models.database.base import SessionLocal
from src.models.database.models import UserTimeOff

logger = logging.getLogger(__name__)


def is_time_off(target_date: date) -> Optional[UserTimeOff]:
    """
    Check if a date falls within a user time-off period.

    Args:
        target_date: Date to check

    Returns:
        UserTimeOff record if date is blocked, None otherwise
    """
    db = SessionLocal()
    try:
        record = (
            db.query(UserTimeOff)
            .filter(
                UserTimeOff.start_date <= target_date,
                UserTimeOff.end_date >= target_date,
                UserTimeOff.is_working == False,
            )
            .first()
        )
        return record
    except Exception as e:
        logger.error(f"Failed to check time-off for {target_date}: {e}")
        return None
    finally:
        db.close()


def add_time_off(start_date: date, end_date: date, reason: str = "", is_working: bool = False) -> str:
    """
    Add a time-off period.

    Args:
        start_date: Start date
        end_date: End date
        reason: Reason for time-off
        is_working: If True, this is a working day (overrides holiday)

    Returns:
        ID of the created record
    """
    db = SessionLocal()
    try:
        record = UserTimeOff(
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            is_working=is_working,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        logger.info(f"Added time-off: {start_date} to {end_date} ({reason})")
        return record.id
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


def remove_time_off(record_id: str) -> bool:
    """
    Remove a time-off record by ID.

    Args:
        record_id: UUID of the time-off record

    Returns:
        True if deleted
    """
    db = SessionLocal()
    try:
        record = db.query(UserTimeOff).filter(UserTimeOff.id == record_id).first()
        if record:
            db.delete(record)
            db.commit()
            logger.info(f"Removed time-off record {record_id}")
            return True
        return False
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


def list_time_off(upcoming_only: bool = True) -> List[Dict[str, Any]]:
    """
    List all time-off records.

    Args:
        upcoming_only: Only show records starting from today

    Returns:
        List of dicts with date range and reason
    """
    db = SessionLocal()
    try:
        query = db.query(UserTimeOff)
        if upcoming_only:
            query = query.filter(UserTimeOff.end_date >= date.today())
        query = query.order_by(UserTimeOff.start_date)

        records = query.all()
        return [
            {
                "id": r.id,
                "start_date": str(r.start_date),
                "end_date": str(r.end_date),
                "reason": r.reason or "",
                "is_working": r.is_working,
            }
            for r in records
        ]
    except Exception as e:
        logger.error(f"Failed to list time-off: {e}")
        return []
    finally:
        db.close()
