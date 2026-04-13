"""
User profile and planner preferences.
Phase 6: Loads user work hours, parallel limits, constant project, deep work settings.
"""
import logging
from datetime import time
from typing import Optional

from src.models.database.base import SessionLocal
from src.models.database.models import UserPreference

logger = logging.getLogger(__name__)


class UserProfile:
    """
    Loads and provides access to user planning preferences.
    """

    def __init__(self):
        self._prefs: Optional[UserPreference] = None

    def load(self) -> None:
        """Load preferences from database."""
        db = SessionLocal()
        try:
            self._prefs = db.query(UserPreference).first()
            if not self._prefs:
                # Create default preferences
                self._prefs = UserPreference()
                db.add(self._prefs)
                db.commit()
                db.refresh(self._prefs)
                logger.info("Created default user preferences")
        finally:
            db.close()

    @property
    def work_start(self) -> time:
        return self._prefs.work_start if self._prefs else time(9, 0)

    @property
    def work_end(self) -> time:
        return self._prefs.work_end if self._prefs else time(17, 0)

    @property
    def lunch_start(self) -> Optional[time]:
        return self._prefs.lunch_start if self._prefs else None

    @property
    def lunch_end(self) -> Optional[time]:
        return self._prefs.lunch_end if self._prefs else None

    @property
    def max_parallel_projects(self) -> int:
        return self._prefs.max_parallel_projects if self._prefs else 2

    @property
    def constant_project_id(self) -> Optional[str]:
        return self._prefs.constant_project_id if self._prefs else None

    @property
    def deep_work_minutes(self) -> int:
        return self._prefs.deep_work_minutes if self._prefs else 120

    @property
    def total_work_minutes(self) -> int:
        """Calculate total available work minutes (excluding lunch)."""
        start = self.work_start
        end = self.work_end
        total = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)

        # Subtract lunch
        if self.lunch_start and self.lunch_end:
            lunch_minutes = (
                (self.lunch_end.hour * 60 + self.lunch_end.minute)
                - (self.lunch_start.hour * 60 + self.lunch_start.minute)
            )
            total -= lunch_minutes

        return max(0, total)


def get_user_profile() -> UserProfile:
    """Get or create the user profile singleton."""
    profile = UserProfile()
    profile.load()
    return profile
