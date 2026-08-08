"""Tests for scrapers/official_scraper.py."""

from bs4 import BeautifulSoup

from scrapers.official_scraper import OfficialRaceScraper


def test_parse_entries_and_result_order():
    html = """
    <html><body>
      <table><tbody>
        <tr><td>1</td><td>選手A</td><td><a href='/foo?toban=1001'>詳細</a></td><td>6.20</td><td>5.80</td><td>6.00</td></tr>
        <tr><td>2</td><td>選手B</td><td><a href='/foo?toban=1002'>詳細</a></td><td>5.90</td><td>5.20</td><td>5.30</td></tr>
        <tr><td>3</td><td>選手C</td><td><a href='/foo?toban=1003'>詳細</a></td><td>5.50</td><td>5.00</td><td>5.10</td></tr>
      </tbody></table>
      <div>1着 2 2着 1 3着 3</div>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    scraper = OfficialRaceScraper(delay_seconds=0)

    entries = scraper._parse_entries(soup)
    result = scraper._parse_result_order(soup)

    assert len(entries) == 3
    assert entries[0]["lane"] == 1
    assert entries[0]["player_id"] == "1001"
    assert result == [2, 1, 3]


def test_fetch_races_for_date_filters_empty_entries(monkeypatch):
    scraper = OfficialRaceScraper(delay_seconds=0)

    def fake_fetch(date_str, venue_code, race_no, include_results):
        if venue_code == "01" and race_no == 1:
            return {
                "race_id": f"{date_str}_{venue_code}_01",
                "entries": [{"lane": 1, "player_id": "1001", "win_rate": 6.0, "motor_rate": 5.0, "venue_rate": 5.5}],
                "result_order": [1, 2, 3],
            }
        return {"race_id": "x", "entries": []}

    scraper.VENUE_CODES = ["01"]
    monkeypatch.setattr(scraper, "_fetch_race_page", fake_fetch)

    races = scraper.fetch_races_for_date(target_date=__import__("datetime").datetime(2026, 8, 2), include_results=True)
    assert len(races) == 1
    assert races[0]["race_id"].endswith("_01_01")
