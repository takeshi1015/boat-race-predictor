"""Official boatrace.jp scraper for recent results and today's races."""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup


def _get_logger() -> logging.Logger:
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger("predictor")
    logger.setLevel(logging.INFO)
    if not any(isinstance(h, logging.FileHandler) and h.baseFilename.endswith("predictor.log") for h in logger.handlers):
        handler = logging.FileHandler("logs/predictor.log", encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        )
        logger.addHandler(handler)
    return logger


class OfficialRaceScraper:
    """Scrape official race/result data from boatrace.jp."""

    BASE_URL = "https://www.boatrace.jp"
    VENUE_CODES = [f"{i:02d}" for i in range(1, 22)]

    def __init__(self, delay_seconds: float = 0.4, request_timeout: int = 5, max_failures: int = 12):
        self.delay_seconds = max(0.0, delay_seconds)
        self.request_timeout = max(1, request_timeout)
        self.max_failures = max(1, max_failures)
        self.logger = _get_logger()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
                )
            }
        )

    def fetch_today_races(self) -> List[Dict[str, Any]]:
        """Fetch race cards (entries + conditions) for today."""
        return self.fetch_races_for_date(datetime.now(), include_results=False)

    def fetch_past_results(self, days: int = 7) -> List[Dict[str, Any]]:
        """Fetch race results for the past N days (excluding today)."""
        races: List[Dict[str, Any]] = []
        for diff in range(1, days + 1):
            target = datetime.now() - timedelta(days=diff)
            races.extend(self.fetch_races_for_date(target, include_results=True))
        return races

    def fetch_recent_with_today(self, days: int = 7) -> List[Dict[str, Any]]:
        """Fetch today + past N days of result pages."""
        races: List[Dict[str, Any]] = []
        for diff in range(0, days + 1):
            target = datetime.now() - timedelta(days=diff)
            races.extend(self.fetch_races_for_date(target, include_results=True))
        return races

    def fetch_races_for_date(self, target_date: datetime, include_results: bool) -> List[Dict[str, Any]]:
        races: List[Dict[str, Any]] = []
        date_str = target_date.strftime("%Y%m%d")
        failure_count = 0
        for venue_code in self.VENUE_CODES:
            for race_no in range(1, 13):
                try:
                    race = self._fetch_race_page(date_str, venue_code, race_no, include_results)
                    if race and race.get("entries"):
                        races.append(race)
                    else:
                        failure_count += 1
                except Exception as exc:
                    failure_count += 1
                    self.logger.error(
                        "scrape failed: date=%s venue=%s race=%s err=%s",
                        date_str,
                        venue_code,
                        race_no,
                        exc,
                    )
                finally:
                    if self.delay_seconds > 0:
                        time.sleep(self.delay_seconds)
                if failure_count >= self.max_failures and not races:
                    self.logger.error("scrape aborted early after repeated failures: date=%s", date_str)
                    return races
        return races

    def _fetch_race_page(
        self, date_str: str, venue_code: str, race_no: int, include_results: bool
    ) -> Dict[str, Any] | None:
        path = "raceresult" if include_results else "racelist"
        url = f"{self.BASE_URL}/owpc/pc/race/{path}"
        params = {"rno": race_no, "jcd": venue_code, "hd": date_str}
        response = self.session.get(url, params=params, timeout=self.request_timeout)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        title_text = soup.get_text(" ", strip=True)
        if "BOAT RACE" not in title_text and "ボートレース" not in title_text:
            return None

        weather = self._extract_condition_text(soup, ["天候", "weather"])
        water_surface = self._extract_condition_text(soup, ["波", "水面", "wind wave"])

        entries = self._parse_entries(soup)
        if not entries:
            return None

        result_order = self._parse_result_order(soup) if include_results else []
        if include_results and not result_order:
            # Skip unfinished races for training data quality.
            return None

        return {
            "race_id": f"{date_str}_{venue_code}_{race_no:02d}",
            "date": date_str,
            "venue_code": venue_code,
            "race_number": race_no,
            "weather": weather,
            "water_surface": water_surface,
            "entries": entries,
            "result_order": result_order,
        }

    @staticmethod
    def _extract_condition_text(soup: BeautifulSoup, labels: List[str]) -> str:
        text = soup.get_text(" ", strip=True)
        for label in labels:
            m = re.search(rf"{re.escape(label)}\s*[:：]?\s*([^\s]+)", text, re.IGNORECASE)
            if m:
                return m.group(1)
        return "unknown"

    def _parse_entries(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        rows = soup.select("table tbody tr")
        for row in rows:
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) < 2:
                continue

            lane_match = re.match(r"^[1-6]$", cells[0])
            if not lane_match:
                continue

            lane = int(lane_match.group(0))
            player_name = cells[1]
            player_id = self._extract_player_id(row)

            numeric_text = " ".join(cells)
            wins = re.findall(r"\d+\.\d+", numeric_text)
            win_rate = float(wins[0]) if len(wins) > 0 else 0.0
            motor_rate = float(wins[1]) if len(wins) > 1 else win_rate
            venue_rate = float(wins[2]) if len(wins) > 2 else win_rate

            entries.append(
                {
                    "lane": lane,
                    "player_id": player_id or f"unknown_{lane}",
                    "player_name": player_name,
                    "win_rate": win_rate,
                    "motor_rate": motor_rate,
                    "venue_rate": venue_rate,
                }
            )
        return entries

    @staticmethod
    def _extract_player_id(row) -> str:
        for a_tag in row.find_all("a", href=True):
            href = a_tag.get("href", "")
            match = re.search(r"toban=(\d+)", href)
            if match:
                return match.group(1)
        return ""

    def _parse_result_order(self, soup: BeautifulSoup) -> List[int]:
        text = soup.get_text(" ", strip=True)
        # 1着 2, 2着 1, 3着 3 など
        first = re.search(r"1着\s*([1-6])", text)
        second = re.search(r"2着\s*([1-6])", text)
        third = re.search(r"3着\s*([1-6])", text)
        if first and second and third:
            return [int(first.group(1)), int(second.group(1)), int(third.group(1))]

        # フォールバック: 結果表の先頭3行
        rows = soup.select("table tbody tr")
        ranking: List[int] = []
        for row in rows:
            cols = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            if len(cols) < 2:
                continue
            if re.match(r"^[1-3]$", cols[0]) and re.match(r"^[1-6]$", cols[1]):
                ranking.append(int(cols[1]))
            if len(ranking) >= 3:
                break
        return ranking[:3]
