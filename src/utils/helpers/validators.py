"""Validation helpers for user input and API responses."""
import re
from urllib.parse import urlparse

from src.utils.exceptions.base import ValidationError


def validate_github_url(url: str) -> str:
    """
    Validate and normalize a GitHub repository URL.
    Accepts full URLs (https://github.com/owner/repo) and shorthand (owner/repo).
    Returns the full URL if valid, raises ValidationError otherwise.
    """
    if not url:
        raise ValidationError("GitHub URL cannot be empty.")

    # Handle shorthand format: owner/repo
    if not url.startswith(("http://", "https://")):
        if not re.match(r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$", url):
            raise ValidationError(
                f"Invalid GitHub repository format: '{url}'.\n"
                "Use format: https://github.com/owner/repo  OR  owner/repo"
            )
        return f"https://github.com/{url}"

    parsed = urlparse(url)
    if parsed.netloc != "github.com":
        raise ValidationError(
            f"Invalid GitHub URL: '{url}'.\n"
            "URL must be from github.com domain."
        )

    # Path should be /owner/repo (possibly with trailing .git)
    path = parsed.path.rstrip("/").removesuffix(".git")
    parts = path.strip("/").split("/")
    if len(parts) != 2:
        raise ValidationError(
            f"Invalid GitHub repository: '{url}'.\n"
            "Expected format: https://github.com/owner/repo"
        )

    return f"https://github.com/{parts[0]}/{parts[1]}"


def validate_notion_database_id(db_id: str) -> str:
    """
    Validate that a Notion database ID looks like a valid UUID/hex string.
    Notion DB IDs are 32-character hex strings (with or without dashes).
    """
    if not db_id:
        raise ValidationError("Notion database ID cannot be empty.")

    # Remove dashes and spaces for normalization
    cleaned = db_id.replace("-", "").replace(" ", "")

    # Notion IDs are typically 32 hex chars, but can vary slightly
    if not re.match(r"^[a-fA-F0-9]{32}$", cleaned):
        raise ValidationError(
            f"Invalid Notion database ID: '{db_id}'.\n"
            "Expected a 32-character hex string (with or without dashes)."
        )

    return cleaned


def validate_project_key(key: str) -> str:
    """Validate project key format: uppercase alphanumeric with hyphens."""
    if not key:
        raise ValidationError("Project key cannot be empty.")

    if not re.match(r"^[A-Z0-9][A-Z0-9-]{1,49}$", key):
        raise ValidationError(
            f"Invalid project key: '{key}'.\n"
            "Key must start with a letter/number, contain only uppercase letters, "
            "numbers, and hyphens (max 50 chars). Example: AUTH-01"
        )

    return key


def validate_project_name(name: str) -> str:
    """Validate project name is non-empty and reasonable length."""
    if not name or not name.strip():
        raise ValidationError("Project name cannot be empty.")
    if len(name) > 255:
        raise ValidationError(
            f"Project name too long ({len(name)} chars, max 255)."
        )
    return name.strip()
