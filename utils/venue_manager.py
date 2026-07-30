"""
ボートレース場の開催状況を管理するモジュール
"""

from datetime import datetime
import json
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class VenueManager:
    """ボートレース場の開催状況を管理"""

    # 全24場のレース場情報
    ALL_VENUES = {
        "桐生": {"code": "01", "name_jp": "桐生"},
        "戸田": {"code": "07", "name_jp": "戸田"},
        "江戸川": {"code": "08", "name_jp": "江戸川"},
        "平和島": {"code": "02", "name_jp": "平和島"},
        "多摩川": {"code": "06", "name_jp": "多摩川"},
        "浜名湖": {"code": "09", "name_jp": "浜名湖"},
        "蒲郡": {"code": "10", "name_jp": "蒲郡"},
        "常滑": {"code": "11", "name_jp": "常滑"},
        "津": {"code": "12", "name_jp": "津"},
        "三国": {"code": "13", "name_jp": "三国"},
        "びわこ": {"code": "14", "name_jp": "びわこ"},
        "住之江": {"code": "03", "name_jp": "住之江"},
        "尼崎": {"code": "04", "name_jp": "尼崎"},
        "鳴門": {"code": "05", "name_jp": "鳴門"},
        "丸亀": {"code": "15", "name_jp": "丸亀"},
        "児島": {"code": "16", "name_jp": "児島"},
        "宮島": {"code": "17", "name_jp": "宮島"},
        "芦屋": {"code": "18", "name_jp": "芦屋"},
        "福岡": {"code": "19", "name_jp": "福岡"},
        "唐津": {"code": "20", "name_jp": "唐津"},
        "大村": {"code": "21", "name_jp": "大村"},
    }

    def __init__(self):
        self.cache_file = "venue_schedule.json"
        self.cache_expiry_hours = 24

    def get_operating_venues_today(self):
        """
        本日開催中のレース場のみを取得
        手順：
        1. キャッシュから取得を試みる
        2. 公式サイトからスクレイピング
        3. データベースのレースデータから抽出
        """
        # キャッシュから取得を試みる
        cached_venues = self._load_cache()
        if cached_venues is not None:
            logger.info(f"キャッシュから開催場所取得: {cached_venues}")
            return cached_venues

        # 公式サイトからスクレイピング
        try:
            operating = self._fetch_from_official_site()
            if operating:
                self._save_cache(operating)
                logger.info(f"公式サイトから開催場所取得: {operating}")
                return operating
        except Exception as e:
            logger.debug(f"公式サイトからのスクレイピング失敗: {e}")

        # フォールバック: データベースのレースデータから開催場所を抽出
        try:
            operating = self._get_venues_from_database()
            if operating:
                logger.info(f"DBから開催場所取得: {operating}")
                return operating
        except Exception as e:
            logger.debug(f"DBからの抽出失敗: {e}")

        logger.warning("開催場所情報を取得できません")
        return []

    def _fetch_from_official_site(self):
        """ボートレース公式サイトからスクレイピング"""
        try:
            import requests
            from bs4 import BeautifulSoup

            url = "https://boatrace.jp/race/schedule"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.content, "html.parser")

            # 公式サイトのHTML構造をパース
            operating_venues = []

            # 例: <div class="schedule-item"> のような構造を探す
            schedule_items = soup.find_all(
                "div", class_=["schedule-item", "race-item", "venue-item"]
            )

            for item in schedule_items:
                # レース場名を抽出
                venue_name = item.get_text(strip=True)

                # 全レース場と照合
                for official_name in self.ALL_VENUES.keys():
                    if official_name in venue_name:
                        if official_name not in operating_venues:
                            operating_venues.append(official_name)
                        break

            # 見つからない場合は別の方法を試す
            if not operating_venues:
                operating_venues = self._parse_schedule_table(soup)

            return operating_venues if operating_venues else None

        except ImportError:
            logger.debug("requests または BeautifulSoup がインストールされていません")
            return None
        except Exception as e:
            logger.debug(f"スクレイピング処理エラー: {e}")
            return None

    def _parse_schedule_table(self, soup):
        """HTML テーブルからスケジュール情報を抽出"""
        try:
            operating_venues = []

            # テーブル構造を探す
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    for cell in cells:
                        text = cell.get_text(strip=True)

                        # 全レース場と照合
                        for official_name in self.ALL_VENUES.keys():
                            if official_name in text:
                                if official_name not in operating_venues:
                                    operating_venues.append(official_name)
                                break

            return operating_venues if operating_venues else None

        except Exception as e:
            logger.debug(f"テーブルパース処理エラー: {e}")
            return None

    def _get_venues_from_database(self):
        """データベースのレースデータから本日の開催場所を抽出"""
        try:
            from database.db_manager import get_db_manager
            from datetime import datetime
            
            db = get_db_manager()
            session = db.get_session()
            try:
                races = db.get_races_by_date(session, datetime.now())
                venues = list(set([r.place or r.venue for r in races if (r.place or r.venue)]))
                return sorted(venues) if venues else None
            finally:
                session.close()
        except Exception as e:
            logger.debug(f"DB抽出エラー: {e}")
            return None

    def _load_cache(self):
        """キャッシュから読み込み"""
        try:
            if not os.path.exists(self.cache_file):
                return None

            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # キャッシュの有効性をチェック
            cached_date = datetime.fromisoformat(data.get("date", ""))
            now = datetime.now()

            # 同じ日付で、キャッシュ有効期限内の場合は使用
            if (
                cached_date.date() == now.date()
                and (now - cached_date).total_seconds() < self.cache_expiry_hours * 3600
            ):
                return data.get("venues", None)

            return None

        except Exception as e:
            logger.debug(f"キャッシュ読み込みエラー: {e}")
            return None

    def _save_cache(self, venues):
        """キャッシュに保存"""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(
                    {"date": datetime.now().isoformat(), "venues": venues}, f, ensure_ascii=False
                )
        except Exception as e:
            logger.debug(f"キャッシュ保存エラー: {e}")

    def is_venue_operating(self, venue_name):
        """特定のレース場が開催中か判定"""
        operating = self.get_operating_venues_today()
        return venue_name in operating

    def get_venue_code(self, venue_name):
        """レース場名からコードを取得"""
        if venue_name in self.ALL_VENUES:
            return self.ALL_VENUES[venue_name]["code"]
        return None

    def get_venue_name(self, code):
        """コードからレース場名を取得"""
        for name, info in self.ALL_VENUES.items():
            if info["code"] == code:
                return name
        return None
