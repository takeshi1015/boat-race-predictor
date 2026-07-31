"""
ボートレース場の開催状況を管理するモジュール
公式サイトから実開催情報を取得
"""

from datetime import datetime
import json
import os
import logging

from utils.official_data_client import OfficialDataClient

logger = logging.getLogger(__name__)


class VenueManager:
    """ボートレース場の開催状況を管理"""

    BASE_URL = "https://boatrace.jp"

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
        self.cache_expiry_hours = 3  # 3時間でキャッシュ無効
        self.client = OfficialDataClient(timeout=10)

    def get_operating_venues_today(self):
        """
        本日開催中のレース場を取得
        優先順位：
        1. 公式サイトからスクレイピング（リアルタイム）
        2. キャッシュから取得
        3. DBのレースデータから抽出
        """
        # 公式サイトからスクレイピング（最優先）
        try:
            operating = self._fetch_from_official_site()
            if operating:
                self._save_cache(operating)
                logger.info(f"公式サイトから開催場所取得: {operating}")
                return operating
        except Exception as e:
            logger.debug(f"公式サイトスクレイピング失敗: {e}")

        # キャッシュから取得
        cached_venues = self._load_cache()
        if cached_venues is not None:
            logger.info(f"キャッシュから開催場所取得: {cached_venues}")
            return cached_venues

        # フォールバック: DBのレースデータから開催場所を抽出
        try:
            operating = self._get_venues_from_database()
            if operating:
                logger.info(f"DBから開催場所取得: {operating}")
                return operating
        except Exception as e:
            logger.debug(f"DB抽出失敗: {e}")

        logger.warning("開催場所情報を取得できません")
        return []

    def get_operating_venues_tomorrow(self):
        """翌日開催中のレース場を取得"""
        from datetime import datetime, timedelta
        
        tomorrow = datetime.now() + timedelta(days=1)
        
        try:
            operating = self._fetch_from_official_site(target_date=tomorrow)
            if operating:
                logger.info(f"翌日開催場所取得: {operating}")
                return operating
        except Exception as e:
            logger.debug(f"翌日スクレイピング失敗: {e}")

        # フォールバック: DBから取得
        try:
            operating = self._get_venues_from_database(target_date=tomorrow)
            if operating:
                logger.info(f"翌日DB開催場所取得: {operating}")
                return operating
        except Exception as e:
            logger.debug(f"翌日DB抽出失敗: {e}")

        return []

    def _fetch_from_official_site(self, target_date=None):
        """ボートレース公式サイトからスクレイピング"""
        try:
            if target_date is None:
                target_date = datetime.now()
            operating_venues = self.client.fetch_operating_venues(target_date)
            return operating_venues if operating_venues else None

        except Exception as e:
            logger.debug(f"スクレイピング処理エラー: {e}")
            return None

    def _extract_venue_name(self, text: str):
        """テキストからレース場名を抽出"""
        for official_name in self.ALL_VENUES.keys():
            if official_name in text:
                return official_name
        return None

    def _get_venues_from_database(self, target_date=None):
        """データベースのレースデータから開催場所を抽出"""
        try:
            from database.db_manager import get_db_manager
            from datetime import datetime
            
            if target_date is None:
                target_date = datetime.now()
            
            db = get_db_manager()
            session = db.get_session()
            try:
                races = db.get_races_by_date(session, target_date)
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
