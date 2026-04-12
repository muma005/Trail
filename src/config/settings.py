"""
Application settings loaded from environment variables.
Uses python-dotenv to load .env file if present.
"""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent.parent.parent / ".env")


class Settings:
    """Central configuration access point. Validates required vars at instantiation."""

    def __init__(self):
        self.database_url: str = os.getenv("DATABASE_URL", "")
        self.redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.github_token: Optional[str] = os.getenv("GITHUB_TOKEN")
        self.notion_token: Optional[str] = os.getenv("NOTION_TOKEN")

    def validate_required(self) -> None:
        """Exit with clear message if any required env var is missing."""
        missing = []
        if not self.database_url:
            missing.append("DATABASE_URL")
        if not self.github_token:
            missing.append("GITHUB_TOKEN")
        if not self.notion_token:
            missing.append("NOTION_TOKEN")

        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                f"Copy .env.example to .env and fill in the values."
            )


# Singleton instance
settings = Settings()
