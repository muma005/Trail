"""Custom exception hierarchy for Trail."""


class TrailError(Exception):
    """Base exception for all Trail errors."""
    pass


class ValidationError(TrailError):
    """Raised when input validation fails."""
    pass


class GitHubError(TrailError):
    """Raised when GitHub API interaction fails."""
    pass


class GitHubRepoNotFoundError(GitHubError):
    """Raised when a GitHub repository is not found."""
    pass


class NotionError(TrailError):
    """Raised when Notion API interaction fails."""
    pass


class NotionDatabaseNotFoundError(NotionError):
    """Raised when a Notion database is not found or inaccessible."""
    pass


class DatabaseError(TrailError):
    """Raised when database operations fail."""
    pass


class DuplicateProjectError(DatabaseError):
    """Raised when a project with the same GitHub URL or Notion DB already exists."""
    pass
