"""Tests for scripts/fetch_real_races.py – BoatraceDataFetcher."""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.fetch_real_races import BoatraceDataFetcher


TARGET_DATE = datetime(2026, 8, 2)
DATE_STR = "20260802"


# ---------------------------------------------------------------------------
# _fetch_active_venues – network error / fallback
# ---------------------------------------------------------------------------

class TestFetchActiveVenuesFallback:
    """_fetch_active_venues falls back to all venues when the site is unreachable."""

    def test_network_error_returns_all_venues(self):
        fetcher = BoatraceDataFetcher()
        with patch.object(fetcher.session, "get", side_effect=Exception("Connection refused")):
            result = fetcher._fetch_active_venues(TARGET_DATE)

        assert sorted(result) == sorted(fetcher.VENUES.keys())

    def test_non_200_returns_all_venues(self):
        fetcher = BoatraceDataFetcher()
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch.object(fetcher.session, "get", return_value=mock_resp):
            result = fetcher._fetch_active_venues(TARGET_DATE)

        assert sorted(result) == sorted(fetcher.VENUES.keys())

    def test_empty_page_returns_all_venues(self):
        """200 response with no matching links → fallback to all venues."""
        fetcher = BoatraceDataFetcher()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"<html><body><p>no links</p></body></html>"
        mock_resp.encoding = "utf-8"
        with patch.object(fetcher.session, "get", return_value=mock_resp):
            result = fetcher._fetch_active_venues(TARGET_DATE)

        assert sorted(result) == sorted(fetcher.VENUES.keys())


# ---------------------------------------------------------------------------
# _fetch_active_venues – successful parse
# ---------------------------------------------------------------------------

class TestFetchActiveVenuesParse:
    """_fetch_active_venues extracts only the venues that race on the target date."""

    def _make_response(self, html: str) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = html.encode("utf-8")
        mock_resp.encoding = "utf-8"
        return mock_resp

    def test_extracts_correct_venue_codes(self):
        fetcher = BoatraceDataFetcher()
        html = f"""
        <html><body>
            <a href="/owpc/pc/race/racelist?hd={DATE_STR}&jcd=01">桐生</a>
            <a href="/owpc/pc/race/racelist?hd={DATE_STR}&jcd=05">鳴門</a>
            <a href="/owpc/pc/race/racelist?hd={DATE_STR}&jcd=13">三国</a>
        </body></html>
        """
        with patch.object(fetcher.session, "get", return_value=self._make_response(html)):
            result = fetcher._fetch_active_venues(TARGET_DATE)

        assert result == ["01", "05", "13"]

    def test_ignores_other_dates(self):
        """Links for dates other than the target date must be excluded."""
        fetcher = BoatraceDataFetcher()
        html = f"""
        <html><body>
            <a href="/owpc/pc/race/racelist?hd={DATE_STR}&jcd=01">桐生(対象日)</a>
            <a href="/owpc/pc/race/racelist?hd=20260803&jcd=02">平和島(翌日)</a>
        </body></html>
        """
        with patch.object(fetcher.session, "get", return_value=self._make_response(html)):
            result = fetcher._fetch_active_venues(TARGET_DATE)

        assert result == ["01"]
        assert "02" not in result

    def test_deduplicates_venue_codes(self):
        """Duplicate venue links should only appear once in the result."""
        fetcher = BoatraceDataFetcher()
        html = f"""
        <html><body>
            <a href="/owpc/pc/race/racelist?hd={DATE_STR}&jcd=01">桐生 1R</a>
            <a href="/owpc/pc/race/racelist?hd={DATE_STR}&jcd=01">桐生 2R</a>
        </body></html>
        """
        with patch.object(fetcher.session, "get", return_value=self._make_response(html)):
            result = fetcher._fetch_active_venues(TARGET_DATE)

        assert result.count("01") == 1

    def test_ignores_unknown_venue_codes(self):
        """Venue codes not present in VENUES dict should be ignored."""
        fetcher = BoatraceDataFetcher()
        html = f"""
        <html><body>
            <a href="/owpc/pc/race/racelist?hd={DATE_STR}&jcd=99">存在しない会場</a>
            <a href="/owpc/pc/race/racelist?hd={DATE_STR}&jcd=01">桐生</a>
        </body></html>
        """
        with patch.object(fetcher.session, "get", return_value=self._make_response(html)):
            result = fetcher._fetch_active_venues(TARGET_DATE)

        assert result == ["01"]
        assert "99" not in result

    def test_result_is_sorted(self):
        fetcher = BoatraceDataFetcher()
        html = f"""
        <html><body>
            <a href="/owpc/pc/race/racelist?hd={DATE_STR}&jcd=13">三国</a>
            <a href="/owpc/pc/race/racelist?hd={DATE_STR}&jcd=01">桐生</a>
            <a href="/owpc/pc/race/racelist?hd={DATE_STR}&jcd=05">鳴門</a>
        </body></html>
        """
        with patch.object(fetcher.session, "get", return_value=self._make_response(html)):
            result = fetcher._fetch_active_venues(TARGET_DATE)

        assert result == sorted(result)


# ---------------------------------------------------------------------------
# _generate_all_venues_races – venue_codes filtering
# ---------------------------------------------------------------------------

class TestGenerateAllVenuesRaces:
    """_generate_all_venues_races respects the optional venue_codes filter."""

    def test_filtered_venues_only(self):
        fetcher = BoatraceDataFetcher()
        venue_codes = ["01", "05", "13"]  # 桐生、鳴門、三国
        races = fetcher._generate_all_venues_races(TARGET_DATE, venue_codes)

        venue_names = {r["venue"] for r in races}
        assert venue_names == {"桐生", "鳴門", "三国"}
        # 12 races per venue
        assert len(races) == 36

    def test_no_filter_generates_all_venues(self):
        fetcher = BoatraceDataFetcher()
        races = fetcher._generate_all_venues_races(TARGET_DATE)

        venue_names = {r["venue"] for r in races}
        assert venue_names == set(fetcher.VENUES.values())

    def test_empty_list_generates_no_races(self):
        fetcher = BoatraceDataFetcher()
        races = fetcher._generate_all_venues_races(TARGET_DATE, [])

        assert races == []


# ---------------------------------------------------------------------------
# fetch_races_for_date – integration of _fetch_active_venues
# ---------------------------------------------------------------------------

class TestFetchRacesForDate:
    """fetch_races_for_date uses _fetch_active_venues to limit venues."""

    def test_uses_active_venues_only(self):
        fetcher = BoatraceDataFetcher()
        active = ["01", "13"]  # 桐生、三国 only

        with patch.object(fetcher, "_fetch_active_venues", return_value=active):
            races = fetcher.fetch_races_for_date(TARGET_DATE)

        venue_names = {r["venue"] for r in races}
        assert venue_names == {"桐生", "三国"}
        assert len(races) == 24  # 2 venues × 12 races

    def test_fallback_all_venues_on_error(self):
        """When _fetch_active_venues falls back to all venues, all races are generated."""
        fetcher = BoatraceDataFetcher()
        all_codes = sorted(fetcher.VENUES.keys())

        with patch.object(fetcher, "_fetch_active_venues", return_value=all_codes):
            races = fetcher.fetch_races_for_date(TARGET_DATE)

        venue_names = {r["venue"] for r in races}
        assert venue_names == set(fetcher.VENUES.values())
