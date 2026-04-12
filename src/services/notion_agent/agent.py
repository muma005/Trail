"""
Notion AI Agent Poller.
Phase 5: Scans tracked Notion databases for @ai commands in page blocks.
Detects new commands and stores them in notion_commands table.
"""
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import settings
from src.core.connectors.notion_connector import NotionConnector
from src.models.database.base import SessionLocal
from src.models.database.models import NotionCommand, Project

logger = logging.getLogger(__name__)

# Regex to detect @ai commands in text
AI_COMMAND_PATTERN = re.compile(r'@ai\s+(.+?)(?:\n|$)', re.IGNORECASE)


class NotionPoller:
    """
    Polls Notion databases for @ai commands in page blocks.
    Stores detected commands in the database for processing.
    """

    def __init__(self):
        self.connector = NotionConnector(settings.notion_token)

    def poll(self) -> int:
        """
        Run one poll cycle: scan all tracked databases for new @ai commands.

        Returns:
            Number of new commands detected.
        """
        if not settings.notion_token:
            logger.warning("Notion token not configured, skipping poll")
            return 0

        db = SessionLocal()
        new_commands = 0

        try:
            # Get all active projects with Notion databases
            projects = (
                db.query(Project)
                .filter(
                    Project.status == "active",
                    Project.notion_database_id.isnot(None),
                )
                .all()
            )

            for project in projects:
                try:
                    count = self._scan_database(project)
                    new_commands += count
                except Exception as e:
                    logger.error(
                        f"Failed to scan database for project {project.project_key}: {e}"
                    )
                    continue

            if new_commands > 0:
                logger.info(f"Detected {new_commands} new @ai command(s)")

        finally:
            db.close()

        return new_commands

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    def _scan_database(self, project: Project) -> int:
        """
        Scan a Notion database for pages containing @ai commands.

        Args:
            project: Project with notion_database_id set

        Returns:
            Number of new commands found
        """
        # Get pages from the database
        pages = self.connector.fetch_database_pages(project.notion_database_id)
        new_count = 0

        for page in pages:
            page_id = page["notion_page_id"]

            # Fetch blocks for this page
            blocks = self.connector.fetch_page_blocks(page_id)

            for block in blocks:
                block_id = block.get("id", "")
                block_type = block.get("type", "")

                # Only check paragraph and heading blocks for @ai commands
                if block_type not in ("paragraph", "heading_1", "heading_2", "heading_3"):
                    continue

                # Extract text from block
                text = self._extract_block_text(block)
                if not text:
                    continue

                # Check for @ai command
                match = AI_COMMAND_PATTERN.search(text)
                if match:
                    command_text = match.group(1).strip()
                    if not command_text:
                        continue

                    # Store command (will skip if duplicate due to unique constraint)
                    stored = self._store_command(
                        project_id=project.id,
                        page_id=page_id,
                        block_id=block_id,
                        command=command_text,
                    )
                    if stored:
                        new_count += 1
                        logger.info(
                            f"New command detected in page {page_id[:8]}: {command_text[:50]}"
                        )

        return new_count

    def _extract_block_text(self, block: Dict) -> str:
        """
        Extract plain text from a Notion block.

        Args:
            block: Notion block dict

        Returns:
            Plain text string or empty string
        """
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})
        rich_text = block_data.get("rich_text", [])

        parts = []
        for item in rich_text:
            plain = item.get("plain_text", "")
            if plain:
                parts.append(plain)

        return " ".join(parts).strip()

    def _store_command(
        self,
        project_id: str,
        page_id: str,
        block_id: str,
        command: str,
    ) -> bool:
        """
        Store a detected command in the database.
        Skips if already exists (unique constraint on page_id + block_id).

        Returns:
            True if newly inserted, False if already exists
        """
        db = SessionLocal()
        try:
            # Check if already exists
            existing = (
                db.query(NotionCommand)
                .filter(
                    NotionCommand.page_id == page_id,
                    NotionCommand.block_id == block_id,
                )
                .first()
            )

            if existing:
                return False

            # Insert new command
            new_cmd = NotionCommand(
                project_id=project_id,
                page_id=page_id,
                block_id=block_id,
                command=command,
                status="pending",
            )
            db.add(new_cmd)
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            # Unique constraint violation is expected - not an error
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                return False
            logger.error(f"Failed to store command: {e}")
            return False
        finally:
            db.close()


def poll_notion_commands() -> int:
    """
    Wrapper function for Celery Beat scheduling.
    Can be called directly or scheduled.
    """
    poller = NotionPoller()
    return poller.poll()
