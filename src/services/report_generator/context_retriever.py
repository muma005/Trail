"""
Context Retriever Agent.
Phase 3: Gathers all project data (commits, tasks, snapshots, dependencies) for report generation.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ContextRetriever:
    """
    Collects comprehensive project context from the database.
    Returns a structured JSON dict for the LLM Analyzer.
    """

    def retrieve(self, project_id: str, days_lookback: int = 30) -> Dict[str, Any]:
        """
        Gather all context for a project.

        Args:
            project_id: Project UUID
            days_lookback: How many days of history to include

        Returns:
            Structured context dict with project info, tasks, commits, snapshots, dependencies
        """
        from src.models.database.base import SessionLocal
        from src.models.database.models import (
            Commit,
            NotionTask,
            Project,
            ProjectSnapshot,
            SubTask,
            TaskDependency,
        )

        db = SessionLocal()
        try:
            # Project info
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")

            since_date = datetime.utcnow() - timedelta(days=days_lookback)

            # Tasks
            tasks = db.query(NotionTask).filter(NotionTask.project_id == project_id).all()
            task_context = [
                {
                    "id": t.notion_page_id,
                    "title": t.title,
                    "status": t.status,
                    "priority": t.priority,
                    "due_date": str(t.due_date) if t.due_date else None,
                    "progress": t.progress_percentage,
                    "estimate_minutes": t.estimated_minutes,
                    "size_tag": t.size_tag,
                }
                for t in tasks
            ]

            # Commits (recent)
            commits = (
                db.query(Commit)
                .filter(Commit.project_id == project_id, Commit.commit_date >= since_date)
                .order_by(Commit.commit_date.desc())
                .limit(50)
                .all()
            )
            commit_context = [
                {
                    "sha": c.commit_sha,
                    "message": c.message,
                    "date": c.commit_date.isoformat() if c.commit_date else None,
                    "author": c.author_name,
                    "lines_added": c.lines_added,
                    "lines_deleted": c.lines_deleted,
                }
                for c in commits
            ]

            # Latest snapshot
            latest_snapshot = (
                db.query(ProjectSnapshot)
                .filter(ProjectSnapshot.project_id == project_id)
                .order_by(ProjectSnapshot.snapshot_date.desc())
                .first()
            )
            snapshot_context = None
            if latest_snapshot:
                snapshot_context = {
                    "date": str(latest_snapshot.snapshot_date),
                    "completion_simple": float(latest_snapshot.completion_percentage_simple or 0),
                    "completion_weighted": float(latest_snapshot.completion_percentage_weighted or 0),
                    "total_tasks": latest_snapshot.total_tasks,
                    "completed_tasks": latest_snapshot.completed_tasks,
                }

            # Dependencies (blocked tasks)
            blocked_deps = (
                db.query(TaskDependency)
                .join(NotionTask, TaskDependency.task_id == NotionTask.id)
                .filter(NotionTask.project_id == project_id)
                .all()
            )
            dep_context = [
                {
                    "task_id": d.task_id,
                    "depends_on": d.depends_on_task_id,
                    "type": d.dependency_type,
                }
                for d in blocked_deps
            ]

            # Sub-tasks summary
            subtasks = (
                db.query(SubTask)
                .join(NotionTask, SubTask.parent_task_id == NotionTask.id)
                .filter(NotionTask.project_id == project_id)
                .all()
            )
            subtask_summary = {
                "total": len(subtasks),
                "completed": sum(1 for st in subtasks if st.is_completed),
            }

            context = {
                "project": {
                    "name": project.name,
                    "key": project.project_key,
                    "github_repo": project.github_repo_url,
                    "status": project.status,
                    "last_synced": project.last_synced_at.isoformat() if project.last_synced_at else None,
                },
                "tasks": task_context,
                "commits": commit_context,
                "latest_snapshot": snapshot_context,
                "dependencies": dep_context,
                "subtasks": subtask_summary,
                "retrieved_at": datetime.utcnow().isoformat(),
            }

            logger.info(f"Context retrieved for project {project.project_key}: "
                       f"{len(tasks)} tasks, {len(commits)} commits")
            return context

        finally:
            db.close()
