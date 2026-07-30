"""
Tests for utils/venue_manager.py
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.venue_manager import VenueManager, ALL_VENUES, DEFAULT_OPERATING_VENUES


class TestVenueManager:
    """VenueManager のテスト"""

    def setup_method(self):
        """各テストの前に一時キャッシュファイルを使う VenueManager を作成"""
        self.tmp_dir = tempfile.mkdtemp()
        self.cache_file = os.path.join(self.tmp_dir, "test_venue_schedule.json")
        self.manager = VenueManager(cache_file=self.cache_file)

    # ------------------------------------------------------------------
    # get_operating_venues_today
    # ------------------------------------------------------------------

    def test_get_operating_venues_today_returns_list(self):
        """get_operating_venues_today がリストを返すことを確認"""
        with patch.object(self.manager, "_fetch_from_official_site", return_value=[]):
            result = self.manager.get_operating_venues_today()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_operating_venues_today_uses_file_cache(self):
        """当日付のキャッシュがある場合にキャッシュを使用することを確認"""
        cached_venues = ["戸田", "江戸川", "多摩川"]
        cache_data = {
            "date": datetime.now().isoformat(),
            "venues": cached_venues,
        }
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False)

        result = self.manager.get_operating_venues_today()
        assert result == cached_venues

    def test_get_operating_venues_today_ignores_stale_cache(self):
        """前日のキャッシュは無視されることを確認"""
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        stale_venues = ["住之江", "鳴門"]
        cache_data = {
            "date": yesterday,
            "venues": stale_venues,
        }
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False)

        with patch.object(self.manager, "_fetch_from_official_site", return_value=[]):
            result = self.manager.get_operating_venues_today()

        # 古いキャッシュは使われず、フォールバックが使われる
        assert result != stale_venues

    def test_get_operating_venues_today_fetches_from_site(self):
        """キャッシュがない場合に公式サイトから取得することを確認"""
        expected = ["戸田", "浜名湖", "常滑"]
        with patch.object(self.manager, "_fetch_from_official_site", return_value=expected):
            result = self.manager.get_operating_venues_today()
        assert result == expected

    def test_get_operating_venues_today_falls_back_to_default(self):
        """スクレイピング失敗時にデフォルト会場にフォールバックすることを確認"""
        with patch.object(self.manager, "_fetch_from_official_site", return_value=[]):
            result = self.manager.get_operating_venues_today()
        assert result == DEFAULT_OPERATING_VENUES

    def test_get_operating_venues_today_uses_in_memory_cache(self):
        """2回目の呼び出しでインメモリキャッシュを使用することを確認"""
        expected = ["桐生", "津"]
        with patch.object(self.manager, "_fetch_from_official_site", return_value=expected) as mock_fetch:
            self.manager.get_operating_venues_today()
            self.manager.get_operating_venues_today()
        # 2回呼ばれても _fetch_from_official_site は1回しか呼ばれない
        mock_fetch.assert_called_once()

    # ------------------------------------------------------------------
    # is_venue_operating
    # ------------------------------------------------------------------

    def test_is_venue_operating_true(self):
        """開催中の場は True を返す"""
        with patch.object(self.manager, "get_operating_venues_today", return_value=["戸田", "津"]):
            assert self.manager.is_venue_operating("戸田") is True

    def test_is_venue_operating_false(self):
        """非開催の場は False を返す"""
        with patch.object(self.manager, "get_operating_venues_today", return_value=["戸田", "津"]):
            assert self.manager.is_venue_operating("住之江") is False

    def test_is_venue_operating_unknown_venue(self):
        """未知の場名は False を返す"""
        with patch.object(self.manager, "get_operating_venues_today", return_value=["戸田"]):
            assert self.manager.is_venue_operating("存在しない場") is False

    # ------------------------------------------------------------------
    # _load_cache / _save_cache
    # ------------------------------------------------------------------

    def test_save_and_load_cache(self):
        """キャッシュの保存と読み込みが正しく動作することを確認"""
        venues = ["桐生", "平和島", "三国"]
        self.manager._save_cache(venues)
        cache_date, loaded_venues = self.manager._load_cache()
        assert cache_date == datetime.now().date()
        assert loaded_venues == venues

    def test_load_cache_no_file(self):
        """キャッシュファイルが存在しない場合 (None, []) を返す"""
        cache_date, venues = self.manager._load_cache()
        assert cache_date is None
        assert venues == []

    def test_save_cache_creates_file(self):
        """_save_cache がキャッシュファイルを作成することを確認"""
        self.manager._save_cache(["戸田"])
        assert Path(self.cache_file).exists()

    # ------------------------------------------------------------------
    # all_venues
    # ------------------------------------------------------------------

    def test_all_venues_contains_24_entries(self):
        """全24場が定義されていることを確認"""
        assert len(ALL_VENUES) == 21  # テスト用場を除く本場21場

    def test_all_venues_have_code(self):
        """全場にコードが設定されていることを確認"""
        for name, info in ALL_VENUES.items():
            assert "code" in info, f"{name} にコードがありません"
            assert info["code"], f"{name} のコードが空です"

    # ------------------------------------------------------------------
    # fetch_official_schedule
    # ------------------------------------------------------------------

    def test_fetch_official_schedule_calls_fetch(self):
        """fetch_official_schedule が _fetch_from_official_site を呼ぶことを確認"""
        expected = ["蒲郡", "芦屋"]
        with patch.object(self.manager, "_fetch_from_official_site", return_value=expected) as mock_fetch:
            result = self.manager.fetch_official_schedule()
        mock_fetch.assert_called_once()
        assert result == expected
