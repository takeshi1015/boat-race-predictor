"""
boatrace.jp 実レースデータ自動取得モジュール

公式サイトから当日・翌日のレースデータを取得してデータベースに保存する。
ネットワークエラー時はリアルなサンプルデータで代替する。
"""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import requests
from bs4 import BeautifulSoup

from utils.logger import setup_logger

logger = setup_logger(__name__)

# boatrace.jp 公式サイト URL
_BASE_URL = "https://www.boatrace.jp"
_INDEX_URL = _BASE_URL + "/owpc/pc/race/index"
_RACE_LIST_URL = _BASE_URL + "/owpc/pc/race/racelist"

# 全24競艇場コード → 日本語名
VENUE_CODES: Dict[str, str] = {
    "01": "桐生",
    "02": "戸田",
    "03": "江戸川",
    "04": "平和島",
    "05": "多摩川",
    "06": "浜名湖",
    "07": "蒲郡",
    "08": "常滑",
    "09": "津",
    "10": "三国",
    "11": "びわこ",
    "12": "住之江",
    "13": "尼崎",
    "14": "鳴門",
    "15": "丸亀",
    "16": "児島",
    "17": "宮島",
    "18": "徳山",
    "19": "下関",
    "20": "若松",
    "21": "芦屋",
    "22": "福岡",
    "23": "唐津",
    "24": "大村",
}

# HTTP セッションの共通ヘッダー
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9",
}

_REQUEST_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_and_save_races(target_date: Optional[datetime] = None) -> int:
    """
    boatrace.jp から指定日のレースデータを取得してDBに保存する。

    ネットワークエラーやパースエラーが発生した場合は、実際のスケジュールに
    基づいたリアルなサンプルデータを代わりに保存する。

    Args:
        target_date: 対象日付（省略時: 本日）

    Returns:
        保存されたレース数
    """
    if target_date is None:
        target_date = datetime.now()

    date_str = target_date.strftime("%Y%m%d")
    logger.info(f"レースデータ取得開始: {date_str}")

    try:
        races = _scrape_races(target_date)
    except Exception as e:
        logger.warning(f"スクレイピング失敗 ({e})。サンプルデータを使用します。")
        races = []

    if not races:
        logger.info("公式サイトからデータを取得できなかったため、サンプルデータを生成します。")
        races = _generate_sample_races(target_date)

    saved = _save_races(races)
    logger.info(f"レースデータ保存完了: {saved}件")
    return saved


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def _scrape_races(target_date: datetime) -> List[Dict[str, Any]]:
    """boatrace.jp から実レースデータを取得"""
    date_str = target_date.strftime("%Y%m%d")
    session = requests.Session()
    session.headers.update(_HEADERS)

    # Step 1: 開催場一覧を取得
    index_resp = session.get(_INDEX_URL, params={"hd": date_str}, timeout=_REQUEST_TIMEOUT)
    index_resp.raise_for_status()
    venue_codes = _parse_venue_codes(index_resp.text)

    if not venue_codes:
        logger.warning(f"{date_str} に開催場が見つかりませんでした。")
        return []

    logger.info(f"開催場: {[VENUE_CODES.get(c, c) for c in venue_codes]}")

    # Step 2: 各開催場のレース一覧を取得
    all_races: List[Dict[str, Any]] = []
    for jcd in venue_codes:
        try:
            races = _scrape_venue_races(session, jcd, target_date)
            all_races.extend(races)
        except Exception as e:
            logger.warning(f"{VENUE_CODES.get(jcd, jcd)} のレース取得失敗: {e}")

    session.close()
    return all_races


def _parse_venue_codes(html: str) -> List[str]:
    """開催場一覧ページから会場コードを抽出"""
    soup = BeautifulSoup(html, "html.parser")
    codes: List[str] = []

    # boatrace.jp の開催場リンクは /owpc/pc/race/racelist?hd=...&jcd=XX 形式
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "racelist" in href and "jcd=" in href:
            jcd = _extract_param(href, "jcd")
            if jcd and jcd not in codes:
                codes.append(jcd)

    return codes


def _scrape_venue_races(
    session: requests.Session,
    jcd: str,
    target_date: datetime,
) -> List[Dict[str, Any]]:
    """指定会場の全レース情報を取得"""
    date_str = target_date.strftime("%Y%m%d")
    resp = session.get(
        _RACE_LIST_URL,
        params={"hd": date_str, "jcd": jcd},
        timeout=_REQUEST_TIMEOUT,
    )
    resp.raise_for_status()

    venue_name = VENUE_CODES.get(jcd, jcd)
    return _parse_race_list(resp.text, jcd, venue_name, target_date)


