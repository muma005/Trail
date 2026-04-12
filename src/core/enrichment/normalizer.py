"""
Task enrichment: dependencies, sub-tasks, and size tagging.
Phase 2.5: Parses Notion relations for dependencies, to_do blocks for sub-tasks,
and auto-classifies task sizes.
"""
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Keywords for size classification when no estimate exists
QUICK_KEYWORDS = {"quick", "fast", "tiny", "minor", "simple", "small", "easy", "trivial"}
LARGE_KEYWORDS = {"large", "big", "major", "complex", "refactor", "rewrite", "overhaul", "epic"}


def classify_size(task: Dict[str, Any]) -> Optional[str]:
    """
    Classify a task's size as 'quick', 'medium', or 'large'.

    Rules (in priority order):
    1. If estimated_minutes exists: <15→quick, 15-240→medium, >240→large
    2. If no estimate, check title keywords
    3. Default to 'medium' if unclear
    """
    estimated = task.get("estimated_minutes")
    if estimated is not None:
        if estimated < 15:
            return "quick"
        elif estimated <= 240:
            return "medium"
        else:
            return "large"

    # Keyword-based classification
    title = (task.get("title") or "").lower()
    words = set(re.findall(r'\b\w+\b', title))

    if words & QUICK_KEYWORDS:
        return "quick"
    if words & LARGE_KEYWORDS:
        return "large"

    return "medium"


def extract_dependencies(task: Dict[str, Any], page_id_to_task_id: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Extract task dependencies from Notion relation properties.

    Args:
        task: Task dict with 'relations' key from Notion connector
        page_id_to_task_id: Maps Notion page IDs to local task IDs

    Returns:
        List of dependency dicts with task_id, depends_on_task_id, dependency_type
    """
    dependencies = []
    relations = task.get("relations", {})
    local_task_id = task.get("id")

    if not local_task_id:
        return dependencies

    # "Blocked by" → this task depends on those tasks
    blocked_by_ids = relations.get("Blocked by", [])
    for page_id in blocked_by_ids:
        target_task_id = page_id_to_task_id.get(page_id.replace("-", "")) or page_id_to_task_id.get(page_id)
        if target_task_id and target_task_id != local_task_id:
            dependencies.append({
                "task_id": local_task_id,
                "depends_on_task_id": target_task_id,
                "dependency_type": "blocked_by",
            })

    # "Blocks" → those tasks depend on this task (inverse)
    blocks_ids = relations.get("Blocks", [])
    for page_id in blocks_ids:
        target_task_id = page_id_to_task_id.get(page_id.replace("-", "")) or page_id_to_task_id.get(page_id)
        if target_task_id and target_task_id != local_task_id:
            dependencies.append({
                "task_id": target_task_id,
                "depends_on_task_id": local_task_id,
                "dependency_type": "blocked_by",
            })

    # "Depends on" → this task depends on those tasks
    depends_on_ids = relations.get("Depends on", [])
    for page_id in depends_on_ids:
        target_task_id = page_id_to_task_id.get(page_id.replace("-", "")) or page_id_to_task_id.get(page_id)
        if target_task_id and target_task_id != local_task_id:
            dependencies.append({
                "task_id": local_task_id,
                "depends_on_task_id": target_task_id,
                "dependency_type": "depends_on",
            })

    if dependencies:
        logger.debug(f"Extracted {len(dependencies)} dependencies for task {local_task_id[:8]}")

    return dependencies


def extract_subtasks_from_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parse Notion to_do blocks into sub-tasks.
    Each to_do block with a checkbox becomes a sub-task.

    Args:
        blocks: List of Notion block dicts from fetch_page_blocks()

    Returns:
        List of sub-task dicts with title, is_completed, order_index
    """
    subtasks = []
    order = 0

    for block in blocks:
        block_type = block.get("type", "")
        if block_type == "to_do":
            to_do_data = block.get("to_do", {})
            text_parts = to_do_data.get("rich_text", [])
            title = " ".join(part.get("plain_text", "") for part in text_parts).strip()

            if title:
                subtasks.append({
                    "title": title,
                    "is_completed": to_do_data.get("checked", False),
                    "order_index": order,
                })
                order += 1

    if subtasks:
        logger.debug(f"Extracted {len(subtasks)} sub-tasks from blocks")

    return subtasks
