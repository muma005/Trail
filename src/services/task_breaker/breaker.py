"""
Task breaker: splits tasks into work units.
Phase 6: Combines quick tasks into batches, splits large tasks into chunks.
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Task size thresholds (in minutes)
QUICK_TASK_MAX = 15
BATCH_MAX_MINUTES = 30
LARGE_TASK_SPLIT_HOURS = 2


def break_into_work_units(
    tasks: List[Dict[str, Any]],
    allocated_minutes: int,
    deep_work_minutes: int = 120,
) -> List[Dict[str, Any]]:
    """
    Convert a list of tasks into work units for scheduling.

    Rules:
    - Quick tasks (<=15 min) are batched together (max 30 min batch)
    - Medium tasks (15-240 min) become single work units
    - Large tasks (>4 hours) are split into 2-hour chunks

    Args:
        tasks: List of task dicts with title, estimated_minutes, size_tag, priority
        allocated_minutes: Total time allocated for this project
        deep_work_minutes: Max length for a deep work unit

    Returns:
        List of work unit dicts
    """
    work_units = []
    remaining_budget = allocated_minutes

    # Separate tasks by size
    quick_tasks = []
    medium_tasks = []
    large_tasks = []

    for task in tasks:
        est = task.get("estimated_minutes", 60)
        size = task.get("size_tag", "medium")

        if size == "quick" or est <= QUICK_TASK_MAX:
            quick_tasks.append(task)
        elif size == "large" or est > 240:
            large_tasks.append(task)
        else:
            medium_tasks.append(task)

    # Batch quick tasks
    if quick_tasks:
        batch_units = _batch_quick_tasks(quick_tasks, BATCH_MAX_MINUTES)
        for batch in batch_units:
            if remaining_budget <= 0:
                break
            work_units.append(batch)
            remaining_budget -= batch["estimated_minutes"]

    # Medium tasks as-is
    for task in medium_tasks:
        if remaining_budget <= 0:
            break
        est = min(task.get("estimated_minutes", 60), remaining_budget)
        work_units.append({
            "task_id": task.get("id"),
            "title": task.get("title", "Untitled"),
            "estimated_minutes": est,
            "type": "shallow" if est < 60 else "deep",
            "project_id": task.get("project_id"),
        })
        remaining_budget -= est

    # Split large tasks
    for task in large_tasks:
        if remaining_budget <= 0:
            break
        est = task.get("estimated_minutes", 240)
        chunks = _split_large_task(task, est, deep_work_minutes)
        for chunk in chunks:
            if remaining_budget <= 0:
                break
            work_units.append(chunk)
            remaining_budget -= chunk["estimated_minutes"]

    logger.info(
        f"Created {len(work_units)} work units "
        f"(budget: {allocated_minutes} min, used: {allocated_minutes - remaining_budget} min)"
    )

    return work_units


def _batch_quick_tasks(
    tasks: List[Dict[str, Any]], max_minutes: int
) -> List[Dict[str, Any]]:
    """
    Combine quick tasks into batches of up to max_minutes.
    """
    batches = []
    current_batch = []
    current_minutes = 0

    for task in tasks:
        est = task.get("estimated_minutes", QUICK_TASK_MAX)
        if current_minutes + est > max_minutes and current_batch:
            # Flush current batch
            batches.append({
                "task_id": None,
                "title": f"Quick tasks batch ({len(current_batch)} tasks)",
                "estimated_minutes": current_minutes,
                "type": "shallow",
                "project_id": current_batch[0].get("project_id"),
                "sub_tasks": [t.get("title") for t in current_batch],
            })
            current_batch = []
            current_minutes = 0

        current_batch.append(task)
        current_minutes += est

    # Flush remaining
    if current_batch:
        batches.append({
            "task_id": None,
            "title": f"Quick tasks batch ({len(current_batch)} tasks)",
            "estimated_minutes": current_minutes,
            "type": "shallow",
            "project_id": current_batch[0].get("project_id"),
            "sub_tasks": [t.get("title") for t in current_batch],
        })

    return batches


def _split_large_task(
    task: Dict[str, Any], total_minutes: int, max_chunk: int
) -> List[Dict[str, Any]]:
    """
    Split a large task into chunks of max_chunk minutes.
    """
    chunks = []
    remaining = total_minutes
    part = 1
    total_parts = (total_minutes + max_chunk - 1) // max_chunk  # Ceiling division

    while remaining > 0:
        chunk_minutes = min(remaining, max_chunk)
        suffix = f" (Part {part}/{total_parts})" if total_parts > 1 else ""
        chunks.append({
            "task_id": task.get("id"),
            "title": f"{task.get('title', 'Untitled')}{suffix}",
            "estimated_minutes": chunk_minutes,
            "type": "deep",
            "project_id": task.get("project_id"),
        })
        remaining -= chunk_minutes
        part += 1

    return chunks
