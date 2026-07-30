"""
ボートレース場の開催状況管理モジュール
"""

import json
import os
from datetime import datetime
from pathlib import Path

from utils.logger import setup_logger

logger = setup_logger(__name__)

# デフォルトキャッシュファイルパス（プロジェクトルート基準）
_DEFAULT_CACHE_FILE = Path(__file__).parent.parent / "venue_schedule.json"

# 全24場のレース場情報
ALL_VENUES = {
    "桐生": {"code": "01", "name_jp": "桐生"},
    "平和島": {"code": "02", "name_jp": "平和島"},
    "住之江": {"code": "03", "name_jp": "住之江"},
    "尼崎": {"code": "04", "name_jp": "尼崎"},
    "鳴門": {"code": "05", "name_jp": "鳴門"},
    "多摩川": {"code": "06", "name_jp": "多摩川"},
    "戸田": {"code": "07", "name_jp": "戸田"},
    "江戸川": {"code": "08", "name_jp": "江戸川"},
    "浜名湖": {"code": "09", "name_jp": "浜名湖"},
    "蒲郡": {"code": "10", "name_jp": "蒲郡"},
    "常滑": {"code": "11", "name_jp": "常滑"},
    "津": {"code": "12", "name_jp": "津"},
    "三国": {"code": "13", "name_jp": "三国"},
    "びわこ": {"code": "14", "name_jp": "びわこ"},
    "丸亀": {"code": "15", "name_jp": "丸亀"},
    "児島": {"code": "16", "name_jp": "児島"},
    "宮島": {"code": "17", "name_jp": "宮島"},
    "芦屋": {"code": "18", "name_jp": "芦屋"},
    "福岡": {"code": "19", "name_jp": "福岡"},
    "唐津": {"code": "20", "name_jp": "唐津"},
    "大村": {"code": "21", "name_jp": "大村"},
}

# スクレイピング失敗時のデフォルト開催場（通常6〜8場）
DEFAULT_OPERATING_VENUES = [
    "戸田",
    "江戸川",
    "多摩川",
    "浜名湖",
    "蒲郡",
    "常滑",
    "津",
    "三国",
]


class VenueManager:
    """ボートレース場の開催状況を管理するクラス"""

    def __init__(self, cache_file: str | None = None):
        """
        Args:
            cache_file: キャッシュファイルのパス。None の場合はデフォルトパスを使用。
        """
        self.cache_file = Path(cache_file) if cache_file else _DEFAULT_CACHE_FILE
        self.venues = ALL_VENUES.copy()
        self._operating_cache: list | None = None
        self._cache_date: datetime | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_operating_venues_today(self) -> list:
        """
        本日開催中のレース場のリストを返す。

        取得順序：
        1. インメモリキャッシュ（同日付）
        2. ファイルキャッシュ（同日付）
        3. 公式サイトからスクレイピング
        4. フォールバック：デフォルト開催場

        Returns:
            本日開催中のレース場名リスト
        """
        today = datetime.now().date()

        # インメモリキャッシュ
        if self._operating_cache is not None and self._cache_date == today:
            logger.debug("インメモリキャッシュから開催場を取得")
            return self._operating_cache

        # ファイルキャッシュ
        cached_date, cached_venues = self._load_cache()
        if cached_date == today and cached_venues:
            logger.info(f"ファイルキャッシュから開催場を取得: {len(cached_venues)}場")
            self._operating_cache = cached_venues
            self._cache_date = today
            return cached_venues

        # 公式サイトからスクレイピング
        try:
            venues = self._fetch_from_official_site()
            if venues:
                logger.info(f"公式サイトから開催場を取得: {len(venues)}場")
                self._save_cache(venues)
                self._operating_cache = venues
                self._cache_date = today
                return venues
        except Exception as e:
            logger.warning(f"公式サイト取得に失敗: {e}")

        # フォールバック
        logger.info("デフォルト開催場を使用")
        fallback = self._get_default_operating_venues()
        self._operating_cache = fallback
        self._cache_date = today
        return fallback

    def is_venue_operating(self, venue_name: str) -> bool:
        """
        特定のレース場が本日開催中かどうかを返す。

        Args:
            venue_name: 確認するレース場名

        Returns:
            開催中の場合 True
        """
        operating = self.get_operating_venues_today()
        return venue_name in operating

    def fetch_official_schedule(self) -> list:
        """
        公式サイトからスケジュールを取得する（外部公開用）。

        Returns:
            開催中のレース場名リスト（失敗時は空リスト）
        """
        return self._fetch_from_official_site()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_from_official_site(self) -> list:
        """ボートレース公式サイトからスクレイピングして開催場を取得"""
        try:
            from utils.web_scraper import scrape_boatrace_schedule
            venues = scrape_boatrace_schedule()
            if venues:
                return venues
        except Exception as e:
            logger.warning(f"スクレイピングモジュール呼び出し失敗: {e}")
        return []

    def _get_default_operating_venues(self) -> list:
        """スクレイピング失敗時のデフォルト開催場"""
        return DEFAULT_OPERATING_VENUES.copy()

    def _load_cache(self) -> tuple:
        """
        ファイルキャッシュを読み込む。

        Returns:
            (cache_date, venues) のタプル。キャッシュが存在しない場合は (None, [])
        """
        try:
            if self.cache_file.exists():
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cache_date = datetime.fromisoformat(data["date"]).date()
                venues = data.get("venues", [])
                return cache_date, venues
        except Exception as e:
            logger.warning(f"キャッシュ読み込みエラー: {e}")
        return None, []

    def _save_cache(self, venues: list) -> None:
        """
        取得した開催場情報をファイルキャッシュに保存する。

        Args:
            venues: 保存するレース場名リスト
        """
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "date": datetime.now().isoformat(),
                        "venues": venues,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as e:
            logger.warning(f"キャッシュ保存エラー: {e}")
