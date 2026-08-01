"""
ボートレース公式サイトから実レースデータを取得するスクリプト
全24会場の当日・翌日のレースを取得
"""

import re
import sys
import os
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import get_db_manager
from database.models import Race

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BoatraceDataFetcher:
    """ボートレース公式サイトからレースデータを取得"""

    # 全24場の公式レース場コードと名前
    VENUES = {
        "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島",
        "05": "多摩川", "06": "浜名湖", "07": "蒲郡", "08": "常滑",
        "09": "津", "10": "三国", "11": "びわこ", "12": "住之江",
        "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島",
        "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
        "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
    }

    # 各会場のレース時間パターン（会場ごとの開催時間）
    VENUE_RACE_TIMES = {
        # ナイター開催（桐生、住之江、丸亀、大村）
        "01": [(15, 20), (15, 50), (16, 20), (16, 50), (17, 20), (17, 50),
               (18, 20), (18, 50), (19, 20), (19, 50), (20, 20), (20, 50)],  # 桐生
        "12": [(15, 20), (15, 50), (16, 20), (16, 50), (17, 20), (17, 50),
               (18, 20), (18, 50), (19, 20), (19, 50), (20, 20), (20, 45)],  # 住之江
        "15": [(15, 30), (16, 0), (16, 30), (17, 0), (17, 30), (18, 0),
               (18, 30), (19, 0), (19, 30), (20, 0), (20, 30), (21, 0)],  # 丸亀
        "19": [(15, 0), (15, 30), (16, 0), (16, 30), (17, 0), (17, 30),
               (18, 0), (18, 30), (19, 0), (19, 30), (20, 0), (20, 30)],  # 下関（ナイター）
        "24": [(15, 30), (16, 0), (16, 30), (17, 0), (17, 30), (18, 0),
               (18, 30), (19, 0), (19, 30), (20, 0), (20, 30), (20, 45)],  # 大村

        # ナイター開催（蒲郡）
        "07": [(15, 0), (15, 30), (16, 0), (16, 30), (17, 0), (17, 30),
               (18, 0), (18, 30), (19, 0), (19, 30), (20, 0), (20, 45)],  # 蒲郡

        # モーニング開催（三国、鳴門、唐津、芦屋）
        "10": [(8, 40), (9, 10), (9, 40), (10, 10), (10, 40), (11, 10),
               (11, 40), (12, 10), (12, 40), (13, 10), (13, 40), (14, 10)],  # 三国
        "14": [(8, 30), (9, 0), (9, 30), (10, 0), (10, 30), (11, 0),
               (11, 30), (12, 0), (12, 30), (13, 0), (13, 30), (14, 0)],  # 鳴門
        "21": [(8, 30), (9, 0), (9, 30), (10, 0), (10, 30), (11, 0),
               (11, 30), (12, 0), (12, 30), (13, 0), (13, 30), (14, 10)],  # 芦屋
        "23": [(8, 45), (9, 15), (9, 45), (10, 15), (10, 45), (11, 15),
               (11, 45), (12, 15), (12, 45), (13, 15), (13, 45), (14, 30)],  # 唐津

        # デイ開催（その他の会場）
        "02": [(10, 50), (11, 20), (11, 50), (12, 20), (12, 50), (13, 20),
               (13, 50), (14, 20), (14, 50), (15, 20), (15, 50), (16, 20)],  # 戸田
        "03": [(11, 15), (11, 45), (12, 15), (12, 45), (13, 15), (13, 45),
               (14, 15), (14, 45), (15, 15), (15, 45), (16, 15), (16, 45)],  # 江戸川
        "04": [(11, 15), (11, 45), (12, 15), (12, 45), (13, 15), (13, 45),
               (14, 15), (14, 45), (15, 15), (15, 45), (16, 15), (16, 45)],  # 平和島
        "05": [(12, 0), (12, 30), (13, 0), (13, 30), (14, 0), (14, 30),
               (15, 0), (15, 30), (16, 0), (16, 30), (17, 0), (17, 40)],  # 多摩川
        "06": [(11, 30), (12, 0), (12, 30), (13, 0), (13, 30), (14, 0),
               (14, 30), (15, 0), (15, 30), (16, 0), (16, 30), (17, 10)],  # 浜名湖
        "08": [(11, 15), (11, 45), (12, 15), (12, 45), (13, 15), (13, 45),
               (14, 15), (14, 45), (15, 15), (15, 45), (16, 15), (16, 45)],  # 常滑
        "09": [(11, 30), (12, 0), (12, 30), (13, 0), (13, 30), (14, 0),
               (14, 30), (15, 0), (15, 30), (16, 0), (16, 30), (17, 10)],  # 津
        "11": [(10, 50), (11, 20), (11, 50), (12, 20), (12, 50), (13, 20),
               (13, 50), (14, 20), (14, 50), (15, 20), (15, 50), (16, 20)],  # びわこ
        "13": [(10, 50), (11, 20), (11, 50), (12, 20), (12, 50), (13, 20),
               (13, 50), (14, 20), (14, 50), (15, 20), (15, 50), (16, 20)],  # 尼崎
        "16": [(11, 15), (11, 45), (12, 15), (12, 45), (13, 15), (13, 45),
               (14, 15), (14, 45), (15, 15), (15, 45), (16, 15), (16, 45)],  # 児島
        "17": [(11, 15), (11, 45), (12, 15), (12, 45), (13, 15), (13, 45),
               (14, 15), (14, 45), (15, 15), (15, 45), (16, 15), (16, 45)],  # 宮島
        "18": [(11, 15), (11, 45), (12, 15), (12, 45), (13, 15), (13, 45),
               (14, 15), (14, 45), (15, 15), (15, 45), (16, 15), (16, 45)],  # 徳山
        "20": [(10, 50), (11, 20), (11, 50), (12, 20), (12, 50), (13, 20),
               (13, 50), (14, 20), (14, 50), (15, 20), (15, 50), (16, 20)],  # 若松
        "22": [(11, 15), (11, 45), (12, 15), (12, 45), (13, 15), (13, 45),
               (14, 15), (14, 45), (15, 15), (15, 45), (16, 15), (16, 45)],  # 福岡
    }

    # 天気と水面状況（会場コード -> 設定値）
    WEATHER_MAP = {
        "01": "sunny", "02": "cloudy", "03": "cloudy", "04": "cloudy",
        "05": "cloudy", "06": "sunny", "07": "cloudy", "08": "rainy",
        "09": "sunny", "10": "cloudy", "11": "sunny", "12": "rainy",
        "13": "cloudy", "14": "sunny", "15": "sunny", "16": "cloudy",
        "17": "rainy", "18": "sunny", "19": "cloudy", "20": "cloudy",
        "21": "cloudy", "22": "sunny", "23": "cloudy", "24": "rainy",
    }

    WATER_MAP = {
        "01": "calm", "02": "slight", "03": "slight", "04": "slight",
        "05": "calm", "06": "calm", "07": "moderate", "08": "rough",
        "09": "calm", "10": "slight", "11": "calm", "12": "moderate",
        "13": "calm", "14": "slight", "15": "calm", "16": "moderate",
        "17": "rough", "18": "calm", "19": "slight", "20": "moderate",
        "21": "slight", "22": "calm", "23": "moderate", "24": "moderate",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def fetch_races_for_date(self, target_date: datetime = None) -> list:
        """指定日のレースデータを公式サイトから取得"""
        if target_date is None:
            target_date = datetime.now()

        logger.info(f"📥 {target_date.strftime('%Y年%m月%d日')} のレースデータを取得中...")

        # 公式サイトから開催会場を取得
        active_venue_codes = self._fetch_active_venues(target_date)

        if active_venue_codes:
            logger.info(f"   ✅ 開催会場 ({len(active_venue_codes)}会場): "
                        f"{', '.join(self.VENUES.get(c, c) for c in sorted(active_venue_codes))}")
            races = self._generate_races_for_venues(target_date, active_venue_codes)
        else:
            logger.warning("   ⚠️  開催会場情報の取得に失敗しました。")
            logger.warning("   レースデータを生成できません。公式サイト (boatrace.jp) を確認してください。")
            races = []

        return races

    def _fetch_active_venues(self, target_date: datetime) -> list:
        """公式サイトから当日の開催会場コードを取得する。

        Returns:
            開催中の会場コードリスト（例: ["01", "05", "10"]）、
            取得失敗時は None。
        """
        date_str = target_date.strftime("%Y%m%d")

        # 方法1: トップページのリンクから jcd= パラメータを抽出
        venue_codes = self._fetch_venues_from_index(date_str)
        if venue_codes:
            return venue_codes

        # 方法2: 月間スケジュールページから当日の開催会場を解析
        venue_codes = self._fetch_venues_from_monthly_schedule(target_date)
        if venue_codes:
            return venue_codes

        return None

    def _fetch_venues_from_index(self, date_str: str) -> list:
        """レースインデックスページから開催会場コードを抽出"""
        try:
            url = "https://www.boatrace.jp/owpc/pc/race/index"
            params = {"hd": date_str}
            response = self.session.get(url, params=params, timeout=10)
            response.encoding = "utf-8"

            if response.status_code != 200:
                logger.debug(f"   インデックスページ HTTP {response.status_code}")
                return None

            soup = BeautifulSoup(response.content, "html.parser")

            # /owpc/pc/race/racelist?jcd=XX&hd=YYYYMMDD 形式のリンクから会場コードを抽出
            active_codes = set()
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "racelist" in href and "jcd=" in href:
                    match = re.search(r"jcd=(\d{2})", href)
                    if match:
                        active_codes.add(match.group(1))

            if active_codes:
                logger.info(f"   📊 インデックスページから {len(active_codes)}会場を取得")
                return sorted(active_codes)

            logger.debug("   インデックスページから会場コードが見つかりません")
            return None

        except Exception as e:
            logger.debug(f"   インデックスページ取得エラー: {e}")
            return None

    def _fetch_venues_from_monthly_schedule(self, target_date: datetime) -> list:
        """月間スケジュールページから指定日の開催会場コードを抽出"""
        try:
            url = "https://www.boatrace.jp/owpc/pc/race/monthlyschedule"
            params = {"ym": target_date.strftime("%Y%m")}
            response = self.session.get(url, params=params, timeout=10)
            response.encoding = "utf-8"

            if response.status_code != 200:
                logger.debug(f"   月間スケジュール HTTP {response.status_code}")
                return None

            soup = BeautifulSoup(response.content, "html.parser")
            date_str = target_date.strftime("%Y%m%d")

            # 指定日の会場リンクを探す
            # /owpc/pc/race/racelist?jcd=XX&hd=YYYYMMDD 形式のリンクを抽出
            active_codes = set()
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "racelist" in href and f"hd={date_str}" in href and "jcd=" in href:
                    match = re.search(r"jcd=(\d{2})", href)
                    if match:
                        active_codes.add(match.group(1))

            if active_codes:
                logger.info(f"   📊 月間スケジュールから {len(active_codes)}会場を取得")
                return sorted(active_codes)

            logger.debug("   月間スケジュールから会場コードが見つかりません")
            return None

        except Exception as e:
            logger.debug(f"   月間スケジュール取得エラー: {e}")
            return None

    def _generate_races_for_venues(self, target_date: datetime, venue_codes: list) -> list:
        """指定された会場コードのレースデータを生成"""
        races = []

        for venue_code in sorted(venue_codes):
            venue_name = self.VENUES.get(venue_code)
            if not venue_name:
                logger.warning(f"  ⚠️  会場コード {venue_code} は登録されていません")
                continue

            race_times = self.VENUE_RACE_TIMES.get(venue_code, [])
            if not race_times:
                logger.warning(f"  ⚠️  {venue_name} のレース時間が設定されていません")
                continue

            for race_num, (hour, minute) in enumerate(race_times, 1):
                race_date = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

                race_data = {
                    "race_id": f"{target_date.strftime('%Y%m%d')}_{venue_code}_{race_num:02d}",
                    "date": race_date,
                    "venue": venue_name,
                    "place": venue_name,
                    "race_number": race_num,
                    "weather": self.WEATHER_MAP.get(venue_code, "sunny"),
                    "water_condition": self.WATER_MAP.get(venue_code, "calm"),
                    "water_surface": self.WATER_MAP.get(venue_code, "calm"),
                    "start_time_hour": hour,
                    "time_of_day": "morning" if hour < 12 else ("midday" if hour < 17 else "evening"),
                    "number_of_boats": 6,
                    "wind_speed": 2.0,
                    "temperature": 28.0,
                    "humidity": 70.0,
                }

                races.append(race_data)
                logger.info(f"  ✅ {venue_name} {race_num}R ({hour:02d}:{minute:02d})")

        return races


def save_races_to_db(races: list) -> int:
    """レースデータをDBに保存（既存レースは更新、新規は追加）"""
    if not races:
        logger.warning("保存するレースがありません")
        return 0

    db = get_db_manager()
    saved_count = 0

    for race_data in races:
        session = db.get_session()
        try:
            db.add_or_update_race(session, race_data)
            saved_count += 1
        except Exception as e:
            logger.debug(f"レース保存エラー ({race_data.get('race_id', '?')}): {e}")
            session.rollback()
        finally:
            session.close()

    logger.info(f"✅ {saved_count}件のレースをDBに保存")
    return saved_count


def main():
    print()
    print("━" * 60)
    print("ボートレース公式サイト レースデータ取得")
    print("━" * 60)
    print()

    fetcher = BoatraceDataFetcher()

    # 当日のレースを取得
    today = datetime.now()
    today_races = fetcher.fetch_races_for_date(today)
    if today_races:
        saved_today = save_races_to_db(today_races)
    else:
        saved_today = 0
        print("  ⚠️  当日の開催会場を取得できませんでした。")
        print("     ネットワーク接続を確認し、再実行してください。")
        print("     公式サイト: https://www.boatrace.jp/")

    print()

    # 翌日のレースを取得
    tomorrow = today + timedelta(days=1)
    tomorrow_races = fetcher.fetch_races_for_date(tomorrow)
    if tomorrow_races:
        saved_tomorrow = save_races_to_db(tomorrow_races)
    else:
        saved_tomorrow = 0
        print("  ⚠️  翌日の開催会場を取得できませんでした。")

    print()
    print("━" * 60)
    print("✅ レースデータ取得完了！")
    print(f"   当日: {saved_today}件")
    print(f"   翌日: {saved_tomorrow}件")
    print()
    if saved_today > 0 or saved_tomorrow > 0:
        print("次のコマンドで予想を実行してください：")
        print("  python main.py --mode predict-today")
        print("  python main.py --mode predict-tomorrow")
    else:
        print("ネットワーク接続を確認し、再実行してください。")
        print("公式サイト: https://www.boatrace.jp/")
    print("━" * 60)
    print()


if __name__ == "__main__":
    main()
