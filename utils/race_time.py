"""Race time filtering helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, List

BUSINESS_START_HOUR = 6
BUSINESS_END_HOUR = 22
BUSINESS_END_MINUTE = 50
PURCHASABLE_LEAD_MINUTES = 10


def is_race_in_business_hours(race_time: datetime) -> bool:
    """Return whether the race time is within allowed business hours."""
    if race_time.hour < BUSINESS_START_HOUR:
        return False
    if race_time.hour > BUSINESS_END_HOUR:
        return False
    if race_time.hour == BUSINESS_END_HOUR and race_time.minute > BUSINESS_END_MINUTE:
        return False
    return True


def is_race_purchasable(
    race_time: datetime,
    race_date: datetime,
    now: datetime | None = None,
) -> bool:
    """
    レースが購入可能かどうかを判定
    - 当日レース: 現在時刻から10分以上先 かつ 22:50以前
    - 翌日以降レース: 22:50以前
    """
    now = now or datetime.now()

    if not is_race_in_business_hours(race_time):
        return False

    if race_date.date() == now.date():
        time_until_race = (race_time - now).total_seconds() / 60
        return time_until_race >= PURCHASABLE_LEAD_MINUTES

    return race_date.date() > now.date()


def get_race_datetime(race: Any) -> datetime | None:
    """Extract a race datetime from a dict-like or object-like race."""
    if isinstance(race, dict):
        value = race.get("date")
    else:
        value = getattr(race, "date", None)

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    return None


def filter_races_by_time(races: Iterable[Any], now: datetime | None = None) -> List[Any]:
    """Return only races that are still displayable/purchasable."""
    now = now or datetime.now()
    filtered: List[Any] = []

    for race in races:
        race_datetime = get_race_datetime(race)
        if race_datetime and is_race_purchasable(race_datetime, race_datetime, now=now):
            filtered.append(race)

    return filtered
