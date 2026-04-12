"""
GitHub API connector using PyGithub.
Phase 0: Authentication, repo validation
Phase 1: Commit fetching with rate limiting, pagination, caching, retries
"""
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from github import Github, GithubException, RateLimitExceededException, UnknownObjectException
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.core.connectors.base_connector import BaseConnector
from src.utils.exceptions.base import GitHubRepoNotFoundError, GitHubError

logger = logging.getLogger(__name__)


class GitHubConnector(BaseConnector):
    """
    Connector for GitHub REST API via PyGithub.
    Phase 0: Validates repository existence and extracts repo metadata.
    Phase 1: Fetches commits with rate limiting, pagination, and retries.
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

    # -------------------------------------------------------------------------
    # Phase 1: Commit fetching with rate limiting, retries, pagination
    # -------------------------------------------------------------------------

    def _check_rate_limit(self) -> None:
        """
        Check remaining API rate limit.
        Logs warning and waits if below 100 requests.
        """
        try:
            rate_limit = self.client.get_rate_limit()
            remaining = rate_limit.core.remaining
            reset_time = rate_limit.core.reset

            if remaining < 100:
                wait_seconds = 60
                logger.warning(
                    f"GitHub rate limit low: {remaining} remaining. "
                    f"Waiting {wait_seconds}s before proceeding. "
                    f"Resets at {reset_time}."
                )
                time.sleep(wait_seconds)
        except GithubException as e:
            logger.warning(f"Failed to check rate limit: {e}")

    @retry(
        retry=retry_if_exception_type(RateLimitExceededException),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _fetch_with_retry(self, repo, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Fetch all commits from a repository with automatic retry on rate limit.
        Uses pagination internally — fetches ALL commits, not just first page.

        Args:
            repo: PyGithub Repository object
            since: Only fetch commits after this datetime (incremental sync)

        Returns:
            List of commit dictionaries
        """
        commits = []
        try:
            # Use PyGithub's paginated iterator — get_commits handles pagination
            commit_iterator = repo.get_commits(since=since) if since else repo.get_commits()

            for commit in commit_iterator:
                commit_data = self._parse_commit(commit)
                commits.append(commit_data)

        except RateLimitExceededException:
            # tenacity will catch this and retry with backoff
            logger.warning("Rate limit exceeded, retrying...")
            raise
        except GithubException as e:
            raise GitHubError(f"Failed to fetch commits: {e.status} - {e.data.get('message', 'Unknown error')}")

        return commits

    def fetch_commits(self, repo_url: str, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Public method: fetch all commits from a repository.
        Checks rate limit before making API call, retries on rate limit.

        Args:
            repo_url: Full GitHub URL
            since: Only fetch commits after this datetime (incremental sync)

        Returns:
            List of commit dictionaries
        """
        full_name = self._extract_repo_full_name(repo_url)

        try:
            # Check rate limit before fetching
            self._check_rate_limit()

            repo = self.client.get_repo(full_name)
            commits = self._fetch_with_retry(repo, since)

            logger.info(f"Fetched {len(commits)} commits from {full_name}"
                       f"{' since ' + str(since) if since else ''}")
            return commits

        except UnknownObjectException:
            raise GitHubRepoNotFoundError(
                f"Repository '{full_name}' not found."
            )
        except GitHubError:
            raise
        except Exception as e:
            raise GitHubError(f"Unexpected error fetching commits: {e}")

    def _parse_commit(self, commit) -> Dict[str, Any]:
        """
        Parse a PyGithub Commit object into a flat dictionary.

        Args:
            commit: PyGithub Commit object

        Returns:
            Dictionary with commit data
        """
        # Extract author info — handle both GitAuthor and missing author
        author = commit.author
        author_name = author.login if author else (commit.commit.author.name if commit.commit.author else "Unknown")
        author_email = author.email if author else (commit.commit.author.email if commit.commit.author else None)

        # Extract file changes from the full commit detail
        files_changed = []
        lines_added = 0
        lines_deleted = 0

        try:
            # commit.files requires an additional API call for full details
            files = commit.files
            if files:
                for f in files:
                    file_info = {
                        "filename": f.filename,
                        "additions": f.additions or 0,
                        "deletions": f.deletions or 0,
                    }
                    files_changed.append(file_info)
                    lines_added += f.additions or 0
                    lines_deleted += f.deletions or 0
        except GithubException as e:
            logger.warning(f"Failed to fetch file details for commit {commit.sha}: {e}")

        return {
            "sha": commit.sha,
            "author": author_name,
            "author_name": author_name,
            "author_email": author_email,
            "date": commit.commit.author.date.isoformat() if commit.commit.author and commit.commit.author.date else None,
            "message": commit.commit.message,
            "files_changed": files_changed,
            "lines_added": lines_added,
            "lines_deleted": lines_deleted,
        }

    # -------------------------------------------------------------------------
    # Phase 1.5: Branch and path filtering
    # -------------------------------------------------------------------------

    def fetch_filtered_commits(
        self,
        repo_url: str,
        allowed_branches: Optional[List[str]] = None,
        allowed_paths: Optional[List[str]] = None,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch commits filtered by allowed branches and paths.
        If no branches specified, fetches from default branch only.
        If no paths specified, accepts all commits.

        Args:
            repo_url: Full GitHub URL
            allowed_branches: List of branch names to include (None = all/default)
            allowed_paths: List of path prefixes to include (None = all paths)
            since: Only fetch commits after this datetime

        Returns:
            Deduplicated list of commit dictionaries
        """
        full_name = self._extract_repo_full_name(repo_url)

        try:
            self._check_rate_limit()
            repo = self.client.get_repo(full_name)

            # Determine which branches to fetch
            branches_to_fetch = allowed_branches if allowed_branches else [repo.default_branch]
            if not branches_to_fetch:
                branches_to_fetch = [repo.default_branch]

            logger.info(
                f"Fetching commits from {full_name} for branches: {branches_to_fetch}"
                f"{' with path filters: ' + str(allowed_paths) if allowed_paths else ''}"
            )

            # Fetch commits from each allowed branch, deduplicate by SHA
            all_commits: Dict[str, Dict[str, Any]] = {}

            for branch in branches_to_fetch:
                try:
                    branch_commits = self._fetch_with_retry(repo, since, sha=branch)
                    for commit in branch_commits:
                        sha = commit["sha"]
                        if sha not in all_commits:
                            all_commits[sha] = commit
                except GitHubError as e:
                    logger.warning(f"Failed to fetch commits from branch '{branch}': {e}")
                    continue

            # Filter by path if scopes defined
            if allowed_paths:
                filtered_commits = {}
                for sha, commit in all_commits.items():
                    if self._matches_path_filter(commit.get("files_changed", []), allowed_paths):
                        filtered_commits[sha] = commit
                    else:
                        logger.debug(f"Filtered out commit {sha[:8]} — no matching paths")
                all_commits = filtered_commits

            # Return newest-first (commits from PyGithub are already in reverse chronological order)
            result = list(all_commits.values())
            logger.info(f"Filtered to {len(result)} commits after branch/path filtering")
            return result

        except UnknownObjectException:
            raise GitHubRepoNotFoundError(f"Repository '{full_name}' not found.")
        except GitHubError:
            raise
        except Exception as e:
            raise GitHubError(f"Unexpected error fetching commits: {e}")

    def _fetch_with_retry(
        self,
        repo,
        since: Optional[datetime] = None,
        sha: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch commits from a repository (or specific branch) with retry.

        Args:
            repo: PyGithub Repository object
            since: Only fetch commits after this datetime
            sha: Branch name to fetch from (None = all branches)

        Returns:
            List of commit dictionaries
        """
        commits = []
        try:
            kwargs = {}
            if since:
                kwargs["since"] = since
            if sha:
                kwargs["sha"] = sha

            commit_iterator = repo.get_commits(**kwargs) if kwargs else repo.get_commits()

            for commit in commit_iterator:
                commit_data = self._parse_commit(commit)
                commits.append(commit_data)

        except RateLimitExceededException:
            logger.warning("Rate limit exceeded, retrying...")
            raise
        except GithubException as e:
            raise GitHubError(f"Failed to fetch commits: {e.status} - {e.data.get('message', 'Unknown error')}")

        return commits

    def _matches_path_filter(self, files_changed: List[Dict], allowed_paths: List[str]) -> bool:
        """
        Check if any changed file matches any allowed path prefix.

        Args:
            files_changed: List of {filename, additions, deletions}
            allowed_paths: List of path prefixes (e.g., ['src/auth/', 'lib/'])

        Returns:
            True if at least one file matches an allowed path
        """
        for file_info in files_changed:
            filename = file_info.get("filename", "")
            for path in allowed_paths:
                if filename.startswith(path):
                    return True
        return False
