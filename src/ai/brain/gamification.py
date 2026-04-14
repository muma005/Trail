"""
Gamification engine: points, streaks, and badges.
Phase 9.5: Rewards plan adherence and task completion.
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.models.database.base import SessionLocal
from src.models.database.models import UserAchievement, UserPreference

logger = logging.getLogger(__name__)

# Point thresholds
POINTS_100_ADHERENCE = 10
POINTS_80_ADHERENCE = 5
POINTS_50_ADHERENCE = 2
POINTS_PER_COMPLETED_TASK = 1

# Streak badge thresholds
STREAK_BADGES = {
    7: "First Week Streak",
    14: "Two Week Warrior",
    30: "Monthly Master",
    60: "Dedicated Planner",
    90: "Quarterly Champion",
}


class GamificationEngine:
    """Manages points, streaks, and badges for user motivation."""

    def award_daily_points(self, adherence_percentage: float, completed_tasks: int = 0) -> Dict[str, Any]:
        """Award points for daily plan adherence and task completion."""
        db = SessionLocal()
        result = {"points_awarded": 0, "new_total": 0, "streak_updated": False}

        try:
            prefs = db.query(UserPreference).first()
            if not prefs:
                return result

            if adherence_percentage >= 100:
                points = POINTS_100_ADHERENCE
            elif adherence_percentage >= 80:
                points = POINTS_80_ADHERENCE
            elif adherence_percentage >= 50:
                points = POINTS_50_ADHERENCE
            else:
                points = 0

            task_points = completed_tasks * POINTS_PER_COMPLETED_TASK
            total_points = points + task_points
            prefs.total_points = (prefs.total_points or 0) + total_points
            result["points_awarded"] = total_points
            result["new_total"] = prefs.total_points

            if adherence_percentage >= 80:
                prefs.current_streak = (prefs.current_streak or 0) + 1
                prefs.longest_streak = max(prefs.longest_streak or 0, prefs.current_streak)
                result["streak_updated"] = True
                self._check_streak_badges(db, prefs.current_streak)
            else:
                if prefs.current_streak and prefs.current_streak > 0:
                    prefs.current_streak = 0

            db.commit()
            return result
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to award daily points: {e}")
            return result
        finally:
            db.close()

    def _check_streak_badges(self, db, current_streak: int) -> None:
        """Check if user earned a streak badge and award if so."""
        for threshold, badge_name in STREAK_BADGES.items():
            if current_streak == threshold:
                existing = db.query(UserAchievement).filter(
                    UserAchievement.achievement_type == "badge",
                    UserAchievement.achievement_name == badge_name,
                ).first()
                if not existing:
                    badge = UserAchievement(
                        achievement_type="badge",
                        achievement_name=badge_name,
                        value=current_streak,
                        earned_at=datetime.utcnow(),
                        achievement_metadata=json.dumps({"streak_days": current_streak}),
                    )
                    db.add(badge)
                    logger.info(f"Badge awarded: {badge_name} ({current_streak} day streak)")

    def award_project_finisher_badge(self, project_key: str) -> None:
        """Award badge for completing a project ahead of schedule."""
        db = SessionLocal()
        try:
            badge_name = "Project Finisher"
            existing = db.query(UserAchievement).filter(
                UserAchievement.achievement_type == "badge",
                UserAchievement.achievement_name == badge_name,
            ).first()
            if not existing:
                badge = UserAchievement(
                    achievement_type="badge",
                    achievement_name=badge_name,
                    value=1,
                    earned_at=datetime.utcnow(),
                    achievement_metadata=json.dumps({"project_key": project_key}),
                )
                db.add(badge)
                db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to award project finisher badge: {e}")
        finally:
            db.close()

    def get_user_stats(self) -> Dict[str, Any]:
        """Get current gamification stats for the user."""
        db = SessionLocal()
        try:
            prefs = db.query(UserPreference).first()
            if not prefs:
                return {"total_points": 0, "current_streak": 0, "longest_streak": 0, "badges": []}

            badges = (
                db.query(UserAchievement)
                .filter(UserAchievement.achievement_type == "badge")
                .order_by(UserAchievement.earned_at.desc())
                .all()
            )

            badge_list = [{"name": b.achievement_name, "value": b.value, "earned_at": str(b.earned_at)} for b in badges]

            return {
                "total_points": prefs.total_points or 0,
                "current_streak": prefs.current_streak or 0,
                "longest_streak": prefs.longest_streak or 0,
                "badges": badge_list,
            }
        except Exception as e:
            logger.error(f"Failed to get user stats: {e}")
            return {"total_points": 0, "current_streak": 0, "longest_streak": 0, "badges": []}
        finally:
            db.close()


def get_gamification_engine() -> GamificationEngine:
    """Factory function for gamification engine."""
    return GamificationEngine()
