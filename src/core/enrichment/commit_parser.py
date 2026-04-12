"""
Commit message parser for extracting task IDs.
Phase 1.5: Parses commit messages for task references like [TASK-123], #456, fixes #789.
"""
import re
from typing import Optional

# Ordered patterns — first match wins
TASK_PATTERNS = [
    # Jira-style: [TASK-123], [AUTH-42]
    re.compile(r'\[([A-Z]+-\d+)\]'),
    # GitHub issue/PR reference: #456
    re.compile(r'#(\d+)'),
    # Closing keywords with issue: fixes #123, closes #456, resolves #789
    re.compile(r'(?:fixes|closes|resolves)\s+#(\d+)'),
]


def parse_task_id(message: str) -> Optional[str]:
    """
    Extract a task/issue ID from a commit message.

    Patterns matched (in order):
    1. [TASK-123] → "TASK-123"
    2. #456 → "#456"
    3. fixes #789 → "#789"

    Args:
        message: Commit message text

    Returns:
        Matched task ID string (e.g., "TASK-123" or "#456") or None
    """
    if not message:
        return None

    for pattern in TASK_PATTERNS:
        match = pattern.search(message)
        if match:
            group = match.group(1)
            # For issue number patterns, prepend #
            if group.isdigit():
                return f"#{group}"
            return group

    return None


def classify_commit(message: str) -> bool:
    """
    Determine if a commit needs manual classification.
    Returns True if no task ID was found in the message.

    Args:
        message: Commit message text

    Returns:
        True if commit needs classification (no task ID found)
    """
    return parse_task_id(message) is None
