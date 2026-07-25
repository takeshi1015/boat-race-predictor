"""
Web Scraper
Collects boat race data from official and third-party websites.
"""

import time
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from utils.logger import setup_logger

logger = setup_logger(__name__)

_DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; BoatRacePredictor/1.0; "
        "+https://github.com/takeshi1015/boat-race-predictor)"
    ),
    "Accept-Language": "ja,en;q=0.9",
}

_BOATRACE_BASE_URL = "https://boatrace.jp"


class WebScraper:
    """Web scraper for collecting boat race data.

    This class provides methods to fetch race schedules, race details,
    odds, and historical results from the official boat race website.

    Attributes:
        base_url: Base URL of the target website.
        timeout: Request timeout in seconds.
        retry_count: Number of retries on failure.
        retry_delay: Delay between retries in seconds.
    """

    def __init__(
        self,
        base_url: str = _BOATRACE_BASE_URL,
        timeout: int = 30,
        retry_count: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        """Initialize the web scraper.

        Args:
            base_url: Base URL of the target website.
            timeout: Request timeout in seconds.
            retry_count: Number of request retries on failure.
            retry_delay: Seconds to wait between retries.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self._session = requests.Session()
        self._session.headers.update(_DEFAULT_HEADERS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_race_schedule(self, target_date: date) -> List[Dict[str, Any]]:
        """Fetch the race schedule for the given date.

        Args:
            target_date: The date to retrieve races for.

        Returns:
            List of race dictionaries with basic schedule information.
        """
        url = f"{self.base_url}/race/index"
        params = {"hd": target_date.strftime("%Y%m%d")}

        html = self._get(url, params=params)
        if html is None:
            return []

        return self._parse_schedule(html, target_date)

    def fetch_race_details(
        self, location_code: str, race_number: int, target_date: date
    ) -> Optional[Dict[str, Any]]:
        """Fetch detailed information for a specific race.

        Args:
            location_code: Venue code (e.g. '01').
            race_number: Race number at the venue (1–12).
            target_date: Date of the race.

        Returns:
            Dictionary of race details, or None on failure.
        """
        url = f"{self.base_url}/race/racelist"
        params = {
            "rno": race_number,
            "jcd": location_code,
            "hd": target_date.strftime("%Y%m%d"),
        }

        html = self._get(url, params=params)
        if html is None:
            return None

        return self._parse_race_details(html, location_code, race_number, target_date)

    def fetch_odds(
        self, location_code: str, race_number: int, target_date: date
    ) -> Optional[Dict[str, Any]]:
        """Fetch current odds for a specific race.

        Args:
            location_code: Venue code (e.g. '01').
            race_number: Race number at the venue (1–12).
            target_date: Date of the race.

        Returns:
            Dictionary of odds data, or None on failure.
        """
        url = f"{self.base_url}/race/odds"
        params = {
            "rno": race_number,
            "jcd": location_code,
            "hd": target_date.strftime("%Y%m%d"),
        }

        html = self._get(url, params=params)
        if html is None:
            return None

        return self._parse_odds(html)

    def fetch_results(
        self, location_code: str, race_number: int, target_date: date
    ) -> Optional[Dict[str, Any]]:
        """Fetch official results for a completed race.

        Args:
            location_code: Venue code (e.g. '01').
            race_number: Race number at the venue (1–12).
            target_date: Date of the race.

        Returns:
            Dictionary of result data, or None on failure.
        """
        url = f"{self.base_url}/race/result"
        params = {
            "rno": race_number,
            "jcd": location_code,
            "hd": target_date.strftime("%Y%m%d"),
        }

        html = self._get(url, params=params)
        if html is None:
            return None

        return self._parse_results(html)

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Perform a GET request with retry logic.

        Args:
            url: Target URL.
            params: Optional query parameters.

        Returns:
            Response text, or None if all retries fail.
        """
        for attempt in range(1, self.retry_count + 1):
            try:
                response = self._session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                response.encoding = response.apparent_encoding
                return response.text
            except requests.RequestException as exc:
                logger.warning(
                    "GET %s attempt %d/%d failed: %s",
                    url,
                    attempt,
                    self.retry_count,
                    exc,
                )
                if attempt < self.retry_count:
                    time.sleep(self.retry_delay)

        logger.error("All %d attempts failed for %s", self.retry_count, url)
        return None

    def _parse_schedule(
        self, html: str, target_date: date
    ) -> List[Dict[str, Any]]:
        """Parse the race schedule page.

        Args:
            html: Raw HTML of the schedule page.
            target_date: Date being parsed.

        Returns:
            List of race schedule dictionaries.
        """
        races: List[Dict[str, Any]] = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            race_rows = soup.find_all("tr", class_="is-race")
            for row in race_rows:
                race = self._parse_schedule_row(row, target_date)
                if race:
                    races.append(race)
        except Exception as exc:
            logger.error("Error parsing schedule: %s", exc)
        return races

    def _parse_schedule_row(
        self, row: Any, target_date: date
    ) -> Optional[Dict[str, Any]]:
        """Parse a single row from the race schedule table.

        Args:
            row: BeautifulSoup tag for the table row.
            target_date: Date of the races.

        Returns:
            Race information dictionary, or None if parsing fails.
        """
        try:
            race: Dict[str, Any] = {"race_date": target_date.isoformat()}

            location_cell = row.find("td", class_="is-jcd")
            if location_cell:
                race["location_code"] = location_cell.get_text(strip=True)

            race_no_cell = row.find("td", class_="is-rno")
            if race_no_cell:
                race["race_number"] = int(race_no_cell.get_text(strip=True))

            return race if len(race) > 1 else None
        except Exception as exc:
            logger.debug("Error parsing schedule row: %s", exc)
            return None

    def _parse_race_details(
        self,
        html: str,
        location_code: str,
        race_number: int,
        target_date: date,
    ) -> Optional[Dict[str, Any]]:
        """Parse the race detail page.

        Args:
            html: Raw HTML of the race detail page.
            location_code: Venue code.
            race_number: Race number.
            target_date: Date of the race.

        Returns:
            Race detail dictionary, or None on parse error.
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            details: Dict[str, Any] = {
                "location_code": location_code,
                "race_number": race_number,
                "race_date": target_date.isoformat(),
                "entries": [],
            }

            runner_rows = soup.find_all("tr", class_="is-runner")
            for row in runner_rows:
                entry = self._parse_runner_row(row)
                if entry:
                    details["entries"].append(entry)

            return details
        except Exception as exc:
            logger.error("Error parsing race details: %s", exc)
            return None

    def _parse_runner_row(self, row: Any) -> Optional[Dict[str, Any]]:
        """Parse a single runner row from the race detail table.

        Args:
            row: BeautifulSoup tag for the runner row.

        Returns:
            Entry dictionary, or None if parsing fails.
        """
        try:
            entry: Dict[str, Any] = {}

            frame_cell = row.find("td", class_="txt-frame")
            if frame_cell:
                entry["frame_number"] = int(frame_cell.get_text(strip=True))

            rider_link = row.find("a", class_="txt-rider")
            if rider_link:
                entry["rider_name"] = rider_link.get_text(strip=True)
                href = rider_link.get("href", "")
                entry["rider_id"] = href.split("/")[-1]

            return entry if entry else None
        except Exception as exc:
            logger.debug("Error parsing runner row: %s", exc)
            return None

    def _parse_odds(self, html: str) -> Optional[Dict[str, Any]]:
        """Parse the odds page.

        Args:
            html: Raw HTML of the odds page.

        Returns:
            Odds dictionary, or None on parse error.
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            odds: Dict[str, Any] = {}

            odds_table = soup.find("table", class_="odds-table")
            if odds_table:
                for row in odds_table.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        combination = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        try:
                            odds[combination] = float(value)
                        except ValueError:
                            pass

            return odds
        except Exception as exc:
            logger.error("Error parsing odds: %s", exc)
            return None

    def _parse_results(self, html: str) -> Optional[Dict[str, Any]]:
        """Parse the results page.

        Args:
            html: Raw HTML of the results page.

        Returns:
            Results dictionary, or None on parse error.
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            results: Dict[str, Any] = {"finishing_order": [], "payouts": {}}

            result_rows = soup.find_all("tr", class_="is-result")
            for i, row in enumerate(result_rows, start=1):
                entry = {"position": i}
                rider_cell = row.find("td", class_="is-rider")
                if rider_cell:
                    entry["rider_name"] = rider_cell.get_text(strip=True)
                results["finishing_order"].append(entry)

            return results
        except Exception as exc:
            logger.error("Error parsing results: %s", exc)
            return None
