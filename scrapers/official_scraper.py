"""
ボートレース公式サイトスクレイパー
boatrace.jp から各場の営業情報・レース状況をリアルタイム取得
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class OfficialScraper:
    """ボートレース公式サイトからリアルタイム情報を取得"""

    BASE_URL = "https://www.boatrace.jp"

    # 全場コードと名前
    VENUE_CODES = {
        "01": "桐生", "02": "平和島", "03": "住之江", "04": "尼崎",
        "05": "鳴門", "06": "多摩川", "07": "戸田", "08": "江戸川",
        "09": "浜名湖", "10": "蒲郡", "11": "常滑", "12": "津",
        "13": "三国", "14": "びわこ", "15": "丸亀", "16": "児島",
        "17": "宮島", "18": "芦屋", "19": "福岡", "20": "唐津",
        "21": "大村",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def get_venue_info(self, venue_code: str, date: datetime) -> Dict:
        """
        各ボートレース場の本日の営業情報を取得

        Args:
            venue_code: 場コード ("01"〜"21")
            date: 対象日付

        Returns:
            {
                "is_open": bool,
                "race_type": str,       # "day", "morning", "night", "midnight"
                "first_race_time": str, # "HH:MM"
                "last_race_time": str,  # "HH:MM"
                "races": [
                    {
                        "race_num": int,
                        "start_time": str,    # "HH:MM"
                        "status": str,         # "open", "closed", "confirmed"
                    }
                ]
            }
        """
        date_str = date.strftime("%Y%m%d")
        url = f"{self.BASE_URL}/owpc/pc/race/racelist"
        params = {"hd": date_str, "jcd": venue_code}

        logger.info(f"公式サイト取得: {url}?hd={date_str}&jcd={venue_code}")

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.encoding = "utf-8"

            if response.status_code != 200:
                logger.warning(f"HTTP {response.status_code}: {venue_code}場")
                return self._empty_venue_info()

            soup = BeautifulSoup(response.content, "html.parser")
            return self._parse_venue_info(soup, date)

        except Exception as e:
            logger.error(f"会場情報取得エラー ({venue_code}): {e}")
            return self._empty_venue_info()

    def _parse_venue_info(self, soup: BeautifulSoup, date: datetime) -> Dict:
        """HTMLから会場情報をパース"""
        races = []

        try:
            # レーステーブルを探す
            # 公式サイトのレースリスト: class="is-w495" or table.racelistWrap
            race_cells = soup.select(".is-w495 .is-fs12, table.racelistWrap tbody tr")

            # 別のセレクタを試す
            if not race_cells:
                race_cells = soup.select("tbody tr")

            for row in race_cells:
                race = self._parse_race_row(row, date)
                if race:
                    races.append(race)

            # レース情報が空の場合はHTMLから直接抽出を試みる
            if not races:
                races = self._extract_races_from_html(soup, date)

        except Exception as e:
            logger.error(f"会場情報パースエラー: {e}")

        if not races:
            return self._empty_venue_info()

        first_time = races[0]["start_time"] if races else None
        last_time = races[-1]["start_time"] if races else None
        race_type = self._determine_race_type(first_time, last_time)

        return {
            "is_open": True,
            "race_type": race_type,
            "first_race_time": first_time,
            "last_race_time": last_time,
            "races": races,
        }

    def _parse_race_row(self, row, date: datetime) -> Optional[Dict]:
        """テーブル行からレース情報を抽出"""
        try:
            text = row.get_text(separator=" ", strip=True)

            # 時刻パターン (HH:MM) を検索
            import re
            time_match = re.search(r'\b(\d{1,2}):(\d{2})\b', text)
            if not time_match:
                return None

            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                return None

            time_str = f"{hour:02d}:{minute:02d}"

            # レース番号を抽出
            race_num_match = re.search(r'\b(\d{1,2})[Rr]\b|第(\d{1,2})レース', text)
            if not race_num_match:
                race_num_match = re.search(r'^(\d{1,2})\b', text.strip())
            if not race_num_match:
                return None

            race_num = int(race_num_match.group(1) or race_num_match.group(2))
            if not 1 <= race_num <= 12:
                return None

            # ステータスを判定
            status = self._determine_status_from_row(row)

            return {
                "race_num": race_num,
                "start_time": time_str,
                "status": status,
            }
        except Exception:
            return None

    def _extract_races_from_html(self, soup: BeautifulSoup, date: datetime) -> List[Dict]:
        """HTMLから直接レース情報を抽出（フォールバック）"""
        import re
        races = []
        text = soup.get_text()

        # 「X R HH:MM」パターンを検索
        patterns = [
            r'(\d{1,2})[Rr]\s+(\d{1,2}:\d{2})',
            r'(\d{1,2})\s+(\d{1,2}:\d{2})',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                for race_num_str, time_str in matches:
                    race_num = int(race_num_str)
                    if 1 <= race_num <= 12:
                        races.append({
                            "race_num": race_num,
                            "start_time": time_str,
                            "status": "open",
                        })
                if races:
                    break

        return races

    def _determine_status_from_row(self, row) -> str:
        """行のHTMLからレースステータスを判定"""
        row_html = str(row)
        row_text = row.get_text(strip=True)

        # 「確定」「確」「結果」マークを検索
        if any(mark in row_text for mark in ["確定", "確", "結果確定"]):
            return "confirmed"

        # CSSクラスによる判定
        confirmed_classes = ["is-result", "is-fixed", "is-kakuteiju"]
        if any(cls in row_html for cls in confirmed_classes):
            return "confirmed"

        # 「締切」「発走済み」マーク
        if any(mark in row_text for mark in ["締切", "発走済", "終了"]):
            return "closed"

        return "open"

    def _determine_race_type(self, first_time: Optional[str], last_time: Optional[str]) -> str:
        """レース時間帯を判定"""
        if not first_time:
            return "day"

        try:
            first_hour = int(first_time.split(":")[0])
        except Exception:
            return "day"

        if first_hour < 10:
            return "morning"
        elif first_hour >= 20:
            return "night"
        elif first_hour >= 15:
            return "night"
        else:
            return "day"

    def _empty_venue_info(self) -> Dict:
        """空の会場情報（非開催）"""
        return {
            "is_open": False,
            "race_type": None,
            "first_race_time": None,
            "last_race_time": None,
            "races": [],
        }

    def get_today_open_venues(self, date: Optional[datetime] = None) -> List[str]:
        """
        本日開催中の会場コードリストを取得

        Returns:
            開催中の会場コードリスト ["01", "03", ...]
        """
        if date is None:
            date = datetime.now()

        date_str = date.strftime("%Y%m%d")
        url = f"{self.BASE_URL}/owpc/pc/race/index"
        params = {"hd": date_str}

        logger.info(f"本日開催会場取得: {url}?hd={date_str}")

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.encoding = "utf-8"

            if response.status_code != 200:
                logger.warning(f"HTTP {response.status_code}: 開催会場一覧")
                return []

            soup = BeautifulSoup(response.content, "html.parser")
            return self._extract_open_venue_codes(soup, date_str)

        except Exception as e:
            logger.error(f"開催会場取得エラー: {e}")
            return []

    def _extract_open_venue_codes(self, soup: BeautifulSoup, date_str: str) -> List[str]:
        """HTMLから開催中の会場コードを抽出"""
        codes = []

        # jcd=XX パターンを含むリンクを探す
        import re
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if f"hd={date_str}" in href or "jcd=" in href:
                jcd_match = re.search(r'jcd=(\d{2})', href)
                if jcd_match:
                    code = jcd_match.group(1)
                    if code in self.VENUE_CODES and code not in codes:
                        codes.append(code)

        # 別パターン: data属性など
        if not codes:
            for elem in soup.select("[data-jcd], [data-venue]"):
                code = elem.get("data-jcd") or elem.get("data-venue")
                if code and code in self.VENUE_CODES and code not in codes:
                    codes.append(code)

        logger.info(f"開催会場コード: {codes}")
        return sorted(codes)

    def get_race_status(self, venue_code: str, race_num: int, date: datetime) -> str:
        """
        特定レースのステータスを取得

        Returns:
            "open" | "closed" | "confirmed"
        """
        date_str = date.strftime("%Y%m%d")

        # レース結果ページを確認（"確定"判定）
        result_url = f"{self.BASE_URL}/owpc/pc/race/raceresult"
        params = {"hd": date_str, "jcd": venue_code, "rno": race_num}

        try:
            response = self.session.get(result_url, params=params, timeout=10)
            response.encoding = "utf-8"

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                if is_race_finished(soup):
                    return "confirmed"

        except Exception as e:
            logger.debug(f"レース結果取得エラー ({venue_code} R{race_num}): {e}")

        # レース詳細ページで締切判定
        detail_url = f"{self.BASE_URL}/owpc/pc/race/racelist"
        params_detail = {"hd": date_str, "jcd": venue_code, "rno": race_num}

        try:
            response = self.session.get(detail_url, params=params_detail, timeout=10)
            response.encoding = "utf-8"

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                text = soup.get_text()
                if any(mark in text for mark in ["締切", "発走済", "終了"]):
                    return "closed"

        except Exception as e:
            logger.debug(f"レース詳細取得エラー ({venue_code} R{race_num}): {e}")

        return "open"

    def close(self):
        """セッションを閉じる"""
        self.session.close()


def is_race_finished(race_html: BeautifulSoup) -> bool:
    """
    レースが終了（着順確定）しているかを判定

    boatrace.jp の HTMLから「確」「確定」「結果」マークを検索し、
    結果表示エリアが存在するかを確認する。

    Args:
        race_html: レースページのBeautifulSoup オブジェクト

    Returns:
        True if finished (着順確定済み), False if ongoing/not started
    """
    # 着順確定マーク検索（CSSクラス）
    confirmed_selectors = [
        ".is-result",
        ".is-fixed",
        ".kakutei",
        "[data-status='confirmed']",
        "[data-status='fixed']",
        ".result-label",
        ".race-result",
    ]
    for selector in confirmed_selectors:
        try:
            if race_html.select(selector):
                logger.debug(f"確定マーク検出 (selector: {selector})")
                return True
        except Exception:
            continue

    # テキストベースの「確定」マーク検索
    page_text = race_html.get_text()
    confirmed_texts = ["着順確定", "確定", "レース結果", "払戻金"]
    for text in confirmed_texts:
        if text in page_text:
            # 「確定」が結果セクション内にあるか確認
            result_sections = race_html.find_all(
                ["div", "table", "section"],
                class_=lambda c: c and any(
                    kw in c for kw in ["result", "kakutei", "pay", "return"]
                ),
            )
            if result_sections:
                logger.debug(f"着順確定テキスト検出: '{text}'")
                return True

    return False
