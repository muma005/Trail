"""
Planner tools for the AI Brain tool registry.
Phase 10: Adds global backlog tool for cross-project recommendations.
"""
import json
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def get_global_backlog_tool() -> Dict[str, Any]:
    """
    Tool definition for getting the global backlog.
    Returns tool schema and execution function.
    """
    def _execute(limit: int = 10) -> str:
        """Get the global backlog - next tasks across all projects."""
        try:
            from src.services.work_planner.planner import get_global_backlog
            backlog = get_global_backlog(limit=limit)

            if not backlog:
                return "No tasks in global backlog."

            lines = [f"Global Backlog (next {limit} tasks):\n"]
            for i, task in enumerate(backlog, 1):
                hours = task.get("estimated_minutes", 60) / 60
                critical = " 🔴" if task.get("is_critical") else ""
                due = f", due {task.get('due_date', 'N/A')}" if task.get("due_date") else ""
                lines.append(
                    f"{i}. [{task.get('priority', 'Medium')}] {task.get('project_key')}: "
                    f"{task.get('title')} ({hours:.1f}h{due}){critical}"
                )

            return "\n".join(lines)
        except Exception as e:
            return f"Failed to get global backlog: {e}"

    return {
        "type": "function",
        "function": {
            "name": "get_global_backlog",
            "description": "Get the next tasks to work on across all projects, ordered by critical path, deadline, and priority.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of tasks to return (default 10)",
                        "default": 10,
                    },
                },
            },
        },
        "execute": _execute,
    }


def get_critical_path_tool() -> Dict[str, Any]:
    """Tool definition for getting the critical path."""
    def _execute() -> str:
        """Get the critical path across all active projects."""
        try:
            from src.services.work_planner.planner import get_critical_path
            path = get_critical_path()

            if not path:
                return "No critical path found — no tasks or dependencies."

            lines = [f"Critical Path ({len(path)} tasks):\n"]
            total_hours = 0
            for i, task in enumerate(path, 1):
                hours = task.get("estimated_minutes", 60) / 60
                total_hours += hours
                lines.append(
                    f"{i}. {task.get('project_key')}: {task.get('title')} ({hours:.1f}h)"
                )

            lines.append(f"\nTotal critical path length: {total_hours:.1f} hours")
            return "\n".join(lines)
        except Exception as e:
            return f"Failed to get critical path: {e}"

    return {
        "type": "function",
        "function": {
            "name": "get_critical_path",
            "description": "Get the critical path - longest chain of dependent tasks across all projects.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        "execute": _execute,
    }
