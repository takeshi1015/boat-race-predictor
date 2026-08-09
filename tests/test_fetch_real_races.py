"""Tests for scripts/fetch_real_races.py."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from scripts.fetch_real_races import BoatraceDataFetcher


TARGET_DATE = datetime(2026, 8, 9)
DATE_STR = "20260809"


def _response(html: str) -> MagicMock:
    resp = MagicMock()
    resp.text = html
    resp.status_code = 200
    return resp


def test_fetch_active_venues_extracts_target_codes():
    fetcher = BoatraceDataFetcher()
    html = f"""
    <a href="/owpc/pc/race/racelist?hd={DATE_STR}&jcd=07">戸田</a>
    <a href="/owpc/pc/race/racelist?hd={DATE_STR}&jcd=08">江戸川</a>
    <a href="/owpc/pc/race/racelist?hd={DATE_STR}&jcd=99">対象外</a>
    """
    with patch.object(fetcher, "_request_with_retry", return_value=_response(html)):
        venues = fetcher._fetch_active_venues(TARGET_DATE)
    assert venues == ["07", "08"]


def test_fetch_active_venues_falls_back_when_unavailable():
    fetcher = BoatraceDataFetcher()
    with patch.object(fetcher, "_request_with_retry", return_value=None):
        venues = fetcher._fetch_active_venues(TARGET_DATE)
    assert "07" in venues
    assert "08" in venues


def test_fetch_race_parses_time_entries_and_odds():
    fetcher = BoatraceDataFetcher()
    race_html = """
    <html>
      <span class="is-time">11:23</span>
      <table>
        <tr><td>1</td><td><a>選手A</a></td></tr>
        <tr><td>2</td><td><a>選手B</a></td></tr>
        <tr><td>3</td><td><a>選手C</a></td></tr>
        <tr><td>4</td><td><a>選手D</a></td></tr>
        <tr><td>5</td><td><a>選手E</a></td></tr>
        <tr><td>6</td><td><a>選手F</a></td></tr>
      </table>
    </html>
    """
    with patch.object(fetcher, "_request_with_retry", return_value=_response(race_html)), patch.object(
        fetcher, "_fetch_odds", return_value={"1-2-3": 12.3}
    ):
        race = fetcher._fetch_race("07", 1, TARGET_DATE)

    assert race is not None
    assert race["race_number"] == 1
    assert race["place"] == "戸田"
    assert race["result"]["race_time"] == "11:23"
    assert len(race["result"]["participants"]) == 6
    assert race["result"]["odds"]["1-2-3"] == 12.3


def test_fetch_races_for_date_uses_active_venues():
    fetcher = BoatraceDataFetcher()
    with patch.object(fetcher, "_fetch_active_venues", return_value=["07"]), patch.object(
        fetcher, "_fetch_race", return_value={"race_id": "x"}
    ) as fetch_mock:
        races = fetcher.fetch_races_for_date(TARGET_DATE)
    assert len(races) == 12
    assert fetch_mock.call_count == 12
