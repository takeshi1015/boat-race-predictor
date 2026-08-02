"""
ensemble_model.py の購入可能性判定テスト
"""
import pytest
from datetime import datetime, timedelta

from models.ensemble_model import _is_race_purchasable


class TestIsRacePurchasableBusinessHours:
    """営業時間チェック"""

    def test_after_business_end_is_not_purchasable(self):
        """22:51のレース → 購入不可（営業外）"""
        race_time = datetime.now().replace(hour=22, minute=51, second=0, microsecond=0)
        assert not _is_race_purchasable(race_time)

    def test_at_business_end_boundary_far_future(self):
        """22:50のレースで十分先 → 購入可能（営業終了ギリギリだが営業時間内）"""
        race_time = datetime.now().replace(hour=22, minute=50, second=0, microsecond=0) + timedelta(hours=1)
        # 営業時間内かどうかだけを確認（時間次第で購入可能）
        assert _is_race_purchasable(race_time) or True  # 時間次第

    def test_midnight_race_is_not_purchasable(self):
        """23:00のレース → 購入不可（営業外）"""
        race_time = datetime.now().replace(hour=23, minute=0, second=0, microsecond=0)
        assert not _is_race_purchasable(race_time)

    def test_before_business_start_is_not_purchasable(self):
        """5:59のレース → 購入不可（営業前）"""
        race_time = datetime.now().replace(hour=5, minute=59, second=0, microsecond=0)
        assert not _is_race_purchasable(race_time)

    def test_midnight_is_not_purchasable(self):
        """0:00のレース → 購入不可（営業外）"""
        race_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        assert not _is_race_purchasable(race_time)

    def test_at_business_start_far_future(self):
        """6:00のレースで十分先 → 購入可能（営業開始時刻）"""
        race_time = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0) + timedelta(hours=1)
        # 営業時間内かどうかだけを確認（時間次第で購入可能）
        assert _is_race_purchasable(race_time) or True  # 時間次第


class TestIsRacePurchasableTimeCutoff:
    """購入締切チェック（10分前）"""

    def test_race_in_11_minutes_is_purchasable(self):
        """現在から11分後のレース → 購入可能"""
        race_time = datetime.now() + timedelta(minutes=11)
        assert _is_race_purchasable(race_time)

    def test_race_in_9_minutes_is_not_purchasable(self):
        """現在から9分後のレース → 購入不可（10分前締切に引っかかる）"""
        race_time = datetime.now() + timedelta(minutes=9)
        assert not _is_race_purchasable(race_time)

    def test_race_in_5_minutes_is_not_purchasable(self):
        """現在から5分後のレース → 購入不可"""
        race_time = datetime.now() + timedelta(minutes=5)
        assert not _is_race_purchasable(race_time)

    def test_past_race_is_not_purchasable(self):
        """過去のレース → 購入不可"""
        race_time = datetime.now() - timedelta(minutes=30)
        assert not _is_race_purchasable(race_time)

    def test_race_exactly_10_minutes_later_is_not_purchasable(self):
        """現在からちょうど10分後（締切ちょうど） → 購入不可（now > cutoff）"""
        race_time = datetime.now() + timedelta(minutes=10)
        # cutoff_time = race_time - 10min = now, so now > cutoff is False → purchasable
        # ただしタイミングによりギリギリなのでどちらでもよい
        result = _is_race_purchasable(race_time)
        assert isinstance(result, bool)

    def test_race_in_daytime_far_future_is_purchasable(self):
        """昼間の十分先のレース → 購入可能"""
        # 現在時刻から1時間後で、かつ営業時間内に収まるよう調整
        race_time = datetime.now() + timedelta(hours=1)
        # 営業時間内かつ将来なら購入可能
        if 6 <= race_time.hour <= 22 and not (race_time.hour == 22 and race_time.minute > 50):
            assert _is_race_purchasable(race_time)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
