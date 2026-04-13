"""
Tool registry for the AI Brain.
Phase 9: Wraps existing functions as callable tools with descriptions and schemas.
"""
import json
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class Tool:
    """
    Represents a single callable tool with metadata.
    """

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        function: Callable,
        requires_confirmation: bool = False,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.function = function
        self.requires_confirmation = requires_confirmation

    def to_dict(self) -> Dict[str, Any]:
        """Convert tool definition to OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": [
                        k for k, v in self.parameters.items()
                        if v.get("required", False)
                    ],
                },
            },
        }

    def execute(self, **kwargs) -> Any:
        """Execute the tool function with provided arguments."""
        try:
            result = self.function(**kwargs)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Tool execution failed: {self.name}({kwargs})")
            return {"success": False, "error": str(e)}


class ToolRegistry:
    """
    Registry of all available tools.
    """

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all_definitions(self) -> List[Dict[str, Any]]:
        """Get all tool definitions for LLM function calling."""
        return [tool.to_dict() for tool in self._tools.values()]

    def execute_tool(self, name: str, **kwargs) -> Any:
        """Execute a tool by name with arguments."""
        tool = self.get_tool(name)
        if not tool:
            return {"success": False, "error": f"Unknown tool: {name}"}
        return tool.execute(**kwargs)

    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())


def create_default_tool_registry() -> ToolRegistry:
    """
    Create and populate the default tool registry with all available tools.
    """
    registry = ToolRegistry()

    # --- Project & Progress Tools ---
    from src.models.database.session import get_project_by_key
    from src.core.enrichment.progress_calculator import (
        calculate_simple_progress,
        calculate_weighted_progress,
        get_commit_stats,
    )

    registry.register(Tool(
        name="get_project_info",
        description="Get basic information about a project by its key.",
        parameters={
            "project_key": {"type": "string", "description": "Project key (e.g., AUTH-01)", "required": True},
        },
        function=lambda project_key: get_project_by_key(project_key),
    ))

    registry.register(Tool(
        name="get_project_progress",
        description="Get completion progress for a project.",
        parameters={
            "project_key": {"type": "string", "description": "Project key", "required": True},
        },
        function=lambda project_key: _get_progress_wrapper(project_key),
    ))

    registry.register(Tool(
        name="get_commit_stats",
        description="Get commit statistics for a project.",
        parameters={
            "project_key": {"type": "string", "description": "Project key", "required": True},
        },
        function=lambda project_key: _get_commit_stats_wrapper(project_key),
    ))

    # --- Planning Tools ---
    from src.services.work_planner.daily_generator import generate_daily_plan
    from datetime import date

    registry.register(Tool(
        name="get_today_plan",
        description="Get today's work plan with allocations and timeline.",
        parameters={
            "detailed": {"type": "boolean", "description": "Include detailed timeline", "required": False},
        },
        function=lambda detailed=False: _today_plan_wrapper(detailed),
    ))

    # --- Task Management Tools ---
    from src.models.database.base import SessionLocal
    from src.models.database.models import NotionTask

    registry.register(Tool(
        name="get_project_tasks",
        description="Get all tasks for a project with their status.",
        parameters={
            "project_key": {"type": "string", "description": "Project key", "required": True},
        },
        function=lambda project_key: _get_tasks_wrapper(project_key),
    ))

    registry.register(Tool(
        name="update_task_status",
        description="Update the status of a Notion task.",
        parameters={
            "task_id": {"type": "string", "description": "Task UUID or Notion page ID", "required": True},
            "status": {"type": "string", "description": "New status (Done, In Progress, Not started, Blocked)", "required": True},
        },
        function=lambda task_id, status: _update_task_status_wrapper(task_id, status),
        requires_confirmation=True,
    ))

    # --- Verification Tools ---
    from src.services.verification.verifier import verify_today, verify_date

    registry.register(Tool(
        name="verify_today",
        description="Run verification for today's planned tasks.",
        parameters={},
        function=lambda: verify_today(),
    ))

    # --- Untracked Work Tools ---
    from src.services.verification.verifier import detect_untracked_sessions
    from src.services.verification.plan_adjuster import resolve_session

    registry.register(Tool(
        name="get_untracked_sessions",
        description="Get list of unresolved untracked work sessions.",
        parameters={},
        function=lambda: _get_untracked_wrapper(),
    ))

    registry.register(Tool(
        name="assign_untracked_time",
        description="Assign an untracked session to a project.",
        parameters={
            "session_id": {"type": "string", "description": "Untracked session UUID", "required": True},
            "project_key": {"type": "string", "description": "Project key to assign to", "required": True},
        },
        function=lambda session_id, project_key: resolve_session(session_id, "assign", project_key),
    ))

    # --- Learning Tools ---
    from src.services.learning.engine import get_learning_engine

    registry.register(Tool(
        name="get_focus_peaks",
        description="Get the user's focus peak hours for deep work.",
        parameters={},
        function=lambda: _get_focus_peaks_wrapper(),
    ))

    registry.register(Tool(
        name="get_learned_multiplier",
        description="Get the learned duration multiplier for a task type.",
        parameters={
            "task_type": {"type": "string", "description": "Task type (e.g., unit_test, feature, bugfix)", "required": True},
            "size_tag": {"type": "string", "description": "Size tag (quick, medium, large)", "required": False},
        },
        function=lambda task_type, size_tag="medium": _get_multiplier_wrapper(task_type, size_tag),
    ))

    # --- Reassignment Tools ---
    from src.services.verification.auto_reassignment import run_reassignment

    registry.register(Tool(
        name="preview_reassignment",
        description="Preview proposed task reassignments without applying.",
        parameters={},
        function=lambda: run_reassignment(dry_run=True),
    ))

    # --- Report Tools ---
    from src.services.report_generator.context_retriever import ContextRetriever
    from src.services.report_generator.generator import ReportWorkflow

    registry.register(Tool(
        name="get_project_report",
        description="Get a structured report for a project.",
        parameters={
            "project_key": {"type": "string", "description": "Project key", "required": True},
        },
        function=lambda project_key: _get_report_wrapper(project_key),
    ))

    logger.info(f"Tool registry initialized with {len(registry.list_tools())} tools")
    return registry


# --- Wrapper Functions ---

def _get_progress_wrapper(project_key: str) -> str:
    """Wrapper to format progress as string."""
    from src.models.database.session import get_project_by_key

    project = get_project_by_key(project_key)
    if not project:
        return f"Project '{project_key}' not found."

    simple = calculate_simple_progress(project["id"])
    weighted = calculate_weighted_progress(project["id"])

    return (
        f"Project: {project['name']} ({project_key})\n"
        f"Simple Progress: {simple['completion_percentage']:.1f}%\n"
        f"Weighted Progress: {weighted['weighted_percentage']:.1f}%\n"
        f"Tasks: {simple['completed_tasks']}/{simple['total_tasks']} completed, "
        f"{simple['in_progress_tasks']} in progress, {simple['blocked_tasks']} blocked"
    )


def _get_commit_stats_wrapper(project_key: str) -> str:
    """Wrapper to format commit stats as string."""
    from src.models.database.session import get_project_by_key

    project = get_project_by_key(project_key)
    if not project:
        return f"Project '{project_key}' not found."

    stats = get_commit_stats(project["id"])
    return (
        f"Project: {project['name']} ({project_key})\n"
        f"Total commits: {stats['total_commits']}\n"
        f"Lines added: {stats['lines_added']}, Lines deleted: {stats['lines_deleted']}"
    )


def _today_plan_wrapper(detailed: bool = False) -> str:
    """Wrapper to format today's plan as string."""
    plan = generate_daily_plan(target_date=date.today(), detailed=detailed)
    if not plan.get("allocations"):
        return "No plan for today — no projects with remaining hours."

    lines = [f"Today's Plan ({plan['date']})"]
    for alloc in plan["allocations"]:
        hours = alloc["allocated_minutes"] / 60
        lines.append(f"  {alloc['project_key']}: {alloc['name']} ({hours:.1f}h)")
    lines.append(f"Total: {plan['total_minutes']} minutes")
    return "\n".join(lines)


