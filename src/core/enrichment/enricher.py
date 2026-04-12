"""
Commit-to-task linker.
Phase 2: Exact matching (confidence=1.0) and embedding-based suggestions (confidence<1.0).
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from src.core.enrichment.commit_parser import parse_task_id
from src.core.enrichment.embedding_generator import embedder
from src.models.database.session import DatabaseError
from src.utils.exceptions.base import TrailError

logger = logging.getLogger(__name__)


class CommitLinker:
    """
    Links GitHub commits to Notion tasks.
    Two strategies:
    1. Exact match: parsed_task_id matches task notion_page_id or a custom property
    2. Embedding suggestion: cosine similarity between commit message and task title
    """

    @staticmethod
    def exact_match_links(
        project_id: str,
        commits: List[Dict[str, Any]],
        tasks: List[Dict[str, Any]],
    ) -> int:
        """
        Create exact links for commits with parsed_task_id.
        Matches against task notion_page_id.

        Returns the number of links created.
        """
        from src.models.database.session import create_commit_link

        # Build lookup: task notion_page_id → task id
        task_lookup = {}
        for task in tasks:
            page_id = task.get("notion_page_id", "")
            # Notion page IDs have dashes; strip them for comparison
            task_lookup[page_id.replace("-", "")] = task["id"]
            task_lookup[page_id] = task["id"]

        link_count = 0
        for commit in commits:
            task_id = commit.get("parsed_task_id")
            if not task_id:
                continue

            # Try to find matching task
            matched_task_id = task_lookup.get(task_id)
            if matched_task_id:
                try:
                    create_commit_link(commit["commit_id"], matched_task_id, confidence=1.0, is_suggestion=False)
                    link_count += 1
                    logger.info(f"Linked commit {commit['sha'][:8]} to task {matched_task_id[:8]} (exact match)")
                except Exception as e:
                    logger.warning(f"Failed to create link for commit {commit['sha'][:8]}: {e}")

        return link_count

    @staticmethod
    def generate_embedding_suggestions(
        project_id: str,
        unlinked_commits: List[Dict[str, Any]],
        unlinked_tasks: List[Dict[str, Any]],
    ) -> int:
        """
        Generate embedding-based link suggestions for unlinked commits.

        Returns the number of suggestions created.
        """
        from src.models.database.session import create_commit_link

        if not embedder.is_available():
            logger.info("Embedding model not available, skipping suggestions")
            return 0

        # Prepare inputs for embedder
        commit_inputs = [(c["sha"], c.get("message", "")) for c in unlinked_commits]
        task_inputs = [(t["id"], t.get("title", "")) for t in unlinked_tasks]

        suggestions = embedder.find_suggestions(commit_inputs, task_inputs)

        suggestion_count = 0
        for suggestion in suggestions:
            try:
                # Find commit_id from sha
                commit_id = None
                for c in unlinked_commits:
                    if c["sha"] == suggestion["commit_sha"]:
                        commit_id = c["commit_id"]
                        break

                if commit_id:
                    create_commit_link(
                        commit_id=commit_id,
                        task_id=suggestion["task_id"],
                        confidence=suggestion["confidence"],
                        is_suggestion=True,
                    )
                    suggestion_count += 1
            except Exception as e:
                logger.warning(f"Failed to create suggestion link: {e}")

        logger.info(f"Created {suggestion_count} embedding-based suggestions")
        return suggestion_count
