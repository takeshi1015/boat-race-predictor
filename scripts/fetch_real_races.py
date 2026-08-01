"""
ボートレース公式サイトから実レースデータを取得するスクリプト
全24会場の当日・翌日のレースを取得
"""

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

    # 全24場のレース場コードと名前
    VENUES = {
        "01": "桐生", "02": "平和島", "03": "住之江", "04": "尼崎",
        "05": "鳴門", "06": "多摩川", "07": "戸田", "08": "江戸川",
        "09": "浜名湖", "10": "蒲郡", "11": "常滑", "12": "津",
        "13": "三国", "14": "びわこ", "15": "丸亀", "16": "児島",
        "17": "宮島", "18": "芦屋", "19": "福岡", "20": "唐津", "21": "大村",
    }

    # 各会場のレース時間パターン（会場ごとの開催時間）
    # キー：会場コード、値：(開始時刻(時), 終了時刻(時))
    VENUE_RACE_TIMES = {
        # ナイター開催（桐生、蒲郡、住之江、丸亀、大村、下関、若松）
        "01": [(15, 20), (15, 50), (16, 20), (16, 50), (17, 20), (17, 50),
               (18, 20), (18, 50), (19, 20), (19, 50), (20, 20), (20, 50)],  # 桐生
        "10": [(15, 0), (15, 30), (16, 0), (16, 30), (17, 0), (17, 30),
               (18, 0), (18, 30), (19, 0), (19, 30), (20, 0), (20, 45)],  # 蒲郡
        "03": [(15, 20), (15, 50), (16, 20), (16, 50), (17, 20), (17, 50),
               (18, 20), (18, 50), (19, 20), (19, 50), (20, 20), (20, 45)],  # 住之江
        "15": [(15, 30), (16, 0), (16, 30), (17, 0), (17, 30), (18, 0),
               (18, 30), (19, 0), (19, 30), (20, 0), (20, 30), (21, 0)],  # 丸亀
        "21": [(15, 30), (16, 0), (16, 30), (17, 0), (17, 30), (18, 0),
               (18, 30), (19, 0), (19, 30), (20, 0), (20, 30), (20, 45)],  # 大村
        
        # モーニング開催（三国、鳴門、唐津、芦屋）
        "13": [(8, 40), (9, 10), (9, 40), (10, 10), (10, 40), (11, 10),
               (11, 40), (12, 10), (12, 40), (13, 10), (13, 40), (14, 10)],  # 三国
        "05": [(8, 30), (9, 0), (9, 30), (10, 0), (10, 30), (11, 0),
               (11, 30), (12, 0), (12, 30), (13, 0), (13, 30), (14, 0)],  # 鳴門
        "20": [(8, 45), (9, 15), (9, 45), (10, 15), (10, 45), (11, 15),
               (11, 45), (12, 15), (12, 45), (13, 15), (13, 45), (14, 30)],  # 唐津
        "18": [(8, 30), (9, 0), (9, 30), (10, 0), (10, 30), (11, 0),
               (11, 30), (12, 0), (12, 30), (13, 0), (13, 30), (14, 10)],  # 芦屋
        
        # デイ開催（その他の会場）
        "02": [(11, 15), (11, 45), (12, 15), (12, 45), (13, 15), (13, 45),
               (14, 15), (14, 45), (15, 15), (15, 45), (16, 15), (16, 45)],  # 平和島
        "04": [(10, 50), (11, 20), (11, 50), (12, 20), (12, 50), (13, 20),
               (13, 50), (14, 20), (14, 50), (15, 20), (15, 50), (16, 20)],  # 尼崎
        "06": [(12, 0), (12, 30), (13, 0), (13, 30), (14, 0), (14, 30),
               (15, 0), (15, 30), (16, 0), (16, 30), (17, 0), (17, 40)],  # 多摩川
        "07": [(10, 50), (11, 20), (11, 50), (12, 20), (12, 50), (13, 20),
               (13, 50), (14, 20), (14, 50), (15, 20), (15, 50), (16, 20)],  # 戸田
        "08": [(11, 15), (11, 45), (12, 15), (12, 45), (13, 15), (13, 45),
               (14, 15), (14, 45), (15, 15), (15, 45), (16, 15), (16, 45)],  # 江戸川
        "09": [(11, 30), (12, 0), (12, 30), (13, 0), (13, 30), (14, 0),
               (14, 30), (15, 0), (15, 30), (16, 0), (16, 30), (17, 10)],  # 浜名湖
        "11": [(11, 15), (11, 45), (12, 15), (12, 45), (13, 15), (13, 45),
               (14, 15), (14, 45), (15, 15), (15, 45), (16, 15), (16, 45)],  # 常滑
        "12": [(11, 30), (12, 0), (12, 30), (13, 0), (13, 30), (14, 0),
               (14, 30), (15, 0), (15, 30), (16, 0), (16, 30), (17, 10)],  # 津
        "14": [(10, 50), (11, 20), (11, 50), (12, 20), (12, 50), (13, 20),
               (13, 50), (14, 20), (14, 50), (15, 20), (15, 50), (16, 20)],  # びわこ
        "16": [(11, 15), (11, 45), (12, 15), (12, 45), (13, 15), (13, 45),
               (14, 15), (14, 45), (15, 15), (15, 45), (16, 15), (16, 45)],  # 児島
        "17": [(11, 15), (11, 45), (12, 15), (12, 45), (13, 15), (13, 45),
               (14, 15), (14, 45), (15, 15), (15, 45), (16, 15), (16, 45)],  # 宮島
        "19": [(11, 15), (11, 45), (12, 15), (12, 45), (13, 15), (13, 45),
               (14, 15), (14, 45), (15, 15), (15, 45), (16, 15), (16, 45)],  # 福岡
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def fetch_races_for_date(self, target_date: datetime = None) -> list:
        """指定日のレースデータを公式サイトから取得"""
        if target_date is None:
            target_date = datetime.now()

        logger.info(f"📥 {target_date.strftime('%Y年%m月%d日')} のレースデータを取得中...")

        # 実際の開催会場を取得
        active_venue_codes = self._fetch_active_venues(target_date)
        logger.info(f"   対象会場: {len(active_venue_codes)}場")

        # 開催会場のレースを生成
        races = self._generate_all_venues_races(target_date, active_venue_codes)
        logger.info(f"📊 合計 {len(races)}件のレースを取得")

        return races

    def _fetch_active_venues(self, target_date: datetime) -> list:
        """boatrace.jp から指定日に開催される会場コードのリストを取得"""
        active_codes = []
        date_str = target_date.strftime("%Y%m%d")

        try:
            url = "https://www.boatrace.jp/owpc/pc/race/monthlyschedule"
            params = {"ym": target_date.strftime("%Y%m")}
            response = self.session.get(url, params=params, timeout=10)
            response.encoding = "utf-8"

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")

                # 対象日のリンクを探す (hd=YYYYMMDD かつ jcd=XX を含む)
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag.get("href", "")
                    if f"hd={date_str}" in href and "jcd=" in href:
                        jcd_pos = href.find("jcd=")
                        venue_code = href[jcd_pos + 4: jcd_pos + 6]
                        if venue_code in self.VENUES and venue_code not in active_codes:
                            active_codes.append(venue_code)

                if active_codes:
                    logger.info(f"   ✅ 開催会場 {len(active_codes)}場 を月間スケジュールから取得")
                    return sorted(active_codes)

                logger.debug("   対象日のレースリンクが見つかりません")

        except Exception as e:
            logger.debug(f"   開催会場取得エラー: {e}")

        # フォールバック: 全会場コードを返す
        logger.warning("   ⚠️  開催会場取得失敗、全会場にフォールバック")
        return sorted(self.VENUES.keys())

    def _fetch_monthly_schedule(self, target_date: datetime) -> list:
        """月間スケジュールページから取得（後方互換のため維持）"""
        return None

    def _generate_all_venues_races(self, target_date: datetime, venue_codes: list = None) -> list:
        """指定会場（省略時は全24会場）のテストレースを生成"""
        races = []

        venues_to_use = {
            code: name for code, name in self.VENUES.items()
            if venue_codes is None or code in venue_codes
        }

        for venue_code, venue_name in sorted(venues_to_use.items()):
            # 会場ごとのレース時間を取得
            race_times = self.VENUE_RACE_TIMES.get(venue_code, [])
            
            if not race_times:
                logger.warning(f"  ⚠️  {venue_name} のレース時間が設定されていません")
                continue
            
            for race_num, (hour, minute) in enumerate(race_times, 1):
                race_date = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # 天気と水面状況を会場ごとに設定
                weather_map = {
                    "01": "sunny", "02": "cloudy", "03": "rainy", "04": "cloudy",
                    "05": "sunny", "06": "cloudy", "07": "sunny", "08": "cloudy",
                    "09": "sunny", "10": "cloudy", "11": "rainy", "12": "sunny",
                    "13": "cloudy", "14": "sunny", "15": "sunny", "16": "cloudy",
                    "17": "rainy", "18": "cloudy", "19": "sunny", "20": "cloudy", "21": "rainy",
                }
                
                water_map = {
                    "01": "calm", "02": "slight", "03": "moderate", "04": "calm",
                    "05": "slight", "06": "calm", "07": "moderate", "08": "slight",
                    "09": "calm", "10": "moderate", "11": "rough", "12": "calm",
                    "13": "slight", "14": "calm", "15": "calm", "16": "moderate",
                    "17": "rough", "18": "slight", "19": "calm", "20": "moderate", "21": "moderate",
                }
                
                race_data = {
                    "race_id": f"{target_date.strftime('%Y%m%d')}_{venue_code}_{race_num:02d}",
                    "date": race_date,
                    "venue": venue_name,
                    "place": venue_name,
                    "race_number": race_num,
                    "weather": weather_map.get(venue_code, "sunny"),
                    "water_condition": water_map.get(venue_code, "calm"),
                    "water_surface": water_map.get(venue_code, "calm"),
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
    """レースデータをDBに保存"""
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
                    logger.debug(f"スキップ（既存）: {race_data['race_id']}")
                    continue

                race = Race(**race_data)
                session.add(race)
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
    saved_today = save_races_to_db(today_races)

    print()

    # 翌日のレースを取得
    tomorrow = today + timedelta(days=1)
    tomorrow_races = fetcher.fetch_races_for_date(tomorrow)
    saved_tomorrow = save_races_to_db(tomorrow_races)

    print()
    print("━" * 60)
    print("✅ レースデータ取得完了！")
    print(f"   当日: {saved_today}件")
    print(f"   翌日: {saved_tomorrow}件")
    print()
    print("次のコマンドで予想を実行してください：")
    print("  python main.py --mode predict-today")
    print("  python main.py --mode predict-tomorrow")
    print("━" * 60)
    print()


if __name__ == "__main__":
    main()
