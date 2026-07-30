"""
ボートレース公式サイトから実レースデータを取得するスクリプト
"""

import sys
import os
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import logging

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import get_db_manager
from database.models import Race

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BoatraceDataFetcher:
    """ボートレース公式サイトからレースデータを取得"""

    BASE_URL = "https://boatrace.jp"

    # 全24場のレース場コード
    VENUES = {
        "01": "桐生",
        "02": "平和島",
        "03": "住之江",
        "04": "尼崎",
        "05": "鳴門",
        "06": "多摩川",
        "07": "戸田",
        "08": "江戸川",
        "09": "浜名湖",
        "10": "蒲郡",
        "11": "常滑",
        "12": "津",
        "13": "三国",
        "14": "びわこ",
        "15": "丸亀",
        "16": "児島",
        "17": "宮島",
        "18": "芦屋",
        "19": "福岡",
        "20": "唐津",
        "21": "大村",
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

        races = []
        date_str = target_date.strftime("%Y%m%d")

        logger.info(f"📥 {target_date.strftime('%Y年%m月%d日')} のレースデータを取得中...")

        # 各レース場のスケジュールページから取得
        for venue_code, venue_name in self.VENUES.items():
            try:
                venue_races = self._fetch_venue_races(venue_code, venue_name, target_date)
                if venue_races:
                    races.extend(venue_races)
                    logger.info(f"  ✅ {venue_name}: {len(venue_races)}件")
            except Exception as e:
                logger.debug(f"  ⚠️  {venue_name}: {e}")

        logger.info(f"📊 合計 {len(races)}件のレースを取得")
        return races

    def _fetch_venue_races(self, venue_code: str, venue_name: str, target_date: datetime) -> list:
        """特定のレース場のレースデータを取得"""
        races = []
        date_str = target_date.strftime("%Y%m%d")

        try:
            # 公式サイトのレーススケジュールページ
            url = f"{self.BASE_URL}/race/schedule"
            params = {
                "date": date_str,
                "jyo": venue_code,
            }

            response = self.session.get(url, params=params, timeout=10)
            response.encoding = "utf-8"

            if response.status_code != 200:
                logger.debug(f"HTTP {response.status_code}: {venue_name}")
                return []

            soup = BeautifulSoup(response.content, "html.parser")

            # レーステーブルを探す
            race_table = soup.find("table", class_="race-schedule-table")
            if not race_table:
                # 代替: div要素から抽出
                race_items = soup.find_all("div", class_="race-item")
            else:
                race_items = race_table.find_all("tr", class_="race-row")

            for item in race_items:
                race_data = self._parse_race_row(item, venue_code, venue_name, target_date)
                if race_data:
                    races.append(race_data)

            return races

        except Exception as e:
            logger.debug(f"スクレイピングエラー ({venue_name}): {e}")
            return []

    def _parse_race_row(self, row_element, venue_code: str, venue_name: str, target_date: datetime) -> dict:
        """HTMLからレース情報をパース"""
        try:
            # レース番号を抽出
            race_num_elem = row_element.find("td", class_="race-number")
            if not race_num_elem:
                race_num_elem = row_element.find("span", class_="race-no")
            
            if not race_num_elem:
                return None

            race_number = int(race_num_elem.get_text(strip=True).replace("R", "").replace("レース", ""))

            # レース時刻を抽出
            time_elem = row_element.find("td", class_="race-time")
            if not time_elem:
                time_elem = row_element.find("span", class_="race-time")

            if not time_elem:
                return None

            time_str = time_elem.get_text(strip=True)
            # "12:30" 形式から時間を抽出
            hour, minute = map(int, time_str.split(":"))

            # 天気情報を抽出
            weather_elem = row_element.find("td", class_="weather")
            weather = "unknown"
            if weather_elem:
                weather_text = weather_elem.get_text(strip=True)
                if "晴" in weather_text:
                    weather = "sunny"
                elif "曇" in weather_text:
                    weather = "cloudy"
                elif "雨" in weather_text:
                    weather = "rainy"

            # 水面状況を抽出
            water_elem = row_element.find("td", class_="water-condition")
            water_condition = "moderate"
            if water_elem:
                water_text = water_elem.get_text(strip=True)
                if "穏" in water_text or "静" in water_text:
                    water_condition = "calm"
                elif "少" in water_text:
                    water_condition = "slight"
                elif "中" in water_text:
                    water_condition = "moderate"

            race_data = {
                "race_id": f"{target_date.strftime('%Y%m%d')}_{venue_code}_{race_number:02d}",
                "date": target_date.replace(hour=hour, minute=minute, second=0, microsecond=0),
                "venue": venue_name,
                "place": venue_name,
                "race_number": race_number,
                "weather": weather,
                "water_condition": water_condition,
                "water_surface": water_condition,
                "start_time_hour": hour,
                "time_of_day": "morning" if hour < 12 else ("midday" if hour < 17 else "evening"),
                "number_of_boats": 6,
                "wind_speed": 0.0,
                "temperature": 0.0,
                "humidity": 0.0,
            }

            return race_data

        except Exception as e:
            logger.debug(f"パースエラー: {e}")
            return None


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
                # 既存チェック
                existing = db.get_race(session, race_data["race_id"])
                if existing:
                    logger.debug(f"スキップ（既存）: {race_data['race_id']}")
                    continue

                # 新規レースを追加
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
