"""
Sub-task aggregator.
Phase 2.5: Parses Notion to_do blocks and child pages into sub-tasks.
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


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
