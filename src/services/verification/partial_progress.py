"""
Partial progress detection.
Phase 7: Determines how much of a planned task was actually completed.
Uses multiple signals: Notion progress, sub-tasks, commit count heuristics.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Configurable commit-count heuristic (can be moved to user_preferences later)
COMMIT_PROGRESS_HEURISTIC = {
    0: 0,    # No commits → 0%
    1: 30,   # 1 commit → 30%
    2: 50,   # 2 commits → 50%
    3: 70,   # 3 commits → 70%
}
MAX_COMMIT_HEURISTIC = 70  # Cap at 70% for commits-only detection


def detect_partial_progress(
    task: Dict[str, Any],
    commits: List[Dict[str, Any]],
    subtasks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Detect partial progress for a task using multiple signals.

    Priority order:
    1. Notion progress_percentage field (if set)
    2. Sub-task completion ratio
    3. Commit count heuristic
    4. 0% (no progress)

    Args:
        task: Task dict with status, progress_percentage, estimated_minutes
        commits: List of commits linked to this task (since plan start)
        subtasks: List of sub-tasks for this task

    Returns:
        Dict with progress_percentage, detection_method, was_completed
    """
    status = task.get("status", "")
    progress = task.get("progress_percentage")

    # Check if task is complete
    if status in ("Done", "Completed", "Complete"):
        return {
            "progress_percentage": 100.0,
            "detection_method": "status",
            "was_completed": True,
        }

    # 1. Use Notion progress field if available
    if progress is not None:
        progress = float(progress)
        if progress >= 100:
            return {
                "progress_percentage": 100.0,
                "detection_method": "status",
                "was_completed": True,
            }
        return {
            "progress_percentage": progress,
            "detection_method": "status",
            "was_completed": False,
        }

    # 2. Use sub-task completion ratio
    if subtasks:
        total = len(subtasks)
        completed = sum(1 for st in subtasks if st.get("is_completed", False))
        if total > 0:
            pct = round((completed / total) * 100, 2)
            return {
                "progress_percentage": pct,
                "detection_method": "subtasks",
                "was_completed": pct >= 100,
            }

    # 3. Use commit count heuristic
    commit_count = len(commits)
    if commit_count > 0:
        pct = COMMIT_PROGRESS_HEURISTIC.get(
            commit_count, MAX_COMMIT_HEURISTIC
        )
        return {
            "progress_percentage": float(pct),
            "detection_method": "commits",
            "was_completed": False,
        }

    # 4. No progress detected
    return {
        "progress_percentage": 0.0,
        "detection_method": "none",
        "was_completed": False,
    }
