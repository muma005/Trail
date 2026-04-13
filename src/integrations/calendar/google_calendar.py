"""
Google Calendar integration (read-only).
Phase 6.5: Fetches events, caches in Redis, provides busy slots for planner.
"""
import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import redis

from src.config.settings import settings

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 3600  # 1 hour
CACHE_PREFIX = "calendar:events"


class GoogleCalendarClient:
    """
    Read-only Google Calendar client.
    Uses service account or OAuth credentials from .env.
    """

    def __init__(self):
        self._service = None
        self._redis = None

    def _get_redis(self) -> Optional[redis.Redis]:
        """Get Redis client for caching."""
        if self._redis is None:
            try:
                self._redis = redis.Redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                )
                self._redis.ping()
            except Exception as e:
                logger.warning(f"Redis unavailable for calendar cache: {e}")
                self._redis = None
        return self._redis

    def authenticate(self) -> bool:
        """
        Authenticate with Google Calendar API.
        Returns True if successful, False if credentials not configured.
        """
        if self._service is not None:
            return True

        # Check if we have credentials
        creds_file = getattr(settings, 'google_calendar_credentials', None)
        if not creds_file:
            logger.warning("Google Calendar credentials not configured")
            return False

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
            credentials = service_account.Credentials.from_service_account_file(
                creds_file, scopes=scopes
            )
            self._service = build("calendar", "v3", credentials=credentials)
            return True
        except ImportError:
            logger.error(
                "Google API libraries not installed. "
                "Run: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2"
            )
            return False
        except Exception as e:
            logger.error(f"Google Calendar authentication failed: {e}")
            return False

    def fetch_events(
        self,
        calendar_id: str = "primary",
        days_ahead: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Fetch calendar events for the next N days.

        Args:
            calendar_id: Calendar ID ('primary' for default)
            days_ahead: How many days ahead to fetch

        Returns:
            List of event dicts with start, end, summary
        """
        # Try cache first
        redis_client = self._get_redis()
        today = date.today().isoformat()
        cache_key = f"{CACHE_PREFIX}:{calendar_id}:{today}:{days_ahead}"

        if redis_client:
            cached = redis_client.get(cache_key)
            if cached:
                logger.info("Calendar events cache hit")
                return json.loads(cached)

        if not self.authenticate():
            return []

        try:
            time_min = datetime.now().isoformat() + "Z"
            time_max = (datetime.now() + timedelta(days=days_ahead)).isoformat() + "Z"

            result = self._service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            events = result.get("items", [])
            parsed = []

            for event in events:
                start = event["start"].get("dateTime", event["start"].get("date"))
                end = event["end"].get("dateTime", event["end"].get("date"))

                parsed.append({
                    "summary": event.get("summary", "No title"),
                    "start": start,
                    "end": end,
                    "location": event.get("location", ""),
                })

            # Cache results
            if redis_client and parsed:
                redis_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(parsed, default=str))

            logger.info(f"Fetched {len(parsed)} calendar events")
            return parsed

        except Exception as e:
            logger.error(f"Failed to fetch calendar events: {e}")
            return []

    def get_busy_slots_for_date(self, target_date: date, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """
        Get busy time slots for a specific date.

        Args:
            target_date: The date to check
            days_ahead: How many days ahead to fetch (must cover target_date)

        Returns:
            List of dicts with start_time, end_time, summary
        """
        events = self.fetch_events(days_ahead=days_ahead)
        busy = []

        for event in events:
            try:
                start = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(event["end"].replace("Z", "+00:00"))
                event_date = start.date()

                if event_date == target_date:
                    busy.append({
                        "start": start,
                        "end": end,
                        "summary": event["summary"],
                    })
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse event time: {e}")
                continue

        return busy
