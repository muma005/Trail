"""
Notion API connector using notion-client.
Phase 2: Fetches database pages with pagination, extracts properties, converts types.
"""
import logging
from typing import Any, Dict, List, Optional

from notion_client import Client
from notion_client.errors import APIResponseError

from src.core.connectors.base_connector import BaseConnector
from src.utils.exceptions.base import NotionDatabaseNotFoundError, NotionError

logger = logging.getLogger(__name__)


class NotionConnector(BaseConnector):
    """
    Connector for Notion API via notion-client.
    Phase 0: Validates database existence.
    Phase 2: Fetches all pages with pagination, extracts structured properties.
    """

    def __init__(self, token: str, timeout: int = 30):
        super().__init__(token, timeout)

    def authenticate(self) -> Client:
        """Create authenticated Notion client."""
        return Client(auth=self.token, timeout_ms=self.timeout * 1000)

    def validate_access(self, database_id: str) -> Dict[str, Any]:
        """
        Validate that a Notion database exists and is accessible.
        Returns database metadata.
        """
        try:
            db = self.client.databases.retrieve(database_id)
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
                    f"Notion database '{database_id}' not found."
                )
            elif e.code == "unauthorized":
                raise NotionDatabaseNotFoundError(
                    f"Notion integration lacks access to database '{database_id}'."
                )
            else:
                raise NotionError(f"Notion API error: {e.code} - {e.message}")

    def fetch_database_pages(self, database_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all pages from a Notion database with full pagination.
        Returns a list of simplified page dicts with extracted properties.

        Handles up to 100 items per request, auto-paginates until done.
        """
        all_pages = []
        start_cursor = None

        try:
            while True:
                response = self.client.databases.query(
                    database_id=database_id,
                    start_cursor=start_cursor,
                    page_size=100,
                )

                pages = response.get("results", [])
                for page in pages:
                    page_data = self._parse_page(page)
                    all_pages.append(page_data)

                # Check if there are more pages
                if not response.get("has_more", False):
                    break
                start_cursor = response.get("next_cursor")

            logger.info(f"Fetched {len(all_pages)} pages from Notion database {database_id}")
            return all_pages

        except APIResponseError as e:
            raise NotionError(f"Failed to query Notion database: {e.code} - {e.message}")

    def fetch_page_blocks(self, page_id: str) -> List[Dict[str, Any]]:
        """
        Fetch child blocks of a page (for parsing to_do lists, checklists).
        Returns list of block dicts.
        """
        try:
            response = self.client.blocks.children.list(block_id=page_id)
            return response.get("results", [])
        except APIResponseError as e:
            logger.warning(f"Failed to fetch blocks for page {page_id}: {e}")
            return []

    def _parse_page(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a Notion page into a flat dict with extracted properties.
        Converts Notion's nested property types to simple Python types.
        """
        props = page.get("properties", {})

        return {
            "notion_page_id": page["id"],
            "title": self._extract_title(props),
            "status": self._extract_select(props, "Status"),
            "priority": self._extract_select(props, "Priority"),
            "mooscow": self._extract_select(props, "MoSCoW"),
            "due_date": self._extract_date(props, "Due date"),
            "completed_at": self._extract_date(props, "Completed"),
            "progress_percentage": self._extract_number(props, "Progress %"),
            "estimated_minutes": self._extract_estimate(props),
            "tags": self._extract_multi_select(props, "Tags"),
            "relations": self._extract_relations(props),
            "created_time": page.get("created_time"),
            "last_edited_time": page.get("last_edited_time"),
        }

    # -------------------------------------------------------------------------
    # Property extractors — handle Notion's nested property structure
    # -------------------------------------------------------------------------

    def _extract_title(self, props: Dict[str, Any]) -> Optional[str]:
        """Extract title from 'Name' or 'Title' property."""
        for key in ("Name", "Title"):
            prop = props.get(key, {})
            if prop.get("type") == "title":
                titles = prop.get("title", [])
                if titles:
                    return titles[0].get("plain_text", "")
        return None

    def _extract_select(self, props: Dict[str, Any], prop_name: str) -> Optional[str]:
        """Extract a select value by property name."""
        prop = props.get(prop_name, {})
        if prop.get("type") == "select":
            select_val = prop.get("select")
            return select_val.get("name") if select_val else None
        elif prop.get("type") == "status":
            return prop.get("status", {}).get("name")
        return None

    def _extract_date(self, props: Dict[str, Any], prop_name: str) -> Optional[str]:
        """Extract an ISO date string from a date property."""
        prop = props.get(prop_name, {})
        if prop.get("type") == "date":
            date_val = prop.get("date")
            return date_val.get("start") if date_val else None
        return None

    def _extract_number(self, props: Dict[str, Any], prop_name: str) -> Optional[float]:
        """Extract a number value by property name."""
        prop = props.get(prop_name, {})
        if prop.get("type") == "number":
            return prop.get("number")
        return None

    def _extract_multi_select(self, props: Dict[str, Any], prop_name: str) -> List[str]:
        """Extract multi-select values as a list of strings."""
        prop = props.get(prop_name, {})
        if prop.get("type") == "multi_select":
            return [item.get("name", "") for item in prop.get("multi_select", [])]
        return []

    def _extract_relations(self, props: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Extract all relation properties.
        Returns dict of {property_name: [related_page_ids]}.
        Captures common relation names: Blocks, Blocked by, Depends on, Parent task.
        """
        relation_names = ["Blocks", "Blocked by", "Depends on", "Parent task", "Sub-tasks"]
        relations = {}

        for name in relation_names:
            prop = props.get(name, {})
            if prop.get("type") == "relation":
                related_ids = [item.get("id") for item in prop.get("relation", [])]
                if related_ids:
                    relations[name] = related_ids

        return relations

    def _extract_estimate(self, props: Dict[str, Any]) -> Optional[int]:
        """
        Extract estimated time in minutes.
        Checks 'Estimate (hours)' and converts to minutes.
        Also checks 'Estimate (minutes)' directly.
        """
        # Try hours first
        hours = self._extract_number(props, "Estimate (hours)")
        if hours is not None:
            return int(hours * 60)

        # Try minutes directly
        minutes = self._extract_number(props, "Estimate (minutes)")
        if minutes is not None:
            return int(minutes)

        return None
