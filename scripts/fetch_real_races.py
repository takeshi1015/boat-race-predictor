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
import re

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
                time.sleep(0.5)  # サーバー負荷軽減のため0.5秒待機
            except Exception as e:
                logger.debug(f"  {venue_name} データ取得エラー: {e}")
                continue

        logger.info(f"📊 合計 {len(races)}件のレースを取得")
        return races

    def _fetch_races_for_venue(self, target_date: datetime, venue_code: str, venue_name: str) -> list:
        """指定会場のレースデータを取得"""
        races = []
        date_str = target_date.strftime("%Y%m%d")

        try:
            # 会場別の開催日程ページからレース時刻を取得
            url = f"https://www.boatrace.jp/owpc/pc/race/index?hd={date_str}&jcd={venue_code}"
            
            response = self.session.get(url, timeout=30)
            response.encoding = "utf-8"

            if response.status_code != 200:
                logger.debug(f"  {venue_name}: HTTP {response.status_code}")
                return races

            soup = BeautifulSoup(response.content, "html.parser")

            # テーブルを取得
            table = soup.find("table")
            if not table:
                logger.info(f"  ℹ️  {venue_name}: 本日の開催なし")
                return races

            rows = table.find_all("tr")
            if not rows:
                logger.info(f"  ℹ️  {venue_name}: 本日の開催なし")
                return races

            # テーブルの行を解析
            # 奇数行がレース情報、偶数行が時刻情報
            i = 1  # ヘッダーをスキップ
            while i < len(rows) - 1:
                try:
                    # レース情報行から R 数を抽出
                    race_row = rows[i]
                    race_cells = race_row.find_all(["td", "th"])
                    
                    if not race_cells:
                        i += 2
                        continue

                    # R数を抽出（例：「10R」から「10」を取得）
                    race_text = ""
                    for cell in race_cells:
                        cell_text = cell.get_text(strip=True)
                        if "R" in cell_text:
                            race_text = cell_text
                            break

                    if not race_text or "R" not in race_text:
                        i += 2
                        continue

                    race_num_match = re.search(r"(\d+)R", race_text)
                    if not race_num_match:
                        i += 2
                        continue

                    race_num = int(race_num_match.group(1))

                    # 次の行から時刻を抽出
                    time_row = rows[i + 1]
                    time_cells = time_row.find_all(["td", "th"])
                    
                    if not time_cells:
                        i += 2
                        continue

                    # 最初のセルから時刻を取得
                    time_text = time_cells[0].get_text(strip=True)
                    
                    # "HH:MM" 形式をパース
                    time_match = re.search(r"(\d{1,2}):(\d{2})", time_text)
                    if not time_match:
                        i += 2
                        continue

                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2))

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

                    i += 2

                except Exception as e:
                    logger.debug(f"  レース抽出エラー: {e}")
                    i += 2
                    continue

        except Exception as e:
            logger.debug(f"  {venue_name} 取得失敗: {str(e)}")

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

    # 当日のレースを���得
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
