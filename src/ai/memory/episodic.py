"""
Memory layers for the AI Brain.
Phase 9: Episodic (past conversations), Semantic (facts), Procedural (preferences), Working (current session).
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.ai.brain.context_manager import get_conversation_manager

logger = logging.getLogger(__name__)


class EpisodicMemory:
    """
    Episodic memory: stores past conversations and decisions.
    Retrieved via vector similarity for context injection.
    """

    def __init__(self):
        self.cm = get_conversation_manager()

    def retrieve_similar(self, query: str, session_id: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Retrieve semantically similar past messages."""
        return self.cm.get_similar_messages(query, session_id=session_id, limit=limit)

    def store_interaction(self, session_id: str, user_query: str, assistant_response: str):
        """Store a user-assistant interaction pair."""
        self.cm.add_message(session_id, "user", user_query)
        self.cm.add_message(session_id, "assistant", assistant_response)


class SemanticMemory:
    """
    Semantic memory: stores facts about projects (deadlines, tech stack, etc.).
    For MVP, this is backed by the database tables directly.
    """

    def get_project_facts(self, project_key: str) -> Dict[str, Any]:
        """Get known facts about a project."""
        from src.models.database.session import get_project_by_key

        project = get_project_by_key(project_key)
        if not project:
            return {}

        facts = {
            "name": project["name"],
            "key": project["project_key"],
            "github_repo": project["github_repo_url"],
            "notion_db": project["notion_database_id"],
            "last_synced": str(project.get("last_synced_at", "Never")),
            "status": project.get("status", "active"),
        }

        # Get constraints if available
        try:
            from src.models.database.base import SessionLocal
            from src.models.database.models import ProjectConstraint

            db = SessionLocal()
            try:
                constraint = (
                    db.query(ProjectConstraint)
                    .filter(ProjectConstraint.project_id == project["id"])
                    .first()
                )
                if constraint:
                    facts["deadline"] = str(constraint.deadline) if constraint.deadline else None
                    facts["remaining_hours"] = float(constraint.estimated_remaining_hours)
                    facts["priority"] = constraint.priority
                    facts["is_constant"] = constraint.is_constant
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to get project constraints: {e}")

        return facts


class ProceduralMemory:
    """
    Procedural memory: how the user likes to work (preferences, habits).
    Backed by user_preferences and learned_patterns tables.
    """

    def get_user_preferences(self) -> Dict[str, Any]:
        """Get user's working preferences."""
        from src.services.work_planner.user_profile import get_user_profile

        profile = get_user_profile()
        return {
            "work_start": str(profile.work_start),
            "work_end": str(profile.work_end),
            "deep_work_minutes": profile.deep_work_minutes,
            "max_parallel": profile.max_parallel_projects,
        }

    def get_learned_habits(self) -> Dict[str, Any]:
        """Get learned patterns that reflect user's habits."""
        from src.services.learning.engine import get_learning_engine

        engine = get_learning_engine()
        patterns = engine.get_all_patterns()
        engine.close()

        habits = {}
        for p in patterns:
            if p["pattern_type"] == "focus_peak_hour":
                ctx = json.loads(p.get("context", "{}"))
                habits.setdefault("focus_peaks", []).append(ctx.get("hour"))
            elif p["pattern_type"] == "duration_multiplier":
                ctx = json.loads(p.get("context", "{}"))
                habits[f"multiplier_{ctx.get('task_type', 'unknown')}"] = p["value"]

        return habits


class WorkingMemory:
    """
    Working memory: current session context (last few exchanges, current project).
    """

    def __init__(self):
        self._current_project: Optional[str] = None
        self._session_context: Dict[str, Any] = {}

    def set_current_project(self, project_key: str):
        """Set the default project for this session."""
        self._current_project = project_key
        self._session_context["current_project"] = project_key

    def get_current_project(self) -> Optional[str]:
        """Get the current default project."""
        return self._current_project

    def set_context(self, key: str, value: Any):
        """Set a context value."""
        self._session_context[key] = value

    def get_context(self, key: str) -> Any:
        """Get a context value."""
        return self._session_context.get(key)

    def get_full_context(self) -> Dict[str, Any]:
        """Get all current context."""
        return self._session_context.copy()

    def clear(self):
        """Clear working memory."""
        self._current_project = None
        self._session_context.clear()
