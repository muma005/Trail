"""
Escalation Engine.
Phase 4: Monitors stale projects, delegates to notifier and archive_manager.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from src.models.database.base import SessionLocal
from src.models.database.models import Project, UserPreference
from src.services.escalation.archive_manager import archive_project
from src.services.escalation.notifier import post_notion_comment, send_slack_message
from src.utils.exceptions.base import NotionError

logger = logging.getLogger(__name__)


class EscalationEngine:
    """
    Checks active projects for staleness and escalates based on thresholds:
    - Warning: Notion comment when idle > warning_days
    - Critical: Slack webhook when idle > critical_days
    - Archive: Set status='archived' when idle > archive_days

    Notifications are sent only once per escalation level (tracked via columns).
    """

    def check_stale_projects(self) -> Dict[str, int]:
        """
        Run the daily stale project check.

        Returns:
            Dict with counts: warned, critical, archived
        """
        db = SessionLocal()
        results = {"warned": 0, "critical": 0, "archived": 0, "skipped": 0}

        try:
            # Get user preferences for thresholds
            prefs = db.query(UserPreference).first()
            if not prefs:
                logger.warning("No user preferences found, using defaults")
                warning_days = 7
                critical_days = 14
                archive_days = 21
            else:
                warning_days = prefs.warning_days or 7
                critical_days = prefs.critical_days or 14
                archive_days = prefs.archive_days or 21

            # Get all active projects
            active_projects = db.query(Project).filter(Project.status == "active").all()

            for project in active_projects:
                try:
                    # Calculate days idle
                    last_date = project.last_commit_date or project.last_synced_at
                    if not last_date:
                        last_date = project.created_at

                    days_idle = (datetime.utcnow() - last_date).days if last_date else 999

                    # Archive check (highest priority)
                    if days_idle > archive_days:
                        archive_project(project, days_idle)
                        results["archived"] += 1
                        continue

                    # Critical notification
                    if days_idle > critical_days:
                        should_notify = (
                            not project.last_critical_notified_at
                            or project.last_critical_notified_at < last_date
                        )
                        if should_notify:
                            self._send_critical_alert(project, days_idle)
                            project.last_critical_notified_at = datetime.utcnow()
                            db.commit()
                            results["critical"] += 1

                    # Warning notification
                    elif days_idle > warning_days:
                        should_notify = (
                            not project.last_warning_notified_at
                            or project.last_warning_notified_at < last_date
                        )
                        if should_notify:
                            self._send_warning(project, days_idle)
                            project.last_warning_notified_at = datetime.utcnow()
                            db.commit()
                            results["warned"] += 1

                    else:
                        results["skipped"] += 1

                except Exception as e:
                    logger.error(f"Error processing project {project.project_key}: {e}")
                    results["skipped"] += 1
                    continue

            logger.info(
                f"Stale project check complete: "
                f"{results['warned']} warned, {results['critical']} critical, "
                f"{results['archived']} archived, {results['skipped']} skipped"
            )

        finally:
            db.close()

        return results

    def _send_warning(self, project: Project, days_idle: int) -> None:
        """Send a warning notification for a stale project."""
        try:
            post_notion_comment(
                project.notion_database_id,
                f"⚠️ **Project Warning**: '{project.name}' has been idle for **{days_idle} days**.\n"
                f"Please resume work or consider archiving."
            )
        except NotionError as e:
            logger.error(f"Failed to post Notion comment for {project.project_key}: {e}")

        logger.warning(f"Warning sent for {project.project_key}: {days_idle} days idle")

    def _send_critical_alert(self, project: Project, days_idle: int) -> None:
        """Send a critical notification for a very stale project."""
        try:
            post_notion_comment(
                project.notion_database_id,
                f"🚨 **CRITICAL**: '{project.name}' has been idle for **{days_idle} days**.\n"
                f"If no action is taken, this project will be archived soon."
            )
        except NotionError as e:
            logger.error(f"Failed to post Notion comment for {project.project_key}: {e}")

        try:
            send_slack_message(
                f"🚨 *Project {project.name}* has been idle for *{days_idle} days*.\n"
                f"Last activity: {project.last_commit_date or 'Never'}\n"
                f"Link: `trail project resurrect --key {project.project_key}`"
            )
        except Exception as e:
            logger.error(f"Failed to send Slack alert for {project.project_key}: {e}")

        logger.critical(f"Critical alert sent for {project.project_key}: {days_idle} days idle")


def check_stale_projects() -> Dict[str, int]:
    """Wrapper function for Celery Beat scheduling."""
    engine = EscalationEngine()
    return engine.check_stale_projects()