def _get_tasks_wrapper(project_key: str) -> str:
    """Wrapper to format project tasks as string."""
    from src.models.database.session import get_project_by_key

    project = get_project_by_key(project_key)
    if not project:
        return f"Project '{project_key}' not found."

    db = SessionLocal()
    try:
        tasks = db.query(NotionTask).filter(NotionTask.project_id == project["id"]).all()
        if not tasks:
            return f"No tasks found for project '{project_key}'."

        lines = [f"Tasks for {project['name']} ({project_key}):"]
        for t in tasks:
            lines.append(f"  [{t.status}] {t.title or 'Untitled'}"
                        f" (est: {t.estimated_minutes or '?'} min, size: {t.size_tag or '?'})")
        return "\n".join(lines)
    finally:
        db.close()


def _update_task_status_wrapper(task_id: str, status: str) -> str:
    """Wrapper to update task status."""
    from src.config.settings import settings
    from src.core.connectors.notion_connector import NotionConnector

    try:
        connector = NotionConnector(settings.notion_token)
        connector.client.pages.update(
            page_id=task_id,
            properties={"Status": {"select": {"name": status}}},
        )
        return f"✅ Task status updated to {status}."
    except Exception as e:
        return f"❌ Failed to update task status: {e}"


def _get_untracked_wrapper() -> str:
    """Wrapper to format untracked sessions as string."""
    from src.models.database.base import SessionLocal
    from src.models.database.models import UntrackedSession, Project

    db = SessionLocal()
    try:
        sessions = (
            db.query(UntrackedSession, Project.project_key, Project.name)
            .join(Project, UntrackedSession.project_id == Project.id)
            .filter(UntrackedSession.resolved == False)
            .all()
        )
        if not sessions:
            return "No unresolved untracked sessions."

        lines = ["Untracked Sessions:"]
        for session, key, name in sessions:
            lines.append(f"  {session.id[:8]}: {key} ({name}) - {session.duration_minutes} min")
        return "\n".join(lines)
    finally:
        db.close()


