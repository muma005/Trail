"""
Notion API connector using notion-client.
Handles authentication, database validation, and task fetching.
"""
from typing import Any, Dict

from notion_client import Client
from notion_client.errors import APIResponseError

from src.core.connectors.base_connector import BaseConnector
from src.utils.exceptions.base import NotionDatabaseNotFoundError, NotionError


class NotionConnector(BaseConnector):
    """
    Connector for Notion API via notion-client.
    Validates database existence and extracts database metadata.
    """

    def __init__(self, token: str, timeout: int = 30):
        super().__init__(token, timeout)

    def authenticate(self) -> Client:
        """
        Create authenticated Notion client.

        Returns:
            Notion Client instance
        """
        return Client(auth=self.token, timeout_ms=self.timeout * 1000)

    def validate_access(self, database_id: str) -> Dict[str, Any]:
        """
        Validate that a Notion database exists and is accessible.

        Args:
            database_id: Notion database ID (32-char hex string)

        Returns:
            Dict with database metadata (title, properties, url)

        Raises:
            NotionDatabaseNotFoundError: If database not found or inaccessible
        """
        try:
            db = self.client.databases.retrieve(database_id)
            # Extract title from Notion's nested title array
            title_array = db.get("title", [])
            title = title_array[0].get("plain_text", "Untitled") if title_array else "Untitled"

            return {
                "id": db["id"],
                "title": title,
                "properties": db.get("properties", {}),
                "url": db.get("url", ""),
            }
        except APIResponseError as e:
            if e.code == "object_not_found":
                raise NotionDatabaseNotFoundError(
                    f"Notion database '{database_id}' not found.\n"
                    f"Check the ID and ensure your integration has access to this database.\n"
                    f"You may need to share the database with your integration."
                )
            elif e.code == "unauthorized":
                raise NotionDatabaseNotFoundError(
                    f"Notion integration token lacks access to database '{database_id}'.\n"
                    f"Share the database with your integration from Notion."
                )
            else:
                raise NotionError(
                    f"Notion API error: {e.code} - {e.message}"
                )

    def get_database_title(self, database_id: str) -> str:
        """
        Get the title of a Notion database.

        Args:
            database_id: Notion database ID

        Returns:
            Database title string
        """
        info = self.validate_access(database_id)
        return info["title"]
