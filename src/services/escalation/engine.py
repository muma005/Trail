"""
Escalation Engine.
Phase 4: Monitors stale projects, sends notifications (Notion, Slack),
and auto-archives abandoned projects.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

from src.config.settings import settings
from src.models.database.base import SessionLocal
from src.models.database.models import Project, UserPreference
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
                        # No activity at all — use creation date as baseline
                        last_date = project.created_at

                    days_idle = (datetime.utcnow() - last_date).days if last_date else 999

                    # Archive check (highest priority — happens first)
                    if days_idle > archive_days:
                        self._archive_project(db, project, days_idle)
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
        # Notion comment
        try:
            self._post_notion_comment(
                project.notion_database_id,
                f"⚠️ **Project Warning**: '{project.name}' has been idle for **{days_idle} days**.\n"
                f"Please resume work or consider archiving."
            )
        except NotionError as e:
            logger.error(f"Failed to post Notion comment for {project.project_key}: {e}")

        logger.warning(f"Warning sent for {project.project_key}: {days_idle} days idle")

    def _send_critical_alert(self, project: Project, days_idle: int) -> None:
        """Send a critical notification for a very stale project."""
        # Notion comment
        try:
            self._post_notion_comment(
                project.notion_database_id,
                f"🚨 **CRITICAL**: '{project.name}' has been idle for **{days_idle} days**.\n"
                f"If no action is taken, this project will be archived in "
                f"**{project.critical_days - days_idle}** days."
            )
        except NotionError as e:
            logger.error(f"Failed to post Notion comment for {project.project_key}: {e}")

        # Slack webhook
        try:
            self._send_slack_message(
                f"🚨 *Project {project.name}* has been idle for *{days_idle} days*.\n"
                f"Last activity: {project.last_commit_date or 'Never'}\n"
                f"Link: `trail project resurrect --key {project.project_key}`"
            )
        except Exception as e:
            logger.error(f"Failed to send Slack alert for {project.project_key}: {e}")

        logger.critical(f"Critical alert sent for {project.project_key}: {days_idle} days idle")

    def _archive_project(self, db, project: Project, days_idle: int) -> None:
        """Archive a project that has exceeded the archive threshold."""
        project.status = "archived"
        db.commit()
        logger.warning(
            f"Project {project.project_key} archived after {days_idle} days idle."
        )

    def _post_notion_comment(self, database_id: str, message: str) -> None:
        """
        Post a comment to a Notion page.
        Uses Notion's blocks API to append a callout block.
        """
        from src.core.connectors.notion_connector import NotionConnector

        if not settings.notion_token:
            raise NotionError("Notion token not configured")

        connector = NotionConnector(settings.notion_token)

        # Try to find the project page or use database
        # For simplicity, we append a comment as a database comment
        # In production, you'd link to the actual project page
        try:
            # Create a page comment on the database
            connector.client.comments.create(
                parent={"database_id": database_id},
                rich_text=[{"type": "text", "text": {"content": message}}],
            )
        except Exception as e:
            raise NotionError(f"Failed to post Notion comment: {e}")

    def _send_slack_message(self, message: str) -> None:
        """
        Send a message to a Slack channel via webhook.
        Requires SLACK_WEBHOOK_URL in .env.
        """
        webhook_url = getattr(settings, 'slack_webhook_url', None)
        if not webhook_url:
            logger.info("Slack webhook URL not configured, skipping Slack notification")
            return

        payload = {
            "text": message,
            "mrkdwn": True,
        }

        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10,
        )

        if response.status_code != 200:
            raise Exception(f"Slack webhook failed: {response.status_code} - {response.text}")

        logger.info(f"Slack message sent successfully")


def check_stale_projects() -> Dict[str, int]:
    """
    Wrapper function for Celery Beat scheduling.
    Can be called directly or scheduled.
    """
    engine = EscalationEngine()
    return engine.check_stale_projects()
