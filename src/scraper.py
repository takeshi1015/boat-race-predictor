"""
src/scraper.py – boatrace.jp から当日のレースデータをリアルタイム取得し、
データベースに保存する。

使用例::

    from src.scraper import RaceDataScraper
    scraper = RaceDataScraper()
    races = scraper.fetch_and_save_today()
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

import config
from utils.logger import logger


# ---------------------------------------------------------------------------
# 全24場の会場コードマッピング
# ---------------------------------------------------------------------------
VENUE_CODES: Dict[str, str] = {
    "桐生": "01",
    "戸田": "02",
    "江戸川": "03",
    "平和島": "04",
    "多摩川": "05",
    "浜名湖": "06",
    "蒲郡": "07",
    "常滑": "08",
    "津": "09",
    "三国": "10",
    "びわこ": "11",
    "住之江": "12",
    "尼崎": "13",
    "鳴門": "14",
    "丸亀": "15",
    "児島": "16",
    "宮島": "17",
    "宇部": "18",
    "福岡": "19",
    "唐津": "20",
    "芦屋": "21",
    "若松": "22",
    "下関": "23",
    "大村": "24",
}

# 逆マッピング（コード → 日本語名）
CODE_TO_VENUE: Dict[str, str] = {v: k for k, v in VENUE_CODES.items()}


class RaceDataScraper:
    """boatrace.jp から当日のレースデータを取得してDBに保存する。

    スクレイピング仕様:
    - 開催一覧: ``https://www.boatrace.jp/owpc/pc/race/index?hd=YYYYMMDD``
    - 出走表:  ``https://www.boatrace.jp/owpc/pc/race/racelist?rno=R&jcd=VC&hd=YYYYMMDD``
    """

    BASE_URL = config.BOATRACE_BASE_URL
    HEADERS = {"User-Agent": config.USER_AGENT}
    TIMEOUT = config.REQUEST_TIMEOUT
    MAX_RETRIES = config.MAX_RETRIES
    RETRY_BACKOFF = config.RETRY_BACKOFF
    INTERVAL = config.REQUEST_INTERVAL

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(self.HEADERS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_and_save_today(self) -> List[Dict[str, Any]]:
        """当日のレースデータを取得してDBに保存する。

        Returns:
            保存したレース情報のリスト。取得・保存に失敗した場合は空リスト。
        """
        target = datetime.now()
        logger.info("当日のレースデータ取得開始: %s", target.strftime("%Y-%m-%d"))
        return self._fetch_and_save(target)

    def fetch_and_save_for_date(self, target: datetime) -> List[Dict[str, Any]]:
        """指定日のレースデータを取得してDBに保存する。

        Args:
            target: 取得対象日付。

        Returns:
            保存したレース情報のリスト。
        """
        return self._fetch_and_save(target)

    # ------------------------------------------------------------------
    # Internal implementation
    # ------------------------------------------------------------------

    def _fetch_and_save(self, target: datetime) -> List[Dict[str, Any]]:
        date_str = target.strftime("%Y%m%d")
        venues = self._get_venue_list(date_str)
        if not venues:
            logger.warning("開催会場を取得できませんでした: %s", date_str)
            return []

        saved: List[Dict[str, Any]] = []
        for venue_code in venues:
            races = self._get_races_for_venue(date_str, venue_code)
            for race_data in races:
                saved_race = self._save_race(race_data)
                if saved_race:
                    saved.append(race_data)
            time.sleep(self.INTERVAL)

        logger.info("レースデータ保存完了: %d件", len(saved))
        return saved

    def _get_venue_list(self, date_str: str) -> List[str]:
        """開催一覧ページから当日の開催会場コードリストを取得する。

        Args:
            date_str: 日付文字列 (YYYYMMDD)。

        Returns:
            会場コードのリスト (例: ["01", "07", "14"])。
        """
        url = f"{self.BASE_URL}/owpc/pc/race/index"
        params = {"hd": date_str}
        html = self._fetch(url, params=params)
        if html is None:
            return []

        try:
            soup = BeautifulSoup(html, "html.parser")
            venue_codes: List[str] = []

            # 開催会場リンク: /owpc/pc/race/racelist?rno=1&jcd=XX&hd=YYYYMMDD
            for a_tag in soup.find_all("a", href=True):
                href: str = a_tag["href"]
                if "racelist" in href and "jcd=" in href:
                    jcd = self._extract_param(href, "jcd")
                    if jcd and jcd not in venue_codes:
                        venue_codes.append(jcd)

            logger.info("開催会場: %s (%d場)", date_str, len(venue_codes))
            return venue_codes
        except Exception as exc:
            logger.error("開催一覧パースエラー: %s", exc)
            return []

    def _get_races_for_venue(
        self, date_str: str, venue_code: str
    ) -> List[Dict[str, Any]]:
        """指定会場の全レース情報を取得する。

        Args:
            date_str: 日付文字列 (YYYYMMDD)。
            venue_code: 会場コード (例: "01")。

        Returns:
            レース情報の辞書リスト。
        """
        races: List[Dict[str, Any]] = []
        venue_name = CODE_TO_VENUE.get(venue_code, venue_code)

        # 通常1日12レース
        for race_number in range(1, 13):
            url = f"{self.BASE_URL}/owpc/pc/race/racelist"
            params = {"rno": race_number, "jcd": venue_code, "hd": date_str}
            html = self._fetch(url, params=params)
            if html is None:
                continue

            race_data = self._parse_race_page(
                html, date_str, venue_code, venue_name, race_number
            )
            if race_data:
                races.append(race_data)
            time.sleep(self.INTERVAL)

        logger.info(
            "会場 %s(%s): %d レース取得", venue_name, venue_code, len(races)
        )
        return races

    def _parse_race_page(
        self,
        html: str,
        date_str: str,
        venue_code: str,
        venue_name: str,
        race_number: int,
    ) -> Optional[Dict[str, Any]]:
        """出走表HTMLからレース情報を抽出する。

        Args:
            html: 出走表ページのHTML。
            date_str: 日付文字列 (YYYYMMDD)。
            venue_code: 会場コード。
            venue_name: 会場名（日本語）。
            race_number: レース番号 (1–12)。

        Returns:
            レース情報の辞書。パース失敗時は None。
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # 出走時刻（例: "10:30"）
            start_time_str = self._extract_race_time(soup)
            race_datetime = self._build_race_datetime(date_str, start_time_str)
            start_time_hour = race_datetime.hour if race_datetime else 12

            # 天候・水面情報
            weather, water_cond, wind_speed = self._extract_conditions(soup)

            # 出走選手情報
            racer_info = self._extract_racer_info(soup)

            # レースが存在するか（出走者がいるか）確認
            if not racer_info:
                return None

            race_id = f"{date_str}_{venue_code}_{race_number:02d}"

            return {
                "race_id": race_id,
                "venue": venue_code,
                "place": venue_name,
                "date": race_datetime or datetime.strptime(date_str, "%Y%m%d"),
                "race_number": race_number,
                "wind_speed": wind_speed,
                "weather": weather,
                "water_condition": water_cond,
                "start_time_hour": start_time_hour,
                "number_of_boats": len(racer_info),
                "result": {"racer_info": racer_info},
            }
        except Exception as exc:
            logger.error(
                "レースページパースエラー (%s R%d): %s", venue_code, race_number, exc
            )
            return None

    # ------------------------------------------------------------------
    # HTML extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_race_time(soup: BeautifulSoup) -> Optional[str]:
        """出走時刻を抽出する。"""
        try:
            # 例: <div class="raceNavi_mainTitle">10R　10:30</div>
            for tag in soup.find_all(class_=lambda c: c and "time" in c.lower()):
                text = tag.get_text(strip=True)
                if ":" in text and len(text) <= 10:
                    return text
            # フォールバック: テキスト内の HH:MM パターン
            import re
            match = re.search(r"\b(\d{1,2}:\d{2})\b", soup.get_text())
            if match:
                return match.group(1)
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_conditions(
        soup: BeautifulSoup,
    ):
        """天候・水面・風速を抽出する。"""
        weather = "sunny"
        water_cond = "calm"
        wind_speed = 0.0

        try:
            # boatrace.jp の天候アイコン alt テキストから判定
            for img in soup.find_all("img", alt=True):
                alt: str = img["alt"].lower()
                if "晴" in alt or "sunny" in alt:
                    weather = "sunny"
                elif "曇" in alt or "cloud" in alt:
                    weather = "cloudy"
                elif "雨" in alt or "rain" in alt:
                    weather = "rainy"

            # 風速
            import re
            for text in soup.stripped_strings:
                m = re.search(r"(\d+(?:\.\d+)?)\s*m", text)
                if m:
                    wind_speed = float(m.group(1))
                    break
        except Exception:
            pass

        return weather, water_cond, wind_speed

    @staticmethod
    def _extract_racer_info(soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """出走表から各選手の情報を抽出する。"""
        racers: List[Dict[str, Any]] = []
        try:
            # 出走表テーブル: class="is-p3-3" または "tbl-raceEntry" など
            table = (
                soup.find("table", {"class": lambda c: c and "entry" in c.lower()})
                or soup.find("table", {"class": lambda c: c and "raceEntry" in c.lower()})
                or soup.find("table")
            )
            if not table:
                return racers

            rows = table.find_all("tr")
            for row in rows[1:]:  # ヘッダーをスキップ
                cols = row.find_all(["td", "th"])
                if len(cols) < 3:
                    continue
                texts = [c.get_text(strip=True) for c in cols]
                racer: Dict[str, Any] = {}

                # 枠番（最初のカラムが数字ならフレーム番号）
                if texts[0].isdigit() and 1 <= int(texts[0]) <= 6:
                    racer["frame_number"] = int(texts[0])
                    racer["player_name"] = texts[1] if len(texts) > 1 else ""
                    racer["player_id"] = texts[2] if len(texts) > 2 else ""
                    racers.append(racer)

        except Exception as exc:
            logger.debug("選手情報抽出エラー: %s", exc)

        return racers

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_race_datetime(
        date_str: str, time_str: Optional[str]
    ) -> Optional[datetime]:
        """日付文字列と時刻文字列から datetime を構築する。"""
        try:
            base = datetime.strptime(date_str, "%Y%m%d")
            if time_str:
                parts = time_str.replace("：", ":").split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                return base.replace(hour=hour, minute=minute)
            return base
        except Exception:
            return None

    @staticmethod
    def _extract_param(url: str, param: str) -> Optional[str]:
        """URL クエリ文字列からパラメータ値を取得する。"""
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            values = qs.get(param, [])
            return values[0] if values else None
        except Exception:
            return None

    def _fetch(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """リトライ付きHTTP GETを実行してレスポンスのテキストを返す。

        Args:
            url: 取得先 URL。
            params: クエリパラメータ。

        Returns:
            レスポンスのテキスト、またはすべてのリトライが失敗した場合は None。
        """
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                resp = self._session.get(url, params=params, timeout=self.TIMEOUT)
                resp.raise_for_status()
                return resp.text
            except requests.exceptions.RequestException as exc:
                logger.warning(
                    "フェッチ失敗 (試行 %d/%d) %s: %s",
                    attempt,
                    self.MAX_RETRIES,
                    url,
                    exc,
                )
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_BACKOFF ** (attempt - 1))
        logger.error("フェッチ失敗（最大リトライ超過）: %s", url)
        return None

    # ------------------------------------------------------------------
    # Database persistence
    # ------------------------------------------------------------------

    @staticmethod
    def _save_race(race_data: Dict[str, Any]) -> bool:
        """レースデータをデータベースに保存する。

        Args:
            race_data: ``add_or_update_race`` に渡すレース情報辞書。

        Returns:
            保存成功時 True、失敗時 False。
        """
        try:
            from database.db_manager import get_db_manager

            db = get_db_manager()
            session = db.get_session()
            try:
                db.add_or_update_race(session, race_data)
                logger.debug(
                    "レース保存: %s (%s R%d)",
                    race_data.get("place"),
                    race_data.get("date"),
                    race_data.get("race_number"),
                )
                return True
            finally:
                session.close()
        except Exception as exc:
            logger.error("レース保存エラー: %s", exc)
            return False
