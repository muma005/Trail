"""
Base connector class for external APIs.
Provides common functionality: timeout handling, error formatting, and retry logic.
"""
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.utils.exceptions.base import TrailError


class BaseConnector(ABC):
    """
    Abstract base for all API connectors (GitHub, Notion, Calendar, etc.).
    Enforces a consistent interface for authentication, validation, and requests.
    """

    def __init__(self, token: str, timeout: int = 30):
        """
        Initialize connector with authentication token.

        Args:
            token: API token for the service
            timeout: Request timeout in seconds
        """
        self.token = token
        self.timeout = timeout
        self._client = None

    @abstractmethod
    def authenticate(self) -> Any:
        """
        Authenticate with the external service.
        Returns the authenticated client object.
        """
        pass

    @abstractmethod
    def validate_access(self, identifier: str) -> bool:
        """
        Verify that the token can access a specific resource.

        Args:
            identifier: Resource identifier (repo URL, database ID, etc.)

        Returns:
            True if accessible, raises specific error otherwise
        """
        pass

    @property
    def client(self) -> Any:
        """Lazy-loaded authenticated client."""
        if self._client is None:
            self._client = self.authenticate()
        return self._client

    def _handle_api_error(self, error: Exception, context: str = "") -> None:
        """
        Centralized error handler that formats API errors consistently.

        Args:
            error: The caught exception
            context: Description of what was being attempted
        """
        raise TrailError(
            f"API error during {context}: {error}"
        )

    def _retry_with_backoff(
        self,
        func,
        max_retries: int = 3,
        base_delay: float = 1.0,
        *args,
        **kwargs,
    ) -> Any:
        """
        Retry a function with exponential backoff.

        Args:
            func: Function to retry
            max_retries: Maximum number of retries
            base_delay: Initial delay between retries (doubles each retry)
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
        raise last_error
