"""
Learning engine: duration learning, focus peaks, empty promise detection.
Phase 8: Learns from historical data to improve future planning estimates.
"""
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.models.database.base import SessionLocal
from src.models.database.models import (
    Commit,
    LearnedPattern,
    NotionTask,
    Project,
    ProjectConstraint,
    TimeLog,
    UserPreference,
)

logger = logging.getLogger(__name__)

# Configurable parameters (could be moved to user_preferences later)
DEFAULT_CONFIDENCE_THRESHOLD = 0.5
SAMPLES_FOR_FULL_CONFIDENCE = 20
EMPTY_PROMISE_THRESHOLD = 2.0  # actual > 2× estimate
FOCUS_PEAKS_COUNT = 2  # top N hours to track


class LearningEngine:
    """
    Main orchestrator for all learning patterns.
    Handles duration multipliers, focus peaks, and empty promise detection.
    """

    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        try:
            self.db.close()
        except Exception:
            pass

    # ----------------------------------------------------------------
    # Duration Learning
    # ----------------------------------------------------------------

    def update_duration_multiplier(
        self, task_id: str, project_id: str
    ) -> Optional[float]:
        """
        After a task is completed, compare estimated vs actual time
        and update the duration multiplier using exponential moving average.

        Args:
            task_id: Notion task UUID
            project_id: Project UUID

        Returns:
            New multiplier value, or None if insufficient data.
        """
        try:
            task = self.db.query(NotionTask).filter(NotionTask.id == task_id).first()
            if not task:
                return None

            estimated = task.estimated_minutes
            actual = task.actual_minutes

            # Skip if no actual time recorded
            if actual is None or actual <= 0:
                return None

            # Skip if no estimate
            if estimated is None or estimated <= 0:
                return None

            ratio = actual / estimated
            task_type = self._extract_task_type(task)
            size_tag = task.size_tag or "unknown"

            context = json.dumps({"task_type": task_type, "size_tag": size_tag})

            # Get existing pattern
            pattern = (
                self.db.query(LearnedPattern)
                .filter(
                    LearnedPattern.pattern_type == "duration_multiplier",
                    LearnedPattern.context == context,
                )
                .first()
            )

            if pattern:
                # Exponential moving average
                old_count = pattern.sample_count or 0
                old_value = float(pattern.value)
                new_value = (old_value * old_count + ratio) / (old_count + 1)
                pattern.value = Decimal(str(new_value))
                pattern.sample_count = old_count + 1
                pattern.confidence = min(
                    Decimal("1.0"),
                    Decimal(str(pattern.sample_count)) / Decimal(str(SAMPLES_FOR_FULL_CONFIDENCE)),
                )
                pattern.updated_at = datetime.utcnow()
            else:
                # New pattern
                pattern = LearnedPattern(
                    pattern_type="duration_multiplier",
                    context=context,
                    value=Decimal(str(ratio)),
                    confidence=Decimal(str(1.0 / SAMPLES_FOR_FULL_CONFIDENCE)),
                    sample_count=1,
                )
                self.db.add(pattern)

            self.db.commit()
            logger.info(
                f"Duration multiplier updated: {task_type}/{size_tag} = {new_value:.2f} "
                f"(samples={pattern.sample_count}, confidence={float(pattern.confidence):.2f})"
            )
            return new_value

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update duration multiplier: {e}")
            return None

    def get_duration_multiplier(
        self, task_type: str, size_tag: str
    ) -> float:
        """
        Get the learned duration multiplier for a task type and size.
        Returns 1.0 if no pattern found or confidence too low.

        Args:
            task_type: Task type (e.g., 'unit_test', 'feature', 'bugfix')
            size_tag: Size tag ('quick', 'medium', 'large')

        Returns:
            Multiplier value (default 1.0)
        """
        context = json.dumps({"task_type": task_type, "size_tag": size_tag})

        try:
            pattern = (
                self.db.query(LearnedPattern)
                .filter(
                    LearnedPattern.pattern_type == "duration_multiplier",
                    LearnedPattern.context == context,
                )
                .first()
            )

            if pattern and float(pattern.confidence) >= DEFAULT_CONFIDENCE_THRESHOLD:
                return float(pattern.value)

            return 1.0

        except Exception as e:
            logger.warning(f"Failed to get duration multiplier: {e}")
            return 1.0

    def _extract_task_type(self, task: NotionTask) -> str:
        """Extract task type from task tags or title."""
        # Check tags first
        if task.tags:
            for tag in task.tags:
                if tag.lower() in ("test", "testing", "unit_test"):
                    return "unit_test"
                elif tag.lower() in ("feature", "feat"):
                    return "feature"
                elif tag.lower() in ("bug", "bugfix", "fix"):
                    return "bugfix"
                elif tag.lower() in ("docs", "documentation"):
                    return "docs"
                elif tag.lower() in ("refactor", "refactoring"):
                    return "refactor"

        # Fallback: infer from title keywords
        title = (task.title or "").lower()
        if "test" in title:
            return "unit_test"
        elif "bug" in title or "fix" in title:
            return "bugfix"
        elif "doc" in title:
            return "docs"
        elif "refactor" in title:
            return "refactor"
        else:
            return "general"

    # ----------------------------------------------------------------
    # Focus Peak Learning
    # ----------------------------------------------------------------

    def update_focus_peaks(self, days_lookback: int = 30) -> List[int]:
        """
        Analyze commit timestamps to find the hours with highest activity.
        Stores top N hours as focus peaks.

        Args:
            days_lookback: How many days of commit history to analyze

        Returns:
            List of peak hours (0-23), sorted by activity
        """
        try:
            cutoff = datetime.utcnow() - timedelta(days=days_lookback)

            commits = (
                self.db.query(Commit)
                .filter(Commit.commit_date >= cutoff)
                .all()
            )

            if not commits:
                logger.warning("No commits found for focus peak analysis")
                return []

            # Count commits per hour
            hour_counts: Dict[int, int] = {}
            for commit in commits:
                if commit.commit_date:
                    hour = commit.commit_date.hour
                    hour_counts[hour] = hour_counts.get(hour, 0) + 1

            # Get top N hours
            sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
            top_hours = [hour for hour, count in sorted_hours[:FOCUS_PEAKS_COUNT]]

            # Store patterns (delete old ones first)
            self.db.query(LearnedPattern).filter(
                LearnedPattern.pattern_type == "focus_peak_hour"
            ).delete()

            for rank, hour in enumerate(top_hours, 1):
                context = json.dumps({"hour": hour, "rank": rank})
                pattern = LearnedPattern(
                    pattern_type="focus_peak_hour",
                    context=context,
                    value=Decimal(str(hour)),
                    confidence=Decimal(str(min(1.0, hour_counts[hour] / 20))),
                    sample_count=hour_counts[hour],
                )
                self.db.add(pattern)

            self.db.commit()
            logger.info(f"Focus peaks updated: {top_hours}")
            return top_hours

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update focus peaks: {e}")
            return []

    def get_focus_peaks(self) -> List[int]:
        """
        Get learned focus peak hours.

        Returns:
            List of hours (0-23), sorted by rank. Defaults to [9, 10] if no data.
        """
        try:
            patterns = (
                self.db.query(LearnedPattern)
                .filter(LearnedPattern.pattern_type == "focus_peak_hour")
                .order_by(LearnedPattern.value)
                .all()
            )

            if not patterns:
                return [9, 10]  # Default focus hours

            hours = []
            for p in patterns:
                ctx = json.loads(p.context)
                hours.append((ctx.get("rank", 99), int(float(p.value))))

            hours.sort()
            return [h for rank, h in hours]

        except Exception as e:
            logger.warning(f"Failed to get focus peaks: {e}")
            return [9, 10]

    # ----------------------------------------------------------------
    # Empty Promise Detection
    # ----------------------------------------------------------------

    def check_empty_promise(self, project_id: str) -> Optional[float]:
        """
        Check if a project's initial estimate was overly optimistic.
        Compares estimated remaining hours vs actual logged time.

        Args:
            project_id: Project UUID

        Returns:
            Multiplier if over-optimism detected, None otherwise.
        """
        try:
            # Get project constraint (initial estimate)
            constraint = (
                self.db.query(ProjectConstraint)
                .filter(ProjectConstraint.project_id == project_id)
                .first()
            )

            if not constraint:
                return None

            initial_estimate = float(constraint.estimated_remaining_hours)
            if initial_estimate <= 0:
                return None

            # Get actual logged time for this project
            actual_minutes = (
                self.db.query(TimeLog)
                .filter(TimeLog.project_id == project_id)
                .with_entities(
                    TimeLog.duration_minutes
                )
            )

            total_actual = sum(row[0] for row in actual_minutes if row[0]) / 60.0

            if total_actual <= 0:
                return None

            # Check if actual > threshold × estimate
            ratio = total_actual / initial_estimate
            if ratio >= EMPTY_PROMISE_THRESHOLD:
                # Store multiplier
                context = json.dumps({"project_id": project_id})

                pattern = (
                    self.db.query(LearnedPattern)
                    .filter(
                        LearnedPattern.pattern_type == "empty_promise_multiplier",
                        LearnedPattern.context == context,
                    )
                    .first()
                )

                if pattern:
                    pattern.value = Decimal(str(ratio))
                    pattern.sample_count += 1
                    pattern.confidence = min(
                        Decimal("1.0"),
                        Decimal(str(pattern.sample_count)) / Decimal("5"),
                    )
                    pattern.updated_at = datetime.utcnow()
                else:
                    pattern = LearnedPattern(
                        pattern_type="empty_promise_multiplier",
                        context=context,
                        value=Decimal(str(ratio)),
                        confidence=Decimal("0.2"),
                        sample_count=1,
                    )
                    self.db.add(pattern)

                self.db.commit()
                logger.info(
                    f"Empty promise detected for project {project_id[:8]}: "
                    f"multiplier = {ratio:.2f}"
                )
                return ratio

            return None

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to check empty promise: {e}")
            return None

    def get_project_multiplier(self, project_id: str) -> float:
        """
        Get the project-specific multiplier for empty promise detection.

        Args:
            project_id: Project UUID

        Returns:
            Multiplier value (default 1.0)
        """
        context = json.dumps({"project_id": project_id})

        try:
            pattern = (
                self.db.query(LearnedPattern)
                .filter(
                    LearnedPattern.pattern_type == "empty_promise_multiplier",
                    LearnedPattern.context == context,
                )
                .first()
            )

            if pattern:
                return float(pattern.value)

            return 1.0

        except Exception as e:
            logger.warning(f"Failed to get project multiplier: {e}")
            return 1.0

    # ----------------------------------------------------------------
    # Utility Functions
    # ----------------------------------------------------------------

    def get_all_patterns(self) -> List[Dict[str, Any]]:
        """Get all learned patterns."""
        try:
            patterns = self.db.query(LearnedPattern).all()
            result = []
            for p in patterns:
                ctx = json.loads(p.context) if p.context else {}
                result.append({
                    "id": str(p.id),
                    "pattern_type": p.pattern_type,
                    "context": ctx,
                    "value": float(p.value),
                    "confidence": float(p.confidence),
                    "sample_count": p.sample_count,
                    "updated_at": str(p.updated_at),
                })
            return result
        except Exception as e:
            logger.error(f"Failed to get all patterns: {e}")
            return []

    def reset_pattern(self, pattern_type: str) -> int:
        """Delete all patterns of a given type."""
        try:
            count = (
                self.db.query(LearnedPattern)
                .filter(LearnedPattern.pattern_type == pattern_type)
                .delete()
            )
            self.db.commit()
            logger.info(f"Reset {count} patterns of type {pattern_type}")
            return count
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to reset patterns: {e}")
            return 0


def get_learning_engine() -> LearningEngine:
    """Factory function for learning engine."""
    return LearningEngine()
