"""
ボートレース公式サイトから実レースデータを取得するスクリプト
全21会場の当日・翌日のレースを取得
"""

import sys
import os
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import logging
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import get_db_manager
from database.models import Race

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BoatraceDataFetcher:
    """ボートレース公式サイトからレースデータを取得"""

    # 全21場のレース場コードと名前
    VENUES = {
        "01": "桐生", "02": "平和島", "03": "住之江", "04": "尼崎",
        "05": "鳴門", "06": "多摩川", "07": "戸田", "08": "江戸川",
        "09": "浜名湖", "10": "蒲郡", "11": "常滑", "12": "津",
        "13": "三国", "14": "びわこ", "15": "丸亀", "16": "児島",
        "17": "宮島", "18": "芦屋", "19": "福岡", "20": "唐津", "21": "大村",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        self.session.timeout = 30

    def fetch_races_for_date(self, target_date: datetime = None) -> list:
        """指定日のレースデータを公式サイトから取得"""
        if target_date is None:
            target_date = datetime.now()

        logger.info(f"📥 {target_date.strftime('%Y年%m月%d日')} のレースデータを取得中...")

        races = []
        date_str = target_date.strftime("%Y%m%d")

        # 各会場ごとにレース情報を取得
        for venue_code, venue_name in sorted(self.VENUES.items()):
            try:
                venue_races = self._fetch_races_for_venue(target_date, venue_code, venue_name)
                races.extend(venue_races)
                time.sleep(1)  # サーバー負荷軽減のため1秒待機
            except Exception as e:
                logger.warning(f"  {venue_name} データ取得エラー: {e}")
                continue

        logger.info(f"📊 合計 {len(races)}件のレースを取得")
        return races

    def _fetch_races_for_venue(self, target_date: datetime, venue_code: str, venue_name: str) -> list:
        """指定会場のレースデータを取得"""
        races = []
        date_str = target_date.strftime("%Y%m%d")

        try:
            # 会場別の開催日程ページから実レース時刻を取得
            # https://www.boatrace.jp/owpc/pc/race/index?hd=YYYYMMDD&jcd=XX
            url = f"https://www.boatrace.jp/owpc/pc/race/index?hd={date_str}&jcd={venue_code}"
            
            response = self.session.get(url, timeout=30)
            response.encoding = "utf-8"

            if response.status_code != 200:
                logger.debug(f"  {venue_name}: HTTP {response.status_code}")
                return races

            soup = BeautifulSoup(response.content, "html.parser")

            # レース情報を含むテーブルを探す
            # boatrace.jpの実際のHTML構造に基づいて調整
            race_rows = soup.find_all("a", {"data-race-id": True})
            
            if not race_rows:
                # 別のセレクタを試す
                race_rows = soup.find_all("div", class_="race-num")

            if not race_rows:
                logger.info(f"  ℹ️  {venue_name}: 本日の開催なし")
                return races

            # レース情報を抽出
            for race_elem in race_rows[:12]:  # 最大12レースまで
                try:
                    # レース番号と時刻を抽出
                    race_text = race_elem.get_text(strip=True)
                    
                    # "1" や "2" など単一の数字を探す
                    if race_text.isdigit():
                        race_num = int(race_text)
                        
                        # 時刻情報を親要素から抽出
                        parent = race_elem.parent
                        time_text = parent.find("span", class_="time") if parent else None
                        
                        if time_text:
                            time_str = time_text.get_text(strip=True)
                            # "12:15" 形式を解析
                            if ":" in time_str:
                                try:
                                    hour, minute = map(int, time_str.split(":"))
                                    
                                    race_datetime = target_date.replace(
                                        hour=hour, minute=minute, second=0, microsecond=0
                                    )

                                    race_data = {
                                        "race_id": f"{date_str}_{venue_code}_{race_num:02d}",
                                        "date": race_datetime,
                                        "venue": venue_name,
                                        "place": venue_name,
                                        "race_number": race_num,
                                        "weather": "sunny",
                                        "water_condition": "calm",
                                        "water_surface": "calm",
                                        "start_time_hour": hour,
                                        "time_of_day": "morning" if hour < 12 else ("midday" if hour < 17 else "evening"),
                                        "number_of_boats": 6,
                                        "wind_speed": 0.0,
                                        "temperature": 25.0,
                                        "humidity": 60.0,
                                    }

                                    races.append(race_data)
                                    logger.info(f"  ✅ {venue_name} {race_num}R ({hour:02d}:{minute:02d})")

                                except ValueError:
                                    continue
                except Exception as e:
                    logger.debug(f"  レース抽出エラー: {e}")
                    continue

        except Exception as e:
            raise Exception(f"{venue_name} 取得失敗: {str(e)}")

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
