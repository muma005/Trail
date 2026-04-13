"""
File-based activity monitor.
Phase 7.5: Detects work by checking file modification times without commits.
Privacy-safe: only records timestamps, never file content or keystrokes.
"""
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default threshold: >2 hours of activity without commits triggers detection
DEFAULT_UNTRACKED_THRESHOLD_MINUTES = 120


def get_last_activity_timestamp(project_path: str) -> Optional[datetime]:
    """
    Get the most recent file modification timestamp in a project directory.
    Only checks files tracked by git (if .git exists), otherwise scans all files.

    Args:
        project_path: Path to the project directory

    Returns:
        Most recent modification datetime, or None if path invalid
    """
    path = Path(project_path)
    if not path.exists() or not path.is_dir():
        logger.warning(f"Project path does not exist or is not a directory: {project_path}")
        return None

    try:
        latest_mtime = None

        # If it's a git repo, only check tracked files
        git_dir = path / ".git"
        if git_dir.exists():
            try:
                import subprocess
                result = subprocess.run(
                    ["git", "-C", str(path), "log", "-1", "--format=%ct"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    timestamp = int(result.stdout.strip())
                    latest_mtime = datetime.fromtimestamp(timestamp)
            except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
                pass

        # Fallback: scan all files in the directory
        if latest_mtime is None:
            for root, dirs, files in os.walk(path):
                # Skip hidden directories and common non-source dirs
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in (
                    'node_modules', '__pycache__', 'venv', '.venv', 'build', 'dist'
                )]
                for f in files:
                    if f.startswith('.'):
                        continue
                    try:
                        file_path = os.path.join(root, f)
                        mtime = os.path.getmtime(file_path)
                        file_dt = datetime.fromtimestamp(mtime)
                        if latest_mtime is None or file_dt > latest_mtime:
                            latest_mtime = file_dt
                    except (OSError, PermissionError):
                        continue

        return latest_mtime

    except Exception as e:
        logger.warning(f"Failed to get activity timestamp for {project_path}: {e}")
        return None


def detect_untracked_work(
    project_path: str,
    last_commit_time: Optional[datetime],
    threshold_minutes: int = DEFAULT_UNTRACKED_THRESHOLD_MINUTES,
) -> Optional[Dict[str, Any]]:
    """
    Detect if there's been file activity without corresponding commits.

    Args:
        project_path: Path to project directory
        last_commit_time: Timestamp of the last commit (from database)
        threshold_minutes: Minimum activity duration to consider as untracked work

    Returns:
        Dict with start_time, end_time, duration_minutes if untracked work detected,
        or None if no untracked work detected.
    """
    last_activity = get_last_activity_timestamp(project_path)

    if last_activity is None:
        return None

    # If there's a recent commit after the last activity, work is tracked
    if last_commit_time and last_commit_time >= last_activity:
        return None

    # Calculate activity window
    end_time = last_activity
    if last_commit_time:
        start_time = last_commit_time
    else:
        # No commit history — estimate start time based on threshold
        start_time = end_time - timedelta(minutes=threshold_minutes)

    duration_minutes = int((end_time - start_time).total_seconds() / 60)

    # Only flag if activity exceeds threshold
    if duration_minutes < threshold_minutes:
        return None

    return {
        "start_time": start_time,
        "end_time": end_time,
        "duration_minutes": duration_minutes,
    }
