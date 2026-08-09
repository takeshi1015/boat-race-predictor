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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def fetch_races_for_date(self, target_date: datetime = None) -> list:
        """指定日のレースデータを公式サイトから取得"""
        if target_date is None:
            target_date = datetime.now()

        logger.info(f"📥 {target_date.strftime('%Y年%m月%d日')} のレースデータを取得中...")

        # 公式サイトから開催会場を取得
        active_venues = self._fetch_active_venues(target_date)
        logger.info(f"   ✅ 開催会場: {', '.join(active_venues)}")

        # 各会場の実レースデータを取得
        races = self._fetch_races_from_official_site(target_date, active_venues)
        logger.info(f"📊 合計 {len(races)}件のレースを取得")

        return races

    def _fetch_active_venues(self, target_date: datetime) -> list:
        """boatrace.jp から指定日に開催される会場のリストを取得"""
        active_venues = []
        date_str = target_date.strftime("%Y%m%d")

        try:
            # 月間スケジュールページを取得
            url = "https://www.boatrace.jp/owpc/pc/race/monthlyschedule"
            params = {"ym": target_date.strftime("%Y%m")}
            response = self.session.get(url, params=params, timeout=10)
            response.encoding = "utf-8"

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")

                # 対象日のリンクを探す (hd=YYYYMMDD を含む)
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag.get("href", "")
                    if f"hd={date_str}" in href and "jcd=" in href:
                        # jcd=XX を抽出
                        jcd_pos = href.find("jcd=")
                        if jcd_pos != -1:
                            venue_code = href[jcd_pos + 4: jcd_pos + 6]
                            if venue_code in self.VENUES and venue_code not in active_venues:
                                active_venues.append(venue_code)

                if active_venues:
                    return sorted(active_venues)

            logger.debug("   対象日のレースリンクが見つかりません")

        except Exception as e:
            logger.warning(f"   開催会場取得エラー: {e}")

        # フォールバック: 全会場を返す
        logger.warning("   ⚠️  デフォルトで全会場を対象に取得します")
        return sorted(self.VENUES.keys())

    def _fetch_races_from_official_site(self, target_date: datetime, venue_codes: list) -> list:
        """公式サイトから各会場の実レースデータを取得"""
        races = []
        date_str = target_date.strftime("%Y%m%d")

        for venue_code in venue_codes:
            try:
                venue_name = self.VENUES.get(venue_code, "不明")
                
                # 各会場のレースリストを取得
                url = f"https://www.boatrace.jp/owpc/pc/race/index?hd={date_str}&jcd={venue_code}"
                response = self.session.get(url, timeout=10)
                response.encoding = "utf-8"

                if response.status_code != 200:
                    logger.warning(f"  ⚠️  {venue_name}: HTTPエラー {response.status_code}")
                    continue

                soup = BeautifulSoup(response.content, "html.parser")

                # レース情報をパース
                race_elements = soup.find_all("tr", class_="is-number")
                
                if not race_elements:
                    logger.info(f"  ℹ️  {venue_name}: 本日の開催なし")
                    continue

                for race_elem in race_elements:
                    try:
                        # レース番号と開始時刻を取得
                        race_num_td = race_elem.find("td", class_="is-number")
                        if not race_num_td:
                            continue

                        race_num_text = race_num_td.get_text(strip=True)
                        if not race_num_text.isdigit():
                            continue

                        race_num = int(race_num_text)

                        # 開始時刻を取得 (通常は2番目のtd)
                        tds = race_elem.find_all("td")
                        if len(tds) < 2:
                            continue

                        time_text = tds[1].get_text(strip=True)
                        # "12:15" 形式を解析
                        if ":" not in time_text:
                            continue

                        try:
                            hour, minute = map(int, time_text.split(":"))
                        except ValueError:
                            continue

                        race_datetime = target_date.replace(
                            hour=hour, minute=minute, second=0, microsecond=0
                        )

                        race_data = {
                            "race_id": f"{date_str}_{venue_code}_{race_num:02d}",
                            "date": race_datetime,
                            "venue": venue_name,
                            "place": venue_name,
                            "race_number": race_num,
                            "weather": "sunny",  # デフォルト
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
                        logger.debug(f"  レース情報パースエラー: {e}")
                        continue

            except Exception as e:
                logger.warning(f"  {venue_name} データ取得エラー: {e}")
                continue

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
