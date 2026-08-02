"""
ボートレース場の開催状況を管理するモジュール
公式サイトから実開催情報を取得
"""

from datetime import datetime
import json
import os
import logging
import requests
from bs4 import BeautifulSoup

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
        "若松": {"code": "22", "name_jp": "若松"},
    }

    # テストデータ用：固定の開催日程（最終フォールバック用）
    FIXED_SCHEDULE = {
        "2026-08-02": ["桐生", "多摩川", "浜名湖", "常滑", "びわこ", "尼崎", "丸亀", "児島", "若松", "芦屋", "福岡", "唐津"],
    }

    def __init__(self):
        self.cache_file = "venue_schedule.json"
        self.cache_expiry_hours = 1  # 1時間でキャッシュ無効（リアルタイム性を重視）
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def get_operating_venues_today(self):
        """
        本日開催中のレース場を取得
        優先順位：
        1. 公式サイトからスクレイピング（リアルタイム）← 最優先
        2. キャッシュから取得（スクレイピング失敗時）
        3. DBのレースデータから抽出（ただしフィルタリング）
        4. 固定スケジュール（テスト用・最終フォールバック）
        """
        # 1. 公式サイトからスクレイピング（最優先）
        try:
            operating = self._fetch_from_official_site()
            if operating:
                self._save_cache(operating)
                logger.info(f"✅ 公式サイトから開催場所取得: {operating}")
                return operating
        except Exception as e:
            logger.debug(f"公式サイトスクレイピング失敗: {e}")

        # 2. キャッシュから取得
        cached_venues = self._load_cache()
        if cached_venues is not None:
            logger.info(f"✅ キャッシュから開催場所取得: {cached_venues}")
            return cached_venues

        # 3. DBのレースデータから開催場所を抽出
        try:
            operating = self._get_venues_from_database()
            if operating:
                logger.info(f"✅ DBから開催場所取得: {operating}")
                return operating
        except Exception as e:
            logger.debug(f"DB抽出失敗: {e}")

        # 4. 固定スケジュール（テスト用・最終フォールバック）
        today_str = datetime.now().strftime("%Y-%m-%d")
        if today_str in self.FIXED_SCHEDULE:
            operating = self.FIXED_SCHEDULE[today_str]
            logger.warning(f"⚠️ 固定スケジュール（テスト用）から開催場所取得: {operating}")
            return operating

        logger.warning("❌ 開催場所情報を取得できません")
        return []

    def get_operating_venues_tomorrow(self):
        """翌日開催中のレース場を取得"""
        from datetime import datetime, timedelta
        
        tomorrow = datetime.now() + timedelta(days=1)
        
        # 1. 公式サイトからスクレイピング（最優先）
        try:
            operating = self._fetch_from_official_site(target_date=tomorrow)
            if operating:
                logger.info(f"✅ 翌日公式サイト開催場所取得: {operating}")
                return operating
        except Exception as e:
            logger.debug(f"翌日スクレイピング失敗: {e}")

        # 2. DBから取得
        try:
            operating = self._get_venues_from_database(target_date=tomorrow)
            if operating:
                logger.info(f"✅ 翌日DB開催場所取得: {operating}")
                return operating
        except Exception as e:
            logger.debug(f"翌日DB抽出失敗: {e}")

        # 3. 固定スケジュール（テスト用）
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        if tomorrow_str in self.FIXED_SCHEDULE:
            operating = self.FIXED_SCHEDULE[tomorrow_str]
            logger.warning(f"⚠️ 翌日固定スケジュール（テスト用）: {operating}")
            return operating

        return []

    def _fetch_from_official_site(self, target_date=None):
        """ボートレース公式サイトからスクレイピング"""
        try:
            if target_date is None:
                target_date = datetime.now()

            date_str = target_date.strftime("%Y%m%d")
            url = f"{self.BASE_URL}/race/schedule"
            params = {"date": date_str}

            logger.debug(f"公式サイトアクセス: {url}?date={date_str}")
            response = self.session.get(url, params=params, timeout=10)
            response.encoding = "utf-8"

            if response.status_code != 200:
                logger.debug(f"HTTP {response.status_code}")
                return None

            soup = BeautifulSoup(response.content, "html.parser")

            # 開催中のレース場を抽出
            operating_venues = []

            # 方法1: schedule-listクラスから抽出
            schedule_list = soup.find("div", class_="schedule-list")
            if schedule_list:
                items = schedule_list.find_all("div", class_="schedule-item")
                for item in items:
                    venue_name = self._extract_venue_name(item.get_text(strip=True))
                    if venue_name and venue_name not in operating_venues:
                        operating_venues.append(venue_name)
                        logger.debug(f"抽出 (method1): {venue_name}")

            # 方法2: テーブルから抽出
            if not operating_venues:
                tables = soup.find_all("table")
                for table in tables:
                    rows = table.find_all("tr")
                    for row in rows:
                        cells = row.find_all(["td", "th"])
                        for cell in cells:
                            venue_name = self._extract_venue_name(cell.get_text(strip=True))
                            if venue_name and venue_name not in operating_venues:
                                operating_venues.append(venue_name)
                                logger.debug(f"抽出 (method2): {venue_name}")

            # 方法3: リンクから抽出
            if not operating_venues:
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    # /race/schedule?date=YYYYMMDD&jyo=XX のようなURL
                    if "/race/schedule" in href and "jyo=" in href:
                        # URLから会場コードを抽出
                        jyo_code = href.split("jyo=")[-1].split("&")[0]
                        for venue_name, info in self.ALL_VENUES.items():
                            if info["code"] == jyo_code:
                                if venue_name not in operating_venues:
                                    operating_venues.append(venue_name)
                                    logger.debug(f"抽出 (method3): {venue_name}")
                                break

            if operating_venues:
                return sorted(operating_venues)
            else:
                logger.debug("公式サイトからレース場を抽出できませんでした")
                return None

        except Exception as e:
            logger.error(f"スクレイピング処理エラー: {e}")
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
                
                logger.debug(f"DBから抽出したレース場: {venues}")
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
                venues = data.get("venues", None)
                logger.debug(f"キャッシュ有効（{(now - cached_date).total_seconds():.0f}秒経過）: {venues}")
                return venues

            logger.debug("キャッシュ期限切れ")
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
            logger.debug(f"キャッシュ保存: {venues}")
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
