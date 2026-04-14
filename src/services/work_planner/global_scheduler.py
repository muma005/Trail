"""
Global scheduler for cross-project orchestration.
Phase 10: Builds global dependency graph, computes critical path,
and performs resource leveling across all active projects.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

from src.models.database.base import SessionLocal
from src.models.database.models import (
    NotionTask,
    Project,
    TaskDependency,
)
from src.services.work_planner.user_profile import UserProfile

logger = logging.getLogger(__name__)

PRIORITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, None: 4}


class GlobalScheduler:
    """
    Manages cross-project scheduling with:
    - Global dependency graph (networkx DiGraph)
    - Critical path method (CPM)
    - Topological sort with cycle detection
    - Resource leveling (ensures daily hours <= available)
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self.task_map: Dict[str, Dict[str, Any]] = {}

    def build_graph(self, project_ids: Optional[List[str]] = None) -> nx.DiGraph:
        """
        Build a global dependency graph for all active projects.

        Args:
            project_ids: List of project UUIDs to include. None = all active.

        Returns:
            NetworkX DiGraph with tasks as nodes and dependencies as edges.
        """
        db = SessionLocal()
        try:
            # Get incomplete tasks
            query = db.query(NotionTask, Project.project_key).join(
                Project, NotionTask.project_id == Project.id
            )
            if project_ids:
                query = query.filter(NotionTask.project_id.in_(project_ids))
            else:
                query = query.filter(Project.status == "active")

            # Exclude completed tasks
            query = query.filter(
                NotionTask.status.notin_(("Done", "Completed"))
            )

            results = query.all()
            if not results:
                logger.info("No incomplete tasks found")
                return self.graph

            # Add nodes (tasks)
            for task, project_key in results:
                task_id = str(task.id)
                est_minutes = task.estimated_minutes or 60
                due_date = task.due_date
                priority = task.priority
                remaining_hours = est_minutes / 60.0

                self.task_map[task_id] = {
                    "task_id": task_id,
                    "notion_page_id": task.notion_page_id,
                    "title": task.title or "Untitled",
                    "project_key": project_key,
                    "project_id": str(task.project_id),
                    "estimated_minutes": est_minutes,
                    "remaining_hours": remaining_hours,
                    "priority": priority,
                    "due_date": due_date,
                    "status": task.status,
                    "size_tag": task.size_tag,
                }

                self.graph.add_node(
                    task_id,
                    title=task.title or "Untitled",
                    project_key=project_key,
                    estimated_minutes=est_minutes,
                    priority=priority,
                    due_date=str(due_date) if due_date else None,
                )

            # Get dependencies
            deps_query = db.query(TaskDependency).join(
                NotionTask, TaskDependency.task_id == NotionTask.id
            )
            if project_ids:
                deps_query = deps_query.filter(NotionTask.project_id.in_(project_ids))
            else:
                deps_query = deps_query.join(
                    Project, NotionTask.project_id == Project.id
                ).filter(Project.status == "active")

            edges_added = 0
            cycles_broken = 0

            for dep in deps_query.all():
                task_id = str(dep.task_id)
                depends_on = str(dep.depends_on_task_id) if dep.depends_on_task_id else None

                # Only add edge if both tasks are in graph
                if task_id in self.graph and depends_on and depends_on in self.graph:
                    # Check if adding this edge would create a cycle
                    if nx.has_path(self.graph, task_id, depends_on):
                        # Would create cycle - skip and log
                        logger.warning(
                            f"Cycle detected: {task_id} → {depends_on}. Breaking cycle."
                        )
                        cycles_broken += 1
                        continue

                    self.graph.add_edge(depends_on, task_id)
                    edges_added += 1

            logger.info(
                f"Built global graph: {self.graph.number_of_nodes()} nodes, "
                f"{edges_added} edges, {cycles_broken} cycles broken"
            )
            return self.graph

        except Exception as e:
            logger.error(f"Failed to build global graph: {e}")
            return self.graph
        finally:
            db.close()

    def get_topological_order(self) -> List[str]:
        """
        Get tasks in topological order (dependencies first).
        Handles cycles by removing problematic edges during graph build.

        Returns:
            List of task IDs in dependency-respecting order.
        """
        try:
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXUnfeasible:
            logger.warning("Graph still has cycles after breaking. Using DFS order.")
            return list(nx.dfs_postorder_nodes(self.graph))

    def compute_critical_path(self) -> List[Dict[str, Any]]:
        """
        Compute the critical path using longest path algorithm.
        Critical path = longest chain of dependent tasks (determines min completion time).

        Returns:
            List of task dicts on the critical path, in order.
        """
        if not self.graph.nodes:
            return []

        try:
            # Create weighted graph (use estimated_minutes as weight)
            weighted_graph = nx.DiGraph()

            for node, attrs in self.graph.nodes(data=True):
                weighted_graph.add_node(node, **attrs)

            for u, v in self.graph.edges():
                u_minutes = self.graph.nodes[u].get("estimated_minutes", 60)
                weighted_graph.add_edge(u, v, weight=u_minutes)

            # Find longest path (critical path)
            # Use Bellman-Ford with negated weights to find longest path
            # Or use DAG longest path algorithm
            critical_path_nodes = nx.dag_longest_path(weighted_graph, weight="weight")

            result = []
            for task_id in critical_path_nodes:
                if task_id in self.task_map:
                    task_info = self.task_map[task_id].copy()
                    result.append(task_info)

            logger.info(f"Critical path: {len(result)} tasks")
            return result

        except Exception as e:
            logger.error(f"Failed to compute critical path: {e}")
            return []

    def get_global_backlog(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the next N tasks to work on, ordered by global priority.

        Priority order:
        1. Critical path tasks first (slack = 0)
        2. Then tasks with earliest deadline
        3. Then tasks with highest priority
        4. Then tasks with largest remaining estimate

        Args:
            limit: Number of tasks to return

        Returns:
            List of task dicts with priority info.
        """
        critical_path = self.compute_critical_path()
        critical_ids = {t["task_id"] for t in critical_path}

        # Get all incomplete tasks
        tasks = list(self.task_map.values())

        # Score each task
        scored_tasks = []
        for task in tasks:
            is_critical = task["task_id"] in critical_ids

            # Due date score (earlier = more urgent)
            if task["due_date"]:
                try:
                    due = datetime.strptime(task["due_date"], "%Y-%m-%d").date()
                    days_until_due = (due - date.today()).days
                    due_score = max(0, 1000 - days_until_due)
                except (ValueError, TypeError):
                    due_score = 0
            else:
                due_score = 0

            # Priority score
            priority_score = (4 - PRIORITY_ORDER.get(task["priority"], 4)) * 100

            # Critical path bonus
            critical_bonus = 10000 if is_critical else 0

            # Estimate score (larger tasks surface earlier)
            estimate_score = task["remaining_hours"] * 10

            total_score = critical_bonus + due_score + priority_score + estimate_score

            scored_tasks.append({
                **task,
                "is_critical": is_critical,
                "total_score": total_score,
            })

        # Sort by score descending
        scored_tasks.sort(key=lambda t: t["total_score"], reverse=True)

        return scored_tasks[:limit]

    def generate_leveled_plan(
        self,
        start_date: Optional[date] = None,
        days_ahead: int = 14,
    ) -> Dict[str, Any]:
        """
        Generate a resource-leveled plan for the next N days.
        Ensures total planned hours per day <= available work hours.

        Args:
            start_date: Starting date (default: today)
            days_ahead: Number of days to plan

        Returns:
            Dict with daily assignments and leveling adjustments.
        """
        if start_date is None:
            start_date = date.today()

        profile = UserProfile()
        profile.load()
        available_minutes = profile.total_work_minutes

        topo_order = self.get_topological_order()
        if not topo_order:
            return {"days": [], "total_tasks": 0}

        # Track task completion times (in days from start)
        task_completion_day: Dict[str, int] = {}
        daily_assignments: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(days_ahead)}
        daily_minutes: Dict[int, int] = {i: 0 for i in range(days_ahead)}

        for task_id in topo_order:
            task = self.task_map.get(task_id)
            if not task:
                continue

            # Find earliest day this task can start (after dependencies)
            earliest_day = 0
            for dep_id in self.graph.predecessors(task_id):
                if dep_id in task_completion_day:
                    dep_completion = task_completion_day[dep_id]
                    earliest_day = max(earliest_day, dep_completion + 1)

            # Find day with available capacity
            est_minutes = task["estimated_minutes"]
            assigned = False

            for day in range(earliest_day, days_ahead):
                if daily_minutes[day] + est_minutes <= available_minutes:
                    daily_assignments[day].append(task)
                    daily_minutes[day] += est_minutes
                    task_completion_day[task_id] = day
                    assigned = True
                    break

            if not assigned:
                logger.warning(
                    f"Could not schedule task {task_id} ({task['title']}) "
                    f"within {days_ahead} days"
                )

        # Build result
        days_result = []
        for day in range(days_ahead):
            day_date = start_date + timedelta(days=day)
            tasks = daily_assignments[day]
            total = daily_minutes[day]

            days_result.append({
                "date": str(day_date),
                "tasks": [
                    {
                        "title": t["title"],
                        "project_key": t["project_key"],
                        "estimated_minutes": t["estimated_minutes"],
                        "priority": t["priority"],
                    }
                    for t in tasks
                ],
                "total_minutes": total,
                "available_minutes": available_minutes,
                "utilization_pct": round(total / available_minutes * 100, 1) if available_minutes > 0 else 0,
            })

        return {
            "days": days_result,
            "total_tasks": sum(len(d["tasks"]) for d in days_result),
            "start_date": str(start_date),
            "days_ahead": days_ahead,
        }


def get_global_scheduler() -> GlobalScheduler:
    """Factory function for global scheduler."""
    return GlobalScheduler()
