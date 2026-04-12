"""
Notification delivery for the Escalation Engine.
Phase 4: Sends alerts via Notion comments and Slack webhooks.
"""
import logging

import requests

from src.config.settings import settings
from src.core.connectors.notion_connector import NotionConnector
from src.utils.exceptions.base import NotionError

logger = logging.getLogger(__name__)


def post_notion_comment(database_id: str, message: str) -> None:
    """
    Post a comment to a Notion database.

    Args:
        database_id: Notion database ID
        message: Comment text (Markdown)

    Raises:
        NotionError on failure
    """
    if not settings.notion_token:
        raise NotionError("Notion token not configured")

    connector = NotionConnector(settings.notion_token)
    try:
        connector.client.comments.create(
            parent={"database_id": database_id},
            rich_text=[{"type": "text", "text": {"content": message}}],
        )
        logger.info(f"Notion comment posted to database {database_id[:8]}")
    except Exception as e:
        raise NotionError(f"Failed to post Notion comment: {e}")


def send_slack_message(message: str) -> None:
    """
    Send a message to a Slack channel via webhook.

    Args:
        message: Message text (supports mrkdwn)

    Raises:
        Exception if webhook fails
    """
    webhook_url = getattr(settings, 'slack_webhook_url', None)
    if not webhook_url:
        logger.info("Slack webhook URL not configured, skipping")
        return

    payload = {"text": message, "mrkdwn": True}
    response = requests.post(webhook_url, json=payload, timeout=10)

    if response.status_code != 200:
        raise Exception(f"Slack webhook failed: {response.status_code} - {response.text}")

    logger.info("Slack message sent successfully")
