"""
GitHub API connector using PyGithub.
Handles authentication, repo validation, and commit fetching.
"""
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from github import Github, GithubException, UnknownObjectException

from src.core.connectors.base_connector import BaseConnector
from src.utils.exceptions.base import GitHubRepoNotFoundError, GitHubError


class GitHubConnector(BaseConnector):
    """
    Connector for GitHub REST API via PyGithub.
    Validates repository existence and extracts repo metadata.
    """

    def __init__(self, token: str, timeout: int = 30):
        super().__init__(token, timeout)

    def authenticate(self) -> Github:
        """
        Create authenticated GitHub client.

        Returns:
            PyGithub Github instance
        """
        try:
            client = Github(self.token, timeout=self.timeout)
            # Test authentication by fetching logged-in user
            user = client.get_user()
            return client
        except GithubException as e:
            raise GitHubError(
                f"GitHub authentication failed: {e.status} - {e.data.get('message', 'Unknown error')}"
            )

    def validate_access(self, repo_url: str) -> Dict[str, Any]:
        """
        Validate that a GitHub repository exists and is accessible.

        Args:
            repo_url: Full URL (https://github.com/owner/repo)

        Returns:
            Dict with repo metadata (full_name, url, default_branch)

        Raises:
            GitHubRepoNotFoundError: If repo doesn't exist or is inaccessible
        """
        full_name = self._extract_repo_full_name(repo_url)

        try:
            repo = self.client.get_repo(full_name)
            return {
                "full_name": repo.full_name,
                "url": repo.html_url,
                "default_branch": repo.default_branch,
                "private": repo.private,
                "description": repo.description or "",
            }
        except UnknownObjectException:
            raise GitHubRepoNotFoundError(
                f"Repository '{full_name}' not found.\n"
                f"Check the URL and ensure the repo exists and your token has access."
            )
        except GithubException as e:
            raise GitHubError(
                f"Failed to access repository '{full_name}': "
                f"{e.status} - {e.data.get('message', 'Unknown error')}"
            )

    def _extract_repo_full_name(self, repo_url: str) -> str:
        """
        Extract owner/repo from a GitHub URL.

        Args:
            repo_url: https://github.com/owner/repo

        Returns:
            owner/repo string
        """
        parsed = urlparse(repo_url)
        path = parsed.path.strip("/")
        # Remove .git suffix if present
        if path.endswith(".git"):
            path = path[:-4]
        return path

    def get_repo_commits_count(self, repo_url: str) -> int:
        """
        Get total commit count for a repository.

        Args:
            repo_url: Full GitHub URL

        Returns:
            Number of commits
        """
        full_name = self._extract_repo_full_name(repo_url)
        try:
            repo = self.client.get_repo(full_name)
            return repo.get_commits().totalCount
        except (UnknownObjectException, GithubException) as e:
            raise GitHubError(f"Failed to fetch commits for '{full_name}': {e}")
