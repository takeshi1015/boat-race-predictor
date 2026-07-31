"""
公式ボートレースデータ取得クライアント
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup


class OfficialDataClient:
    """boatrace.jp から開催情報・レース情報・結果を取得するクライアント"""

    BASE_URL = "https://boatrace.jp"
    VENUES = {
        "01": "桐生",
        "02": "平和島",
        "03": "住之江",
        "04": "尼崎",
        "05": "鳴門",
        "06": "多摩川",
        "07": "戸田",
        "08": "江戸川",
        "09": "浜名湖",
        "10": "蒲郡",
        "11": "常滑",
        "12": "津",
        "13": "三国",
        "14": "びわこ",
        "15": "丸亀",
        "16": "児島",
        "17": "宮島",
        "18": "芦屋",
        "19": "福岡",
        "20": "唐津",
        "21": "大村",
    }

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

    def fetch_operating_venues(self, target_date: Optional[datetime] = None) -> List[str]:
        if target_date is None:
            target_date = datetime.now()

        date_str = target_date.strftime("%Y%m%d")
        response = self.session.get(
            f"{self.BASE_URL}/race/schedule",
            params={"date": date_str},
            timeout=self.timeout,
        )
        response.raise_for_status()
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.content, "html.parser")

        operating = set()
        for link in soup.find_all("a", href=True):
            code = self._extract_jyo_code(link["href"])
            if code and code in self.VENUES:
                operating.add(self.VENUES[code])
                continue
            text = link.get_text(strip=True)
            for venue_name in self.VENUES.values():
                if venue_name in text:
                    operating.add(venue_name)
                    break

        return sorted(operating)

    def fetch_races_for_date(self, target_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        if target_date is None:
            target_date = datetime.now()

        races: List[Dict[str, Any]] = []
        date_str = target_date.strftime("%Y%m%d")
        for venue_code, venue_name in self.VENUES.items():
            try:
                response = self.session.get(
                    f"{self.BASE_URL}/race/schedule",
                    params={"date": date_str, "jyo": venue_code},
                    timeout=self.timeout,
                )
                if response.status_code != 200:
                    continue
                response.encoding = "utf-8"
                races.extend(self._parse_schedule(response.content, target_date, venue_code, venue_name))
            except Exception:
                continue
        return races

    def fetch_race_results(self, target_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        if target_date is None:
            target_date = datetime.now()
        date_str = target_date.strftime("%Y%m%d")

        urls = [
            f"{self.BASE_URL}/race/result?hd={date_str}",
            f"{self.BASE_URL}/owpc/pc/race/results?hd={date_str}",
            f"{self.BASE_URL}/cgi-bin/race/race_result.cgi?d={date_str}",
        ]
        for url in urls:
            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code != 200:
                    continue
                response.encoding = "utf-8"
                results = self._parse_results(response.content, target_date)
                if results:
                    return results
            except Exception:
                continue
        return []

    def _parse_schedule(
        self,
        html: bytes,
        target_date: datetime,
        venue_code: str,
        venue_name: str,
    ) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        races: List[Dict[str, Any]] = []

        candidates = soup.select("tr.race-row, tr.is-race, div.race-item")
        if not candidates:
            candidates = soup.find_all(["tr", "div"])

        for element in candidates:
            parsed = self._extract_race_from_element(element, target_date, venue_code, venue_name)
            if parsed:
                races.append(parsed)

        return self._dedupe_races(races)

    def _extract_race_from_element(
        self,
        element: Any,
        target_date: datetime,
        venue_code: str,
        venue_name: str,
    ) -> Optional[Dict[str, Any]]:
        text = element.get_text(" ", strip=True)
        race_num_match = re.search(r"(\d{1,2})\s*(?:R|レース)", text)
        time_match = re.search(r"([01]?\d|2[0-3]):([0-5]\d)", text)
        if not race_num_match or not time_match:
            return None

        race_number = int(race_num_match.group(1))
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        weather = self._normalize_weather(text)
        water_condition = self._normalize_water(text)

        return {
            "race_id": f"{target_date.strftime('%Y%m%d')}_{venue_code}_{race_number:02d}",
            "date": target_date.replace(hour=hour, minute=minute, second=0, microsecond=0),
            "venue": venue_name,
            "place": venue_name,
            "race_number": race_number,
            "weather": weather,
            "water_condition": water_condition,
            "water_surface": water_condition,
            "start_time_hour": hour,
            "time_of_day": "morning" if hour < 12 else ("midday" if hour < 17 else "evening"),
            "number_of_boats": 6,
            "wind_speed": 0.0,
            "temperature": 0.0,
            "humidity": 0.0,
        }

    def _parse_results(self, html: bytes, target_date: datetime) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        results: List[Dict[str, Any]] = []
        venue_by_code = self.VENUES.copy()

        for row in soup.find_all("tr"):
            row_text = row.get_text(" ", strip=True)
            code_match = re.search(r"\b(0[1-9]|1[0-9]|2[0-1])\b", row_text)
            race_match = re.search(r"(\d{1,2})\s*(?:R|レース)", row_text)
            trifecta_match = re.search(r"\b([1-6])\s*[-／/]\s*([1-6])\s*[-／/]\s*([1-6])\b", row_text)
            if not race_match or not trifecta_match:
                continue

            venue_code = code_match.group(1) if code_match else None
            if not venue_code:
                continue
            venue_name = venue_by_code.get(venue_code)
            if not venue_name:
                continue

            race_number = int(race_match.group(1))
            first = int(trifecta_match.group(1))
            second = int(trifecta_match.group(2))
            third = int(trifecta_match.group(3))
            odds_match = re.search(r"(\d+(?:\.\d+)?)\s*倍", row_text)

            results.append(
                {
                    "race_id": f"{target_date.strftime('%Y%m%d')}_{venue_code}_{race_number:02d}",
                    "venue": venue_name,
                    "place": venue_name,
                    "race_number": race_number,
                    "date": target_date,
                    "result": {
                        "order": [first, second, third],
                        "first": first,
                        "second": second,
                        "third": third,
                        "trifecta_odds": float(odds_match.group(1)) if odds_match else 0.0,
                        "source": "official",
                        "fetched_at": datetime.now().isoformat(),
                    },
                }
            )

        deduped: Dict[str, Dict[str, Any]] = {}
        for result in results:
            deduped[result["race_id"]] = result
        return list(deduped.values())

    def _extract_jyo_code(self, href: str) -> Optional[str]:
        parsed = urlparse(href)
        query = parse_qs(parsed.query)
        value = query.get("jyo", [None])[0]
        if value and value in self.VENUES:
            return value
        return None

    def _normalize_weather(self, text: str) -> str:
        if "晴" in text:
            return "sunny"
        if "曇" in text:
            return "cloudy"
        if "雨" in text:
            return "rainy"
        return "sunny"

    def _normalize_water(self, text: str) -> str:
        if "穏" in text or "静" in text:
            return "calm"
        if "少" in text:
            return "slight"
        if "荒" in text:
            return "rough"
        return "moderate"

    def _dedupe_races(self, races: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique: Dict[str, Dict[str, Any]] = {}
        for race in races:
            unique[race["race_id"]] = race
        return list(unique.values())
