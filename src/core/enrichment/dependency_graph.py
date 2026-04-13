"""
Dependency graph builder and topological sort for scheduling.
Phase 6.5: Respects task_dependencies including cross-project deps.
Uses Kahn's algorithm with cycle detection.
"""
import logging
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from src.models.database.base import SessionLocal
from src.models.database.models import NotionTask, Project, TaskDependency

logger = logging.getLogger(__name__)


def build_dependency_graph(project_ids: List[str]) -> Tuple[Dict[str, List[str]], Set[str]]:
    """
    Build a dependency graph for tasks in the given projects.

    Args:
        project_ids: List of project UUIDs to include

    Returns:
        Tuple of (graph, cycle_broken_tasks)
        graph: dict mapping task_id → list of dependency task_ids
        cycle_broken_tasks: set of task IDs where cycles were broken
    """
    db = SessionLocal()
    graph: Dict[str, List[str]] = {}
    cycle_broken_tasks: Set[str] = set()

    try:
        # Get all dependencies for these projects
        deps = (
            db.query(TaskDependency)
            .join(NotionTask, TaskDependency.task_id == NotionTask.id)
            .filter(NotionTask.project_id.in_(project_ids))
            .all()
        )

        # Build adjacency list: task → list of tasks it depends on
        for dep in deps:
            task_id = str(dep.task_id)
            depends_on = str(dep.depends_on_task_id) if dep.depends_on_task_id else None

            if task_id not in graph:
                graph[task_id] = []
            if depends_on:
                graph[task_id].append(depends_on)

        # Detect and break cycles using Kahn's algorithm
        graph, cycle_broken_tasks = _detect_and_break_cycles(graph)

        return graph, cycle_broken_tasks

    except Exception as e:
        logger.error(f"Failed to build dependency graph: {e}")
        return {}, set()
    finally:
        db.close()


def _detect_and_break_cycles(
    graph: Dict[str, List[str]]
) -> Tuple[Dict[str, List[str]], Set[str]]:
    """
    Detect cycles using Kahn's algorithm and break them by removing edges.

    Returns:
        Tuple of (cleaned_graph, broken_task_ids)
    """
    # Calculate in-degree
    in_degree: Dict[str, int] = {node: 0 for node in graph}
    for node in graph:
        for dep in graph[node]:
            if dep in in_degree:
                pass  # dep exists as a key
            in_degree[dep] = in_degree.get(dep, 0)

    for node in graph:
        for dep in graph[node]:
            in_degree[dep] = in_degree.get(dep, 0) + 1

    # Start with nodes that have no dependencies
    queue = [node for node in graph if not graph[node]]
    visited = set()
    broken_tasks: Set[str] = set()

    while queue:
        node = queue.pop(0)
        visited.add(node)

        # Find nodes that depend on this node
        for other_node in graph:
            if node in graph[other_node] and other_node not in visited:
                in_degree[other_node] -= 1
                if in_degree[other_node] <= 0:
                    queue.append(other_node)

    # Nodes not visited are in cycles — break them
    for node in graph:
        if node not in visited:
            logger.warning(f"Dependency cycle detected involving task {node}, breaking cycle")
            broken_tasks.add(node)
            graph[node] = []  # Break cycle by removing dependencies

    return graph, broken_tasks


def topological_sort_tasks(
    tasks: List[Dict[str, Any]],
    graph: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    """
    Sort tasks topologically respecting dependencies.
    Tasks with dependencies come after their prerequisites.

    Args:
        tasks: List of task dicts with 'id' key
        graph: Dependency graph from build_dependency_graph

    Returns:
        Sorted list of task dicts
    """
    # Build task lookup
    task_map = {str(t["id"]): t for t in tasks}

    # Kahn's algorithm for topological sort
    in_degree: Dict[str, int] = {tid: 0 for tid in task_map}
    reverse_graph: Dict[str, List[str]] = {tid: [] for tid in task_map}

    for task_id in task_map:
        for dep_id in graph.get(task_id, []):
            if dep_id in task_map:
                in_degree[task_id] = in_degree.get(task_id, 0) + 1
                if dep_id not in reverse_graph:
                    reverse_graph[dep_id] = []
                reverse_graph[dep_id].append(task_id)

    # Start with tasks that have no dependencies
    queue = [tid for tid in task_map if in_degree.get(tid, 0) == 0]
    sorted_tasks = []

    while queue:
        # Sort by priority within same dependency level
        queue.sort(key=lambda tid: {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}.get(
            task_map[tid].get("priority", "Medium"), 2
        ))

        node = queue.pop(0)
        sorted_tasks.append(task_map[node])

        for dependent in reverse_graph.get(node, []):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    # Add any remaining tasks (cycle-broken ones)
    remaining = [task_map[tid] for tid in task_map if task_map[tid] not in sorted_tasks]
    sorted_tasks.extend(remaining)

    return sorted_tasks


def get_cross_project_warnings(project_ids: List[str]) -> List[str]:
    """
    Check for cross-project dependencies that might affect scheduling.

    Returns:
        List of warning messages
    """
    db = SessionLocal()
    warnings = []

    try:
        # Find dependencies where the prerequisite is in a different project
        cross_deps = (
            db.query(TaskDependency, NotionTask, Project)
            .join(NotionTask, TaskDependency.task_id == NotionTask.id)
            .join(Project, NotionTask.project_id == Project.id)
            .filter(
                NotionTask.project_id.in_(project_ids),
                TaskDependency.depends_on_project_id.isnot(None),
            )
            .all()
        )

        for dep, task, project in cross_deps:
            warnings.append(
                f"Task in {project.project_key} depends on external project "
                f"(dependency: {dep.depends_on_project_id})"
            )

        return warnings

    except Exception as e:
        logger.error(f"Failed to check cross-project deps: {e}")
        return []
    finally:
        db.close()
