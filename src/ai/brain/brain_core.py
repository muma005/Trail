"""
Trail AI Brain — Core.
Phase 5: Basic command routing for Notion @ai commands.
Future phases will add memory, reasoning engine, tool registry.
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class BrainCore:
    """
    Simple command parser and dispatcher for Notion AI commands.
    Phase 5: Handles summarize, status queries, status updates.
    Later phases: add memory layers, reasoning, tool registry.
    """

    def process_command(self, command: str, page_id: str, project_id: Optional[str] = None) -> str:
        """
        Process an @ai command and return the response.

        Args:
            command: Command text (everything after @ai)
            page_id: Notion page ID where command was issued
            project_id: Associated project ID

        Returns:
            Response text to write back to Notion
        """
        command_lower = command.lower().strip()

        # Summarize this page
        if self._matches(command_lower, ["summarize", "summary", "summarize this page"]):
            return self._summarize_page(page_id)

        # Status query: "what is the status of X?" or "status of X"
        status_match = re.search(r'(?:status of|how\'s|how is)\s+(.+?)(?:\?|$)', command_lower)
        if status_match:
            project_query = status_match.group(1).strip()
            return self._get_project_status(project_query)

        # Update status: "update status to Done" or "mark as Done"
        update_match = re.search(r'(?:update|set|mark|change)\s+(?:status\s+)?to\s+(\w+)', command_lower)
        if update_match:
            new_status = update_match.group(1)
            return self._update_task_status(page_id, new_status)

        # Unknown command
        return (
            "I don't understand that command. Try one of these:\n"
            "• `@ai summarize this page` — Get a summary of this page\n"
            "• `@ai what is the status of Project X?` — Check project progress\n"
            "• `@ai update status to Done` — Mark this task as complete"
        )

    def _matches(self, text: str, keywords: list) -> bool:
        """Check if text contains any of the keywords."""
        return any(kw in text for kw in keywords)

    def _summarize_page(self, page_id: str) -> str:
        """
        Summarize a Notion page's content using OpenRouter.
        """
        from src.config.settings import settings
        from src.core.connectors.notion_connector import NotionConnector
        from src.services.report_generator.llm_analyzer import LLMAnalyzer

        if not settings.openrouter_api_key:
            return "⚠️ OpenRouter API not configured. Cannot summarize."

        try:
            connector = NotionConnector(settings.notion_token)
            blocks = connector.fetch_page_blocks(page_id)

            # Extract text from blocks
            text_parts = []
            for block in blocks:
                block_type = block.get("type", "")
                block_data = block.get(block_type, {})
                rich_text = block_data.get("rich_text", [])
                for item in rich_text:
                    plain = item.get("plain_text", "")
                    if plain:
                        text_parts.append(plain)

            page_content = "\n".join(text_parts)

            if not page_content:
                return "This page appears to be empty."

            # Limit content to avoid token limits
            if len(page_content) > 5000:
                page_content = page_content[:5000] + "..."

            # Call LLM for summary
            analyzer = LLMAnalyzer(api_key=settings.openrouter_api_key)
            prompt = f"Summarize the following Notion page content in 3-5 bullet points:\n\n{page_content}"
            summary = analyzer.generate_report({"content": prompt})

            return f"**Page Summary:**\n{summary}"

        except Exception as e:
            logger.error(f"Failed to summarize page {page_id}: {e}")
            return f"❌ Could not summarize page. Reason: {e}"

    def _get_project_status(self, project_query: str) -> str:
        """
        Look up a project by name or key and return its progress.
        """
        from src.core.enrichment.progress_calculator import calculate_simple_progress
        from src.models.database.base import SessionLocal
        from src.models.database.models import Project

        db = SessionLocal()
        try:
            # Try match on key or name
            project = (
                db.query(Project)
                .filter(
                    Project.status == "active",
                    (Project.project_key.ilike(f"%{project_query}%")) |
                    (Project.name.ilike(f"%{project_query}%")),
                )
                .first()
            )

            if not project:
                # List matching projects
                matches = (
                    db.query(Project)
                    .filter(Project.status == "active")
                    .all()
                )
                if matches:
                    project_list = ", ".join(f"{p.project_key}: {p.name}" for p in matches[:5])
                    return (
                        f"I couldn't find a project matching '{project_query}'.\n"
                        f"Active projects: {project_list}"
                    )
                return "No active projects found."

            # Calculate progress
            progress = calculate_simple_progress(project.id)

            # Get task breakdown
            from src.models.database.models import NotionTask
            tasks = db.query(NotionTask).filter(NotionTask.project_id == project.id).all()
            total = len(tasks)
            done = sum(1 for t in tasks if t.status in ("Done", "Completed"))
            in_progress = sum(1 for t in tasks if t.status in ("In Progress", "Started"))
            blocked = sum(1 for t in tasks if t.status == "Blocked")

            response = (
                f"**{project.name}** ({project.project_key})\n"
                f"• Completion: {progress['completion_percentage']:.1f}%\n"
                f"• Tasks: {done}/{total} done, {in_progress} in progress, {blocked} blocked\n"
            )

            # Add recent activity
            from src.models.database.models import Commit
            recent_commit = (
                db.query(Commit)
                .filter(Commit.project_id == project.id)
                .order_by(Commit.commit_date.desc())
                .first()
            )
            if recent_commit:
                response += f"• Last commit: {recent_commit.message[:50]} ({recent_commit.commit_date.strftime('%Y-%m-%d')})"
            else:
                response += "• No commits recorded yet"

            return response

        except Exception as e:
            logger.error(f"Failed to get project status for '{project_query}': {e}")
            return f"❌ Could not fetch status. Reason: {e}"
        finally:
            db.close()

    def _update_task_status(self, page_id: str, new_status: str) -> str:
        """
        Update a Notion task's status property.
        """
        from src.config.settings import settings
        from src.core.connectors.notion_connector import NotionConnector

        try:
            connector = NotionConnector(settings.notion_token)

            # Update the page's Status property
            connector.client.pages.update(
                page_id=page_id,
                properties={
                    "Status": {
                        "select": {"name": new_status.capitalize()},
                    }
                },
            )

            return f"✅ Status updated to **{new_status.capitalize()}**."

        except Exception as e:
            logger.error(f"Failed to update status for page {page_id}: {e}")
            return (
                f"❌ Could not update status. Make sure:\n"
                f"• The page has a 'Status' property\n"
                f"• The integration has edit permissions\n"
                f"• Error: {e}"
            )
