"""実レースデータ取得（boatrace.jp）."""

from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import get_db_manager
from database.models import Race
from utils.logger import setup_logger

logger = setup_logger(__name__)


class BoatraceDataFetcher:
    """boatrace.jp から当日レースを取得する."""

    BASE_URL = "https://www.boatrace.jp"
    REQUEST_RETRY_COUNT = 3
    REQUEST_RETRY_DELAY = 2
    REQUEST_TIMEOUT = 15

    # 要件で指定された会場（実運用で使われるコード差異を吸収）
    PRIMARY_VENUES = {
        "02": "平和島",
        "03": "住之江",
        "04": "尼崎",
        "05": "鳴門",
        "06": "多摩川",
        "07": "戸田",
        "08": "江戸川",
        "09": "浜名湖",
        "10": "蒲郡",
        "12": "津",
        "13": "三国",
        "14": "びわこ",
        "15": "丸亀",
        "16": "児島",
        "17": "宮島",
        "18": "徳山",
        "19": "下関",
        "20": "戸畑",
        "22": "福岡",
        "23": "唐津",
        "24": "大村",
    }
    LEGACY_VENUE_CODE_BY_NAME = {
        "福岡": "19",
        "唐津": "20",
        "大村": "21",
    }
    VENUES = dict(PRIMARY_VENUES)

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36"
                )
            }
        )

    def fetch_races_for_date(self, target_date: Optional[datetime] = None) -> list:
        """指定日の実レースデータを取得."""
        target_date = target_date or datetime.now()
        active_venues = self._fetch_active_venues(target_date)
        races: List[Dict[str, Any]] = []
        for venue_code in active_venues:
            for race_number in range(1, 13):
                race_data = self._fetch_race(venue_code, race_number, target_date)
                if race_data:
                    races.append(race_data)
        logger.info("%s レース取得件数: %d", target_date.strftime("%Y-%m-%d"), len(races))
        return races

    def _request_with_retry(self, path: str, params: Dict[str, Any]) -> Optional[requests.Response]:
        url = f"{self.BASE_URL}{path}"
        for attempt in range(1, self.REQUEST_RETRY_COUNT + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.REQUEST_TIMEOUT)
                response.raise_for_status()
                response.encoding = "utf-8"
                return response
            except requests.RequestException as exc:
                logger.warning(
                    "HTTP失敗 (%s) attempt=%d/%d: %s",
                    path,
                    attempt,
                    self.REQUEST_RETRY_COUNT,
                    exc,
                )
                if attempt < self.REQUEST_RETRY_COUNT:
                    time.sleep(self.REQUEST_RETRY_DELAY)
        return None

    def _fetch_active_venues(self, target_date: datetime) -> list:
        """指定日開催の対象会場コードを取得."""
        date_str = target_date.strftime("%Y%m%d")
        response = self._request_with_retry(
            "/owpc/pc/race/monthlyschedule", {"ym": target_date.strftime("%Y%m")}
        )

        candidates: List[str] = []
        if response is not None:
            soup = BeautifulSoup(response.text, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag.get("href", "")
                if f"hd={date_str}" not in href:
                    continue
                match = re.search(r"jcd=(\d{2})", href)
                if not match:
                    continue
                code = match.group(1)
                if code in self.PRIMARY_VENUES and code not in candidates:
                    candidates.append(code)

        if candidates:
            return sorted(candidates)

        logger.warning("開催会場の取得に失敗。要件対象会場の既知コードにフォールバックします。")
        fallback: List[str] = sorted(self.PRIMARY_VENUES.keys())
        for legacy_code in self.LEGACY_VENUE_CODE_BY_NAME.values():
            if legacy_code not in fallback:
                fallback.append(legacy_code)
        return sorted(fallback)

    def _fetch_race(self, venue_code: str, race_number: int, target_date: datetime) -> Optional[Dict[str, Any]]:
        params = {"hd": target_date.strftime("%Y%m%d"), "jcd": venue_code, "rno": race_number}
        race_response = self._request_with_retry("/owpc/pc/race/racelist", params)
        if race_response is None:
            return None

        soup = BeautifulSoup(race_response.text, "html.parser")
        race_datetime = self._parse_race_datetime(soup, target_date)
        participants = self._parse_participants(soup)
        if not participants:
            return None

        odds = self._fetch_odds(venue_code, race_number, target_date)
        venue_name = self.PRIMARY_VENUES.get(venue_code)
        if not venue_name:
            for name, code in self.LEGACY_VENUE_CODE_BY_NAME.items():
                if code == venue_code:
                    venue_name = name
                    break
        venue_name = venue_name or f"会場{venue_code}"

        return {
            "race_id": f"{target_date.strftime('%Y%m%d')}_{venue_code}_{race_number:02d}",
            "date": race_datetime,
            "venue": venue_name,
            "place": venue_name,
            "race_number": race_number,
            "weather": self._parse_weather(soup),
            "water_condition": self._parse_water_condition(soup),
            "water_surface": self._parse_water_condition(soup),
            "start_time_hour": race_datetime.hour,
            "time_of_day": self._time_of_day(race_datetime.hour),
            "number_of_boats": len(participants),
            "wind_speed": 0.0,
            "temperature": 0.0,
            "humidity": 0.0,
            "result": {
                "source": "boatrace.jp",
                "venue_code": venue_code,
                "participants": participants,
                "odds": odds,
                "race_time": race_datetime.strftime("%H:%M"),
                "status": "upcoming",
            },
        }

    def _fetch_odds(self, venue_code: str, race_number: int, target_date: datetime) -> Dict[str, float]:
        params = {"hd": target_date.strftime("%Y%m%d"), "jcd": venue_code, "rno": race_number}
        response = self._request_with_retry("/owpc/pc/race/odds3t", params)
        if response is None:
            return {}
        soup = BeautifulSoup(response.text, "html.parser")
        odds: Dict[str, float] = {}
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            combo = self._extract_combination(cells[0].get_text(" ", strip=True))
            odd = self._extract_float(cells[1].get_text(" ", strip=True))
            if combo and odd is not None:
                odds[combo] = odd
        if odds:
            return odds
        for combo, value in re.findall(r"(\d-\d-\d)\s*([0-9]+(?:\.[0-9]+)?)", soup.get_text(" ", strip=True)):
            odds[combo] = float(value)
        return odds

    @staticmethod
    def _parse_race_datetime(soup: BeautifulSoup, target_date: datetime) -> datetime:
        race_time = None
        for selector in [".is-time", ".time", ".raceTime", ".raceresult_time"]:
            node = soup.select_one(selector)
            if node:
                race_time = BoatraceDataFetcher._extract_time(node.get_text(" ", strip=True))
                if race_time:
                    break
        if not race_time:
            race_time = BoatraceDataFetcher._extract_time(soup.get_text(" ", strip=True))
        if not race_time:
            race_time = "00:00"
        hour, minute = [int(x) for x in race_time.split(":")]
        return target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

    @staticmethod
    def _parse_participants(soup: BeautifulSoup) -> List[Dict[str, Any]]:
        participants: List[Dict[str, Any]] = []
        seen_lane = set()
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if not cells:
                continue
            lane = BoatraceDataFetcher._extract_lane(cells[0].get_text(" ", strip=True))
            if lane is None or lane in seen_lane:
                continue
            name = BoatraceDataFetcher._extract_name_from_row(row)
            if not name:
                continue
            participants.append({"lane": lane, "name": name})
            seen_lane.add(lane)
        participants.sort(key=lambda item: item["lane"])
        return participants

    @staticmethod
    def _extract_name_from_row(row) -> str:
        for a_tag in row.find_all("a"):
            text = a_tag.get_text(strip=True)
            if text and not text.isdigit():
                return text
        for cell in row.find_all("td")[1:]:
            text = cell.get_text(" ", strip=True)
            if text and re.search(r"[ぁ-んァ-ン一-龥]", text):
                return text.split()[0]
        return ""

    @staticmethod
    def _parse_weather(soup: BeautifulSoup) -> str:
        text = soup.get_text(" ", strip=True)
        if "雨" in text:
            return "rainy"
        if "曇" in text:
            return "cloudy"
        return "sunny"

    @staticmethod
    def _parse_water_condition(soup: BeautifulSoup) -> str:
        text = soup.get_text(" ", strip=True)
        if "荒" in text:
            return "rough"
        if "波高" in text or "波" in text:
            return "slight"
        return "calm"

    @staticmethod
    def _extract_time(text: str) -> Optional[str]:
        match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
        if not match:
            return None
        return f"{int(match.group(1)):02d}:{match.group(2)}"

    @staticmethod
    def _extract_lane(text: str) -> Optional[int]:
        match = re.search(r"\b([1-6])\b", text)
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _extract_combination(text: str) -> Optional[str]:
        match = re.search(r"([1-6])\D+([1-6])\D+([1-6])", text)
        if not match:
            return None
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    @staticmethod
    def _extract_float(text: str) -> Optional[float]:
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", text.replace(",", ""))
        if not match:
            return None
        return float(match.group(1))

    @staticmethod
    def _time_of_day(hour: int) -> str:
        if hour < 12:
            return "morning"
        if hour < 17:
            return "midday"
        return "evening"


def save_races_to_db(races: list) -> int:
    """レースデータをDBに保存（重複時は更新）."""
    if not races:
        logger.warning("保存するレースがありません")
        return 0

    db = get_db_manager()
    session = db.get_session()

    try:
        saved_count = 0
        for race_data in races:
            try:
                existing = db.get_race(session, race_data["race_id"])
                if existing:
                    for key, value in race_data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                else:
                    session.add(Race(**race_data))
                saved_count += 1
            except Exception as e:
                logger.debug(f"レース保存エラー: {e}")
                session.rollback()

        session.commit()
        logger.info(f"✅ {saved_count}件のレースをDBに保存")
        return saved_count

    except Exception as e:
        logger.error(f"DB保存エラー: {e}")
        session.rollback()
        return 0
    finally:
        session.close()


def archive_completed_races(now: Optional[datetime] = None) -> int:
    """終了レースを履歴状態へ更新."""
    now = now or datetime.now()
    db = get_db_manager()
    session = db.get_session()
    try:
        archived = 0
        races = session.query(Race).all()
        for race in races:
            race_result = race.result if isinstance(race.result, dict) else {}
            status = race_result.get("status")
            if race.date and race.date <= now and status != "completed":
                race_result["status"] = "completed"
                race.result = race_result
                archived += 1
            elif race.date and race.date > now and status != "upcoming":
                race_result["status"] = "upcoming"
                race.result = race_result
        session.commit()
        return archived
    except Exception as exc:
        logger.error("終了レース履歴更新エラー: %s", exc)
        session.rollback()
        return 0
    finally:
        session.close()


def refresh_race_data(target_date: Optional[datetime] = None) -> Tuple[int, int]:
    """指定日の実レース取得 + DB保存 + 履歴更新."""
    fetcher = BoatraceDataFetcher()
    date_to_use = target_date or datetime.now()
    races = fetcher.fetch_races_for_date(date_to_use)
    saved = save_races_to_db(races)
    archived = archive_completed_races()
    return saved, archived


def main():
    print()
    print("━" * 60)
    print("ボートレース公式サイト レースデータ取得")
    print("━" * 60)
    print()

    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    saved_today, archived_today = refresh_race_data(today)
    saved_tomorrow, archived_tomorrow = refresh_race_data(tomorrow)

    print()
    print("━" * 60)
    print("✅ レースデータ取得完了！")
    print(f"   当日保存: {saved_today}件")
    print(f"   翌日保存: {saved_tomorrow}件")
    print(f"   履歴移動: {archived_today + archived_tomorrow}件")
    print()
    print("次のコマンドでサーバーを起動してください：")
    print("  python main.py --mode run-server")
    print("━" * 60)
    print()


if __name__ == "__main__":
    main()