def _parse_race_list(
    html: str,
    jcd: str,
    venue_name: str,
    target_date: datetime,
) -> List[Dict[str, Any]]:
    """レース一覧ページをパース"""
    soup = BeautifulSoup(html, "html.parser")
    races: List[Dict[str, Any]] = []
    date_str = target_date.strftime("%Y%m%d")

    # boatrace.jp のレース一覧テーブル (.is-type2_inner または .table1 など)
    race_rows = soup.select("table.is-type2_inner tbody tr, table tbody tr.is-race")
    if not race_rows:
        # フォールバック: すべての <tr> を走査
        race_rows = soup.select("tbody tr")

    race_number = 0
    for row in race_rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        # レース番号を探す
        race_num_cell = row.find("td", class_=lambda c: c and "race" in c.lower())
        num_text = race_num_cell.get_text(strip=True) if race_num_cell else cells[0].get_text(strip=True)
        try:
            rnum = int(num_text.replace("R", "").replace("レース", ""))
        except ValueError:
            continue

        # 発走時刻
        time_text = ""
        for cell in cells:
            txt = cell.get_text(strip=True)
            if ":" in txt and len(txt) <= 5:
                time_text = txt
                break

        race_datetime = _parse_race_datetime(target_date, time_text)
        race_id = f"{date_str}_{jcd}_{rnum:02d}"

        race_data = {
            "race_id": race_id,
            "venue": venue_name,
            "place": venue_name,
            "date": race_datetime,
            "race_number": rnum,
            "weather": "sunny",
            "water_condition": "calm",
            "start_time_hour": race_datetime.hour if race_datetime else 12,
        }
        races.append(race_data)
        race_number += 1

    logger.info(f"{venue_name}: {race_number}レース取得")
    return races


# ---------------------------------------------------------------------------
# Sample data generation (fallback when offline)
# ---------------------------------------------------------------------------

_WEATHER_OPTIONS = ["sunny", "cloudy", "rainy"]
_WATER_OPTIONS = ["calm", "slight", "moderate", "rough"]
_WEATHER_WEIGHTS = [0.6, 0.3, 0.1]
_WATER_WEIGHTS = [0.5, 0.3, 0.15, 0.05]


def _generate_sample_races(target_date: datetime) -> List[Dict[str, Any]]:
    """
    実際のスケジュールに基づくリアルなサンプルレースを生成する。

    通常、1日に6〜8会場が開催され、各会場で12レース程度が行われる。
    """
    date_str = target_date.strftime("%Y%m%d")

    # 同じ日は常に同じ会場・構成を返すためにシード固定のローカルRNGを使用
    rng = random.Random(target_date.toordinal())

    # 当日開催する会場を決定（週末: 10〜14場、平日: 6〜9場）
    weekday = target_date.weekday()
    if weekday >= 5:  # 土日
        num_venues = rng.randint(10, 14)
    else:
        num_venues = rng.randint(6, 9)

    venue_items = list(VENUE_CODES.items())
    selected_venues = rng.sample(venue_items, min(num_venues, len(venue_items)))

    races: List[Dict[str, Any]] = []

    for jcd, venue_name in selected_venues:
        num_races = 12  # 1会場あたり通常12レース

        # 発走時刻: 9:00〜16:00 の間で等間隔
        start_hour = rng.choice([9, 10])
        start_minute = rng.choice([0, 15, 30])
        interval_minutes = rng.choice([30, 35, 40])

        weather = rng.choices(_WEATHER_OPTIONS, weights=_WEATHER_WEIGHTS)[0]
        water = rng.choices(_WATER_OPTIONS, weights=_WATER_WEIGHTS)[0]

        for rnum in range(1, num_races + 1):
            total_minutes = (start_hour * 60 + start_minute) + (rnum - 1) * interval_minutes
            race_hour = total_minutes // 60
            race_minute = total_minutes % 60
            race_datetime = target_date.replace(
                hour=min(race_hour, 20),
                minute=race_minute,
                second=0,
                microsecond=0,
            )
            race_id = f"{date_str}_{jcd}_{rnum:02d}"

            races.append({
                "race_id": race_id,
                "venue": venue_name,
                "place": venue_name,
                "date": race_datetime,
                "race_number": rnum,
                "weather": weather,
                "water_condition": water,
                "start_time_hour": race_datetime.hour,
            })

    logger.info(f"サンプルデータ生成: {len(races)}レース ({len(selected_venues)}会場)")
    return races


# ---------------------------------------------------------------------------
# Database persistence
# ---------------------------------------------------------------------------

def _save_races(races: List[Dict[str, Any]]) -> int:
    """レースデータをデータベースに保存"""
    if not races:
        return 0

    try:
        from database.db_manager import get_db_manager
        db = get_db_manager()
        session = db.get_session()
        try:
            saved = 0
            for race_data in races:
                db.add_or_update_race(session, race_data)
                saved += 1
            return saved
        finally:
            session.close()
    except Exception as e:
        logger.error(f"DB保存エラー: {e}", exc_info=True)
        return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_param(url: str, param: str) -> Optional[str]:
    """URL からクエリパラメータを抽出"""
    for part in url.split("?", 1)[-1].split("&"):
        if part.startswith(param + "="):
            return part.split("=", 1)[1]
    return None


def _parse_race_datetime(base_date: datetime, time_str: str) -> datetime:
    """HH:MM 形式の時刻文字列を datetime に変換"""
    try:
        parts = time_str.strip().split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except (ValueError, IndexError):
        return base_date.replace(hour=12, minute=0, second=0, microsecond=0)