def _get_focus_peaks_wrapper() -> str:
    """Wrapper to format focus peaks as string."""
    engine = get_learning_engine()
    peaks = engine.get_focus_peaks()
    engine.close()
    peak_strs = [f"{h:02d}:00" for h in peaks]
    return f"Focus peaks: {', '.join(peak_strs)}"


def _get_multiplier_wrapper(task_type: str, size_tag: str) -> str:
    """Wrapper to format duration multiplier as string."""
    engine = get_learning_engine()
    multiplier = engine.get_duration_multiplier(task_type, size_tag)
    engine.close()
    return f"Duration multiplier for {task_type}/{size_tag}: {multiplier:.2f}"


def _get_report_wrapper(project_key: str) -> str:
    """Wrapper to get a project report summary."""
    from src.models.database.session import get_project_by_key
    from src.services.report_generator.context_retriever import ContextRetriever

    project = get_project_by_key(project_key)
    if not project:
        return f"Project '{project_key}' not found."

    retriever = ContextRetriever()
    context = retriever.retrieve(project["id"])

    # Return a summary instead of full LLM report
    tasks = context.get("tasks", [])
    commits = context.get("commits", [])
    return (
        f"Project Report: {project['name']} ({project_key})\n"
        f"Tasks: {len(tasks)} total\n"
        f"Commits (last 50): {len(commits)}\n"
        f"Last synced: {project.get('last_synced', 'Never')}"
    )
