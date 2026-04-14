"""
Morning briefing and celebration detection.
Phase 9 (Week 3): Proactive intelligence - daily briefings and celebrations.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from src.models.database.base import SessionLocal
from src.models.database.models import (
    NotionTask,
    Project,
    ProjectConstraint,
    UntrackedSession,
)
from src.services.escalation.notifier import send_slack_message
from src.services.work_planner.daily_generator import generate_daily_plan

logger = logging.getLogger(__name__)


def generate_morning_briefing() -> str:
    """
    Generate a morning briefing with today's plan, stale projects, blockers, etc.

    Returns:
        Formatted briefing text
    """
    lines = ["🌅 **Trail Morning Briefing**", f"_Date: {date.today()}_", ""]

    # 1. Today's plan
    try:
        plan = generate_daily_plan(target_date=date.today(), detailed=False)
        if plan.get("allocations"):
            lines.append("**Today's Plan:**")
            for alloc in plan["allocations"]:
                hours = alloc["allocated_minutes"] / 60
                lines.append(f"• {alloc['project_key']}: {alloc['name']} ({hours:.1f}h)")
            lines.append("")
        else:
            lines.append("**Today's Plan:** No tasks scheduled")
            lines.append("")
    except Exception as e:
        logger.warning(f"Could not fetch today's plan: {e}")
        lines.append("**Today's Plan:** Unable to fetch (database unavailable)")
        lines.append("")

    # 2-4. Stale projects, blocked tasks, untracked sessions
    try:
        db = SessionLocal()
        try:
            # Stale projects
            stale_threshold = date.today() - timedelta(days=7)
            stale_projects = (
                db.query(Project)
                .filter(
                    Project.status == "active",
                    Project.last_commit_date < stale_threshold,
                )
                .all()
            )

            if stale_projects:
                lines.append("**⚠️ Stale Projects (no commits for >7 days):**")
                for proj in stale_projects:
                    days_idle = (date.today() - proj.last_commit_date.date()).days if proj.last_commit_date else "?"
                    lines.append(f"• {proj.project_key}: {proj.name} ({days_idle} days)")
                lines.append("")

            # Blocked tasks
            blocked_tasks = (
                db.query(NotionTask, Project.project_key)
                .join(Project, NotionTask.project_id == Project.id)
                .filter(NotionTask.status == "Blocked")
                .all()
            )

            if blocked_tasks:
                lines.append("**🚧 Blocked Tasks:**")
                for task, key in blocked_tasks:
                    lines.append(f"• [{key}] {task.title or 'Untitled'}")
                lines.append("")

            # Untracked sessions
            untracked = (
                db.query(UntrackedSession, Project.project_key)
                .join(Project, UntrackedSession.project_id == Project.id)
                .filter(UntrackedSession.resolved == False)
                .all()
            )

            if untracked:
                lines.append(f"**🕵️ Untracked Sessions:** {len(untracked)} unresolved")
                for session, key in untracked:
                    lines.append(f"• {key}: {session.duration_minutes} min")
                lines.append("")

        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Could not fetch project data for briefing: {e}")

    lines.append("---")
    lines.append("*Run `trail plan today` for details, or `trail brain ask \"...\"` for help.*")

    return "\n".join(lines)


def send_morning_briefing() -> bool:
    """
    Generate and send the morning briefing via configured channels.

    Returns:
        True if sent successfully
    """
    try:
        briefing = generate_morning_briefing()
        logger.info("Morning briefing generated")

        # Send via Slack if configured
        try:
            send_slack_message(briefing)
            logger.info("Morning briefing sent to Slack")
        except Exception as e:
            logger.warning(f"Failed to send briefing to Slack: {e}")

        # For Notion, we'd need a specific page to post to
        # This would reuse the Notion agent's response writer
        # For now, log the briefing
        logger.info(f"Morning briefing:\n{briefing}")
        return True

    except Exception as e:
        logger.error(f"Failed to generate morning briefing: {e}")
        return False


def check_celebrations() -> List[Dict[str, Any]]:
    """
    Check for projects that reached 100% completion or achieved milestones.

    Returns:
        List of celebration dicts with project_key, name, reason
    """
    db = SessionLocal()
    celebrations = []

    try:
        active_projects = db.query(Project).filter(Project.status == "active").all()

        for project in active_projects:
            # Get tasks for this project
            tasks = db.query(NotionTask).filter(NotionTask.project_id == project.id).all()
            if not tasks:
                continue

            # Check if all tasks are completed
            completed = sum(1 for t in tasks if t.status in ("Done", "Completed"))
            total = len(tasks)

            if total > 0 and completed == total:
                celebrations.append({
                    "project_key": project.project_key,
                    "name": project.name,
                    "reason": f"All {total} tasks completed! 🎉",
                })
                continue

            # Check if remaining hours = 0 but tasks still exist (edge case)
            constraint = (
                db.query(ProjectConstraint)
                .filter(ProjectConstraint.project_id == project.id)
                .first()
            )

            if constraint and float(constraint.estimated_remaining_hours or 0) <= 0 and total > 0:
                celebrations.append({
                    "project_key": project.project_key,
                    "name": project.name,
                    "reason": f"Remaining hours reached 0 ({completed}/{total} tasks done)",
                })

    finally:
        db.close()

    return celebrations


def send_celebrations() -> int:
    """
    Check for and send celebration messages.

    Returns:
        Number of celebrations sent
    """
    celebrations = check_celebrations()
    count = 0

    for cel in celebrations:
        message = (
            f"🎉 **Congratulations!**\n\n"
            f"You finished **{cel['name']}** ({cel['project_key']})!\n"
            f"{cel['reason']}\n\n"
            f"Great job! 🚀"
        )

        try:
            send_slack_message(message)
            logger.info(f"Celebration sent for {cel['project_key']}")
            count += 1
        except Exception as e:
            logger.warning(f"Failed to send celebration for {cel['project_key']}: {e}")

    return count
