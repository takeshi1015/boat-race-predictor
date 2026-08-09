"""
ボートレース公式サイトから実レースデータを取得するスクリプト
全会場の当日・翌日のレースを取得（終了したレースは除外）
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

    def fetch_active_venues(self, target_date: datetime) -> list:
        """指定日に開催される会場を月間スケジュールから取得"""
        active_venues = []
        date_str = target_date.strftime("%Y%m%d")
        ym_str = target_date.strftime("%Y%m")

        try:
            url = f"https://www.boatrace.jp/owpc/pc/race/monthlyschedule?ym={ym_str}"
            response = self.session.get(url, timeout=30)
            response.encoding = "utf-8"

            soup = BeautifulSoup(response.content, "html.parser")
            links = soup.find_all("a", href=True)

            for link in links:
                href = link.get("href", "")
                if f"hd={date_str}" in href and "jcd=" in href:
                    # jcd=XXを抽出
                    jcd_match = re.search(r"jcd=(\d+)", href)
                    if jcd_match:
                        venue_code = jcd_match.group(1)
                        if venue_code in self.VENUES and venue_code not in active_venues:
                            active_venues.append(venue_code)

            logger.info(f"📅 本日開催会場: {len(active_venues)}場")
            if active_venues:
                venue_names = [self.VENUES[code] for code in sorted(active_venues)]
                logger.info(f"   {', '.join(venue_names)}")

            return sorted(active_venues)

        except Exception as e:
            logger.warning(f"開催会場取得エラー: {e}")
            return []

    def fetch_races_for_date(self, target_date: datetime = None) -> list:
        """指定日のレースデータを公式サイトから取得（未開始レースのみ）"""
        if target_date is None:
            target_date = datetime.now()

        logger.info(f"📥 {target_date.strftime('%Y年%m月%d日')} のレースデータを取得中...")
        logger.info(f"⏰ 現在時刻: {datetime.now().strftime('%H:%M')}")

        # 開催会場を取得
        active_venues = self.fetch_active_venues(target_date)

        races = []
        date_str = target_date.strftime("%Y%m%d")

        # 各開催会場のレース情報を取得
        for venue_code in active_venues:
            try:
                venue_name = self.VENUES[venue_code]
                venue_races = self._fetch_races_for_venue(target_date, venue_code, venue_name)
                races.extend(venue_races)
                time.sleep(0.3)  # サーバー負荷軽減
            except Exception as e:
                logger.warning(f"  {venue_name} データ取得エラー: {e}")
                continue

        logger.info(f"📊 合計 {len(races)}件のレースを取得")
        return races

    def _fetch_races_for_venue(self, target_date: datetime, venue_code: str, venue_name: str) -> list:
        """指定会場のレースデータを取得（終了したレースは除外）"""
        races = []
        date_str = target_date.strftime("%Y%m%d")
        now = datetime.now()

        try:
            # 正確なエンドポイント: /owpc/pc/race/raceindex
            url = f"https://www.boatrace.jp/owpc/pc/race/raceindex?jcd={venue_code}&hd={date_str}"
            
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
            if len(rows) < 3:
                logger.info(f"  ℹ️  {venue_name}: 本日の開催なし")
                return races

            # 行2以降がレース情報
            for i in range(2, len(rows)):
                try:
                    row = rows[i]
                    cells = row.find_all(["td", "th"])

                    if len(cells) < 2:
                        continue

                    # セル[0]からR数を抽出
                    race_text = cells[0].get_text(strip=True)
                    race_num_match = re.search(r"(\d+)R?", race_text)
                    if not race_num_match:
                        continue

                    race_num = int(race_num_match.group(1))

                    # セル[1]から時刻を抽出
                    time_text = cells[1].get_text(strip=True)
                    time_match = re.search(r"(\d{1,2}):(\d{2})", time_text)
                    if not time_match:
                        continue

                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2))

                    race_datetime = target_date.replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )

                    # ⭐️ 重要：現在時刻より後のレースのみ取得
                    # 厳密な比較: race_datetime > now
                    if race_datetime <= now:
                        logger.debug(f"  スキップ（既終了）: {venue_name} {race_num}R ({hour:02d}:{minute:02d}) (現在時刻: {now.strftime('%H:%M')})")
                        continue

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

                except Exception as e:
                    logger.debug(f"  レース抽出エラー: {e}")
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
    if saved_today > 0:
        print("次のコマンドで予想を実行してください：")
        print("  python main.py --mode predict-today")
    if saved_tomorrow > 0:
        print("  python main.py --mode predict-tomorrow")
    print("━" * 60)
    print()


if __name__ == "__main__":
    main()
