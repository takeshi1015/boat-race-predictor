"""boatrace.jp の公式ページから実レース情報を取得するスクレイパー。"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class ScraperConfig:
    """スクレイピング設定。"""

    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    )
    request_timeout: int = 15
    delay_seconds: float = 0.8
    max_retries: int = 3


class OfficialBoatraceScraper:
    """boatrace.jp の開催情報・結果・出走情報を収集する。"""

    BASE_URL = "https://www.boatrace.jp"

    VENUES: Dict[str, str] = {
        "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川", "06": "浜名湖",
        "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国", "11": "びわこ", "12": "住之江",
        "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島", "17": "宮島", "18": "徳山",
        "19": "下関", "20": "若松", "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
    }

    def __init__(self, config: Optional[ScraperConfig] = None) -> None:
        self.config = config or ScraperConfig()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.config.user_agent})

    def fetch_past_results(self, days: int = 30) -> List[Dict[str, Any]]:
        """過去N日分の実レース結果を取得する。"""
        records: List[Dict[str, Any]] = []
        today = datetime.now().date()

        for diff in range(1, days + 1):
            target = today - timedelta(days=diff)
            date_str = target.strftime("%Y%m%d")
            venues = self.fetch_active_venues(target)
            for venue_code in venues:
                for race_no in range(1, 13):
                    result = self.fetch_race_result(date_str=date_str, venue_code=venue_code, race_no=race_no)
                    if result is not None:
                        records.append(result)
        return records

    def fetch_active_venues(self, date_obj: datetime.date) -> List[str]:
        """対象日に開催が確認できる会場コードを返す。"""
        monthly = self._request(
            "/owpc/pc/race/monthlyschedule",
            params={"ym": date_obj.strftime("%Y%m")},
        )
        if monthly is None:
            return []

        date_str = date_obj.strftime("%Y%m%d")
        soup = BeautifulSoup(monthly.text, "html.parser")
        seen = set()
        venues: List[str] = []
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            if f"hd={date_str}" not in href:
                continue
            matched = re.search(r"jcd=(\d{2})", href)
            if not matched:
                continue
            code = matched.group(1)
            if code in seen:
                continue
            seen.add(code)
            venues.append(code)
        return sorted(venues)

    def fetch_race_result(self, date_str: str, venue_code: str, race_no: int) -> Optional[Dict[str, Any]]:
        """レース結果ページを取得・解析する。"""
        response = self._request(
            "/owpc/pc/race/raceresult",
            params={"rno": race_no, "jcd": venue_code, "hd": date_str},
        )
        if response is None:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        race_id = f"{date_str}_{venue_code}_{race_no:02d}"

        weather = self._extract_labeled_value(soup, ["天候", "weather"], default="unknown")
        water = self._extract_labeled_value(soup, ["波高", "水面", "water"], default="unknown")
        wind = self._extract_float_from_text(self._extract_labeled_value(soup, ["風速", "wind"], default="0"))

        finish_order = self._parse_finish_order(soup)
        entries = self._parse_entries(soup)
        odds = self._parse_odds(soup)

        race_datetime = datetime.strptime(date_str, "%Y%m%d")
        return {
            "race_id": race_id,
            "date": race_datetime,
            "venue": self.VENUES.get(venue_code, venue_code),
            "place": self.VENUES.get(venue_code, venue_code),
            "race_number": race_no,
            "weather": weather,
            "water_condition": water,
            "water_surface": water,
            "wind_speed": float(wind),
            "number_of_boats": max(len(entries), 6),
            "result": {
                "finish_order": finish_order,
                "entries": entries,
                "odds": odds,
                "source": "boatrace.jp",
                "fetched_at": datetime.now().isoformat(),
            },
        }

    def _request(self, path: str, params: Dict[str, Any]) -> Optional[requests.Response]:
        url = f"{self.BASE_URL}{path}"
        for attempt in range(self.config.max_retries):
            try:
                response = self.session.get(url, params=params, timeout=self.config.request_timeout)
                response.raise_for_status()
                time.sleep(self.config.delay_seconds)
                return response
            except requests.RequestException:
                if attempt >= self.config.max_retries - 1:
                    return None
                time.sleep(self.config.delay_seconds * (attempt + 1))
        return None

    @staticmethod
    def _extract_labeled_value(soup: BeautifulSoup, labels: List[str], default: str = "") -> str:
        text = soup.get_text(" ", strip=True)
        for label in labels:
            pattern = re.compile(rf"{re.escape(label)}\s*[:：]?\s*([^\s]+)")
            matched = pattern.search(text)
            if matched:
                return matched.group(1)
        return default

    @staticmethod
    def _extract_float_from_text(value: str) -> float:
        matched = re.search(r"[-+]?[0-9]*\.?[0-9]+", value or "")
        return float(matched.group(0)) if matched else 0.0

    @staticmethod
    def _parse_finish_order(soup: BeautifulSoup) -> List[int]:
        order: List[int] = []
        for row in soup.find_all("tr"):
            cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
            if len(cells) < 2:
                continue
            if cells[0] not in {"1", "2", "3"}:
                continue
            lane = cells[1]
            if lane.isdigit():
                order.append(int(lane))
            if len(order) >= 3:
                break
        return order

    @staticmethod
    def _parse_entries(soup: BeautifulSoup) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for row in soup.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
            if len(cells) < 4:
                continue
            first = cells[0]
            if not first.isdigit() or not (1 <= int(first) <= 6):
                continue
            entry: Dict[str, Any] = {"lane": int(first)}
            entry["player_id"] = OfficialBoatraceScraper._extract_player_id(" ".join(cells))
            entry["motor_no"] = OfficialBoatraceScraper._extract_int(cells[-1])
            entries.append(entry)
            if len(entries) >= 6:
                break
        return entries

    @staticmethod
    def _parse_odds(soup: BeautifulSoup) -> Dict[str, float]:
        odds: Dict[str, float] = {}
        text = soup.get_text(" ", strip=True)
        trifecta = re.search(r"3連単\s*([0-9\-]+)\s*([0-9]+\.?[0-9]*)", text)
        if trifecta:
            odds["trifecta_combo"] = trifecta.group(1)
            odds["trifecta"] = float(trifecta.group(2))
        quinella = re.search(r"2連単\s*([0-9\-]+)\s*([0-9]+\.?[0-9]*)", text)
        if quinella:
            odds["exacta_combo"] = quinella.group(1)
            odds["exacta"] = float(quinella.group(2))
        return odds

    @staticmethod
    def _extract_player_id(text: str) -> Optional[str]:
        matched = re.search(r"\b(\d{4,6})\b", text)
        return matched.group(1) if matched else None

    @staticmethod
    def _extract_int(text: str) -> Optional[int]:
        matched = re.search(r"\d+", text or "")
        return int(matched.group(0)) if matched else None
