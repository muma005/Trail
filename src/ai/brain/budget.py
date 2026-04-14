"""
Budget alert system for LLM usage.
Phase 9.5: Monitors monthly spend and alerts at 80% threshold.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from src.config.settings import settings
from src.models.database.base import SessionLocal
from src.models.database.models import BudgetTracking, UserPreference
from src.services.escalation.notifier import send_slack_message

logger = logging.getLogger(__name__)

BUDGET_ALERT_THRESHOLD = 0.80  # 80%


def get_current_month_spend(user_id: Optional[str] = None) -> float:
    """Get total LLM spend for the current calendar month."""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (now.replace(day=28) + timedelta(days=4)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        query = db.query(BudgetTracking).filter(
            BudgetTracking.timestamp >= month_start,
            BudgetTracking.timestamp < month_end,
        )
        if user_id:
            query = query.filter(BudgetTracking.user_id == user_id)

        total = query.with_entities(BudgetTracking.cost).all()
        return float(sum(row[0] for row in total if row[0]))
    except Exception as e:
        logger.warning(f"Failed to get current month spend: {e}")
        return 0.0
    finally:
        db.close()


def get_budget_limit() -> float:
    """Get the monthly LLM budget limit from user preferences."""
    db = SessionLocal()
    try:
        prefs = db.query(UserPreference).first()
        if prefs and prefs.llm_budget_monthly_usd:
            return float(prefs.llm_budget_monthly_usd)
        return 10.00
    except Exception as e:
        logger.warning(f"Failed to get budget limit: {e}")
        return 10.00
    finally:
        db.close()


def check_budget_alert() -> Optional[str]:
    """
    Check if monthly spend has reached 80% of budget limit.
    Sends alert if threshold crossed and not already alerted today.
    """
    try:
        spend = get_current_month_spend()
        limit = get_budget_limit()
        threshold = limit * BUDGET_ALERT_THRESHOLD

        if spend < threshold:
            return None

        db = SessionLocal()
        try:
            prefs = db.query(UserPreference).first()
            if prefs and prefs.last_budget_alert_sent:
                if prefs.last_budget_alert_sent.date() == datetime.utcnow().date():
                    return None

            pct = (spend / limit) * 100 if limit > 0 else 100
            message = (
                f"⚠️ **Budget Alert**\n\n"
                f"You have spent **${spend:.2f}** of your **${limit:.2f}** monthly LLM budget "
                f"({pct:.0f}%).\n\n"
                f"Consider switching to cheaper models or reducing usage."
            )

            try:
                send_slack_message(message)
            except Exception as e:
                logger.warning(f"Failed to send budget alert to Slack: {e}")

            if prefs:
                prefs.last_budget_alert_sent = datetime.utcnow()
                db.commit()

            logger.info(f"Budget alert sent: ${spend:.2f}/${limit:.2f} ({pct:.0f}%)")
            return message
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to check budget alert: {e}")
        return None


def record_llm_usage(cost: float, model: str = "", tokens: int = 0, description: str = "") -> None:
    """Record LLM API usage for budget tracking."""
    db = SessionLocal()
    try:
        usage = BudgetTracking(
            cost=Decimal(str(cost)),
            model=model,
            tokens_used=tokens,
            timestamp=datetime.utcnow(),
            description=description,
        )
        db.add(usage)
        db.commit()
        check_budget_alert()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to record LLM usage: {e}")
    finally:
        db.close()
