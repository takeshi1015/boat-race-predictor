"""
API Client
Fetches boat race data from external APIs.
"""

import time
import logging
from datetime import date
from typing import Any, Dict, List, Optional

import requests

from utils.logger import setup_logger

logger = setup_logger(__name__)


class APIClient:
    """Client for fetching boat race data from external APIs.

    This class handles authentication, request retries, and response
    parsing for external boat race data APIs.

    Attributes:
        base_url: Base URL of the external API.
        api_key: API key for authenticated requests.
        timeout: Request timeout in seconds.
        retry_count: Number of retries on transient failures.
        retry_delay: Delay between retries in seconds.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        timeout: int = 30,
        retry_count: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        """Initialize the API client.

        Args:
            base_url: Base URL of the external API.
            api_key: Optional API key for authentication.
            timeout: Request timeout in seconds.
            retry_count: Number of request retries on failure.
            retry_delay: Seconds to wait between retries.
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay

        self._session = requests.Session()
        self._session.headers.update(self._build_headers())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_races(self, target_date: date) -> List[Dict[str, Any]]:
        """Fetch all races scheduled for the given date.

        Args:
            target_date: Date to retrieve races for.

        Returns:
            List of race data dictionaries.
        """
        endpoint = "/races"
        params = {"date": target_date.isoformat()}
        response = self._get(endpoint, params=params)
        if response is None:
            return []
        return response if isinstance(response, list) else response.get("races", [])

    def get_race_detail(
        self, race_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch detailed information for a specific race.

        Args:
            race_id: Unique race identifier.

        Returns:
            Race detail dictionary, or None on failure.
        """
        endpoint = f"/races/{race_id}"
        return self._get(endpoint)

    def get_odds(self, race_id: str) -> Optional[Dict[str, Any]]:
        """Fetch current odds for a specific race.

        Args:
            race_id: Unique race identifier.

        Returns:
            Odds data dictionary, or None on failure.
        """
        endpoint = f"/races/{race_id}/odds"
        return self._get(endpoint)

    def get_results(self, race_id: str) -> Optional[Dict[str, Any]]:
        """Fetch results for a completed race.

        Args:
            race_id: Unique race identifier.

        Returns:
            Results data dictionary, or None on failure.
        """
        endpoint = f"/races/{race_id}/results"
        return self._get(endpoint)

    def get_rider(self, rider_id: str) -> Optional[Dict[str, Any]]:
        """Fetch statistics for a specific rider.

        Args:
            rider_id: Unique rider identifier.

        Returns:
            Rider data dictionary, or None on failure.
        """
        endpoint = f"/riders/{rider_id}"
        return self._get(endpoint)

    def get_boat(self, boat_id: str) -> Optional[Dict[str, Any]]:
        """Fetch information for a specific boat.

        Args:
            boat_id: Unique boat identifier.

        Returns:
            Boat data dictionary, or None on failure.
        """
        endpoint = f"/boats/{boat_id}"
        return self._get(endpoint)

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers including authentication.

        Returns:
            Dictionary of HTTP headers.
        """
        headers: Dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        return headers

    def _get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """Perform a GET request with retry logic.

        Args:
            endpoint: API endpoint path (will be appended to base_url).
            params: Optional query parameters.

        Returns:
            Parsed JSON response, or None if all retries fail.
        """
        url = f"{self.base_url}{endpoint}"

        for attempt in range(1, self.retry_count + 1):
            try:
                response = self._session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                logger.warning(
                    "HTTP %s from %s (attempt %d/%d)",
                    status,
                    url,
                    attempt,
                    self.retry_count,
                )
                # Do not retry on client errors
                if status is not None and 400 <= status < 500:
                    return None
            except requests.RequestException as exc:
                logger.warning(
                    "Request to %s attempt %d/%d failed: %s",
                    url,
                    attempt,
                    self.retry_count,
                    exc,
                )

            if attempt < self.retry_count:
                time.sleep(self.retry_delay)

        logger.error("All %d attempts failed for %s", self.retry_count, url)
        return None
