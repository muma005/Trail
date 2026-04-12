"""
Notion AI Agent Responder.
Phase 5: Processes pending @ai commands, calls the Brain, writes responses back to Notion.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import settings
from src.core.connectors.notion_connector import NotionConnector
from src.models.database.base import SessionLocal
from src.models.database.models import NotionCommand
from src.ai.brain.brain_core import BrainCore

logger = logging.getLogger(__name__)


class NotionResponder:
    """
    Processes pending Notion commands and writes AI responses back to Notion.
    """

    def __init__(self):
        self.brain = BrainCore()
        self.connector = NotionConnector(settings.notion_token)

    def process_all_pending(self) -> Dict[str, int]:
        """
        Process all pending commands.

        Returns:
            Dict with counts: processed, failed
        """
        db = SessionLocal()
        results = {"processed": 0, "failed": 0}

        try:
            pending = (
                db.query(NotionCommand)
                .filter(NotionCommand.status == "pending")
                .order_by(NotionCommand.created_at)
                .all()
            )

            for cmd in pending:
                try:
                    self._process_command(db, cmd)
                    results["processed"] += 1
                except Exception as e:
                    logger.error(f"Failed to process command {cmd.id}: {e}")
                    cmd.status = "failed"
                    cmd.error_message = str(e)
                    cmd.processed_at = datetime.utcnow()
                    db.commit()
                    results["failed"] += 1

        finally:
            db.close()

        if results["processed"] > 0 or results["failed"] > 0:
            logger.info(
                f"Responder complete: {results['processed']} processed, "
                f"{results['failed']} failed"
            )

        return results

    def process_single(self, command_id: str) -> bool:
        """
        Process a single command by ID.

        Args:
            command_id: UUID of the notion_command

        Returns:
            True if processed successfully
        """
        db = SessionLocal()
        try:
            cmd = db.query(NotionCommand).filter(NotionCommand.id == command_id).first()
            if not cmd:
                logger.error(f"Command {command_id} not found")
                return False

            self._process_command(db, cmd)
            return cmd.status == "completed"

        finally:
            db.close()

    def _process_command(self, db, cmd: NotionCommand) -> None:
        """
        Process a single command: call brain, write response, update status.
        """
        # Mark as processing
        cmd.status = "processing"
        db.commit()

        # Call the brain
        response = self.brain.process_command(
            command=cmd.command,
            page_id=cmd.page_id,
            project_id=cmd.project_id,
        )

        # Write response to Notion
        response_block_id = self._write_response(cmd.page_id, response)

        # Update command status
        cmd.status = "completed"
        cmd.response_block_id = response_block_id
        cmd.processed_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"Command processed: {cmd.command[:50]} → response block {response_block_id}"
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    def _write_response(self, page_id: str, response: str) -> str:
        """
        Write an AI response as a callout block below the command.

        Args:
            page_id: Notion page ID
            response: Response text (Markdown)

        Returns:
            Block ID of the appended callout
        """
        # Split response into chunks for Notion (max 2000 chars per block)
        chunks = self._split_text(response, 1900)

        block_id = None
        for i, chunk in enumerate(chunks):
            # First chunk gets the emoji, subsequent ones are plain
            if i == 0:
                block = {
                    "object": "block",
                    "type": "callout",
                    "callout": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": chunk},
                            }
                        ],
                        "icon": {"emoji": "🤖"},
                    },
                }
            else:
                block = {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": chunk},
                            }
                        ]
                    },
                }

            # Append block to page
            resp = self.connector.client.blocks.children.append(
                block_id=page_id,
                children=[block],
            )

            if i == 0 and resp.get("results"):
                block_id = resp["results"][0]["id"]

        return block_id

    def _split_text(self, text: str, max_length: int) -> List[str]:
        """
        Split text into chunks that fit Notion's block size limit.
        Respects line boundaries, falls back to character splitting.
        """
        if len(text) <= max_length:
            return [text]

        # If text has no newlines, split by character count
        if "\n" not in text:
            return [text[i:i+max_length] for i in range(0, len(text), max_length)]

        chunks = []
        current = ""

        for line in text.split("\n"):
            if len(current) + len(line) + 1 > max_length:
                if current:
                    chunks.append(current)
                current = line
            else:
                current = (current + "\n" + line).strip()

        if current:
            chunks.append(current)

        return chunks


def process_notion_commands() -> Dict[str, int]:
    """
    Wrapper function for Celery Beat scheduling.
    Processes all pending commands.
    """
    responder = NotionResponder()
    return responder.process_all_pending()
