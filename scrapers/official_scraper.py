"""Official race scraper with purchasable-race filtering."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, List

from scripts.fetch_real_races import BoatraceDataFetcher, save_races_to_db
from utils.race_time import filter_races_by_time, is_race_purchasable


class OfficialRaceScraper:
    """Fetch official race data and keep only purchasable races."""

    def __init__(self) -> None:
        self.fetcher = BoatraceDataFetcher()

    def fetch_races_for_date(
        self,
        target_date: datetime | None = None,
        now: datetime | None = None,
    ) -> List[dict[str, Any]]:
        target_date = target_date or datetime.now()
        races = self.fetcher.fetch_races_for_date(target_date)
        return filter_races_by_time(races, now=now)

    def fetch_today_races(self, now: datetime | None = None) -> List[dict[str, Any]]:
        reference_now = now or datetime.now()
        return self.fetch_races_for_date(reference_now, now=reference_now)

    def fetch_tomorrow_races(self, now: datetime | None = None) -> List[dict[str, Any]]:
        reference_now = now or datetime.now()
        return self.fetch_races_for_date(reference_now + timedelta(days=1), now=reference_now)

    def save_races(self, races: List[dict[str, Any]]) -> int:
        """Persist filtered races to the database."""
        return save_races_to_db(races)


__all__ = ["OfficialRaceScraper", "is_race_purchasable"]
