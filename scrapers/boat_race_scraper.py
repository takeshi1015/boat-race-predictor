"""
boatrace.jp 公式サイト スクレイパー

当日開催場・レース情報・出走艇情報・結果配当を取得する。
"""

import re
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# boatrace.jp の公式ベースURL
BASE_URL = "https://www.boatrace.jp"

# 全24場コード→名前
VENUES = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島",
    "05": "多摩川", "06": "浜名湖", "07": "蒲郡", "08": "常滑",
    "09": "津", "10": "三国", "11": "びわこ", "12": "住之江",
    "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島",
    "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}

# 天気文字列→内部キー
_WEATHER_MAP = {
    "晴": "sunny", "晴れ": "sunny",
    "曇": "cloudy", "曇り": "cloudy",
    "雨": "rainy", "雨天": "rainy",
    "雪": "rainy",
}

# 水面状況→内部キー
_WATER_MAP = {
    "穏やか": "calm", "静水": "calm",
    "やや波": "slight", "小波": "slight",
    "波": "moderate", "中波": "moderate",
    "荒波": "rough", "大波": "rough",
}


def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    })
    return s


def _get(session: requests.Session, url: str, params: dict = None, timeout: int = 15) -> Optional[BeautifulSoup]:
    """HTTP GET with retry; returns BeautifulSoup or None."""
    for attempt in range(3):
        try:
            resp = session.get(url, params=params, timeout=timeout)
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                return BeautifulSoup(resp.content, "html.parser")
            logger.warning(f"HTTP {resp.status_code} for {url}")
            if attempt < 2:
                time.sleep(2 ** attempt)
        except Exception as exc:
            logger.warning(f"Request attempt {attempt + 1} failed: {exc}")
            if attempt < 2:
                time.sleep(2 ** attempt)
    return None


def _safe_float(text: str, default: float = 0.0) -> float:
    try:
        return float(re.sub(r"[^\d.\-]", "", text))
    except (ValueError, TypeError):
        return default


def _safe_int(text: str, default: int = 0) -> int:
    try:
        return int(re.sub(r"[^\d]", "", text))
    except (ValueError, TypeError):
        return default


# ============================================================================
# Public API
# ============================================================================

def fetch_today_races() -> list:
    """
    当日開催全場のレース情報を取得する。

    Returns:
        list[dict]: レース基本情報のリスト。
        {
            "race_id": "20260808_01_01",
            "date": datetime,
            "venue": "桐生",
            "venue_code": "01",
            "race_number": 1,
            "weather": "sunny",
            "water_condition": "calm",
            "wind_speed": 2.5,
            "start_time_hour": 15,
        }
    """
    today = datetime.now()
    return _fetch_races_for_date(today)


def _fetch_races_for_date(target_date: datetime) -> list:
    """指定日の全レース情報を取得する。"""
    session = _make_session()
    date_str = target_date.strftime("%Y%m%d")

    # Step 1: 開催場一覧を取得
    active_codes = _fetch_active_venue_codes(session, target_date)
    logger.info(f"開催場: {len(active_codes)}場 ({', '.join(active_codes)})")

    races = []
    for venue_code in active_codes:
        venue_name = VENUES.get(venue_code, venue_code)
        venue_races = _fetch_venue_racelist(session, venue_code, venue_name, date_str, target_date)
        races.extend(venue_races)

    logger.info(f"合計 {len(races)}件のレースを取得")
    return races


def _fetch_active_venue_codes(session: requests.Session, target_date: datetime) -> list:
    """当日の開催場コードを月間スケジュールから取得する。"""
    date_str = target_date.strftime("%Y%m%d")
    url = f"{BASE_URL}/owpc/pc/race/monthlyschedule"
    params = {"ym": target_date.strftime("%Y%m")}
    soup = _get(session, url, params=params)

    if soup is None:
        return sorted(VENUES.keys())

    codes = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if f"hd={date_str}" in href and "jcd=" in href:
            m = re.search(r"jcd=(\d{2})", href)
            if m:
                code = m.group(1)
                if code in VENUES and code not in codes:
                    codes.append(code)

    if codes:
        return sorted(codes)

    logger.warning("開催場コードが取得できませんでした。全場にフォールバックします。")
    return sorted(VENUES.keys())


def _fetch_venue_racelist(
    session: requests.Session,
    venue_code: str,
    venue_name: str,
    date_str: str,
    target_date: datetime,
) -> list:
    """指定場の当日レースリストを取得する。"""
    url = f"{BASE_URL}/owpc/pc/race/racelist"
    params = {"hd": date_str, "jcd": venue_code}
    soup = _get(session, url, params=params)

    races = []
    if soup is None:
        return races

    # レース一覧テーブルを探す
    for tbody in soup.find_all("tbody"):
        for tr in tbody.find_all("tr"):
            race = _parse_racelist_row(tr, venue_code, venue_name, date_str, target_date)
            if race:
                races.append(race)

    if not races:
        # フォールバック：12Rを予定として生成
        logger.debug(f"{venue_name}: レースリストのパース失敗、スキップ")

    return races


def _parse_racelist_row(
    tr,
    venue_code: str,
    venue_name: str,
    date_str: str,
    target_date: datetime,
) -> Optional[dict]:
    """レース一覧の1行をパースしてレース辞書を返す。"""
    try:
        # レース番号
        race_num_td = tr.find("td", class_=re.compile(r"is-fst"))
        if not race_num_td:
            # <a> タグからレース番号を探す
            a_tag = tr.find("a", href=re.compile(r"raceno=\d+"))
            if not a_tag:
                return None
            m = re.search(r"raceno=(\d+)", a_tag["href"])
            race_num = int(m.group(1)) if m else None
        else:
            race_num = _safe_int(race_num_td.get_text(strip=True))

        if not race_num:
            return None

        # レース時刻
        time_td = tr.find("td", class_=re.compile(r"time|schedule"))
        time_text = time_td.get_text(strip=True) if time_td else ""
        hour, minute = 12, 0
        m = re.search(r"(\d{1,2}):(\d{2})", time_text)
        if m:
            hour, minute = int(m.group(1)), int(m.group(2))

        race_datetime = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        race_id = f"{date_str}_{venue_code}_{race_num:02d}"

        return {
            "race_id": race_id,
            "date": race_datetime,
            "venue": venue_name,
            "place": venue_name,
            "venue_code": venue_code,
            "race_number": race_num,
            "start_time_hour": hour,
            "time_of_day": "morning" if hour < 12 else ("midday" if hour < 17 else "evening"),
            "number_of_boats": 6,
            "weather": "sunny",
            "water_condition": "calm",
            "water_surface": "calm",
            "wind_speed": 0.0,
            "temperature": 0.0,
            "humidity": 0.0,
        }
    except Exception as exc:
        logger.debug(f"行パースエラー: {exc}")
        return None


def fetch_race_details(venue_code: str, race_number: int, date_str: str) -> dict:
    """
    特定レースの詳細情報と出走艇情報を取得する。

    Returns:
        dict: {
            "race_info": {...},       # 天気・水面状況等
            "entries": [...],         # 6艇分の出走艇情報
        }
    """
    session = _make_session()
    url = f"{BASE_URL}/owpc/pc/race/racelist"
    params = {"hd": date_str, "jcd": venue_code, "rno": race_number}
    soup = _get(session, url, params=params)

    result = {"race_info": {}, "entries": []}

    if soup is None:
        return result

    # 天気・水面状況
    result["race_info"] = _parse_race_conditions(soup)

    # 出走表
    entries_url = f"{BASE_URL}/owpc/pc/race/beforeinfo"
    entries_params = {"hd": date_str, "jcd": venue_code, "rno": race_number}
    entries_soup = _get(session, entries_url, entries_params)
    if entries_soup:
        result["entries"] = _parse_entries(entries_soup)

    return result


def _parse_race_conditions(soup: BeautifulSoup) -> dict:
    """レースの天気・水面状況をパースする。"""
    info = {
        "weather": "sunny",
        "water_condition": "calm",
        "wind_speed": 0.0,
        "temperature": 0.0,
        "humidity": 0.0,
        "tide": "",
    }

    # 天気アイコン or テキスト
    weather_span = soup.find("span", class_=re.compile(r"weather|is-weather"))
    if weather_span:
        text = weather_span.get_text(strip=True)
        info["weather"] = _WEATHER_MAP.get(text, "sunny")

    # 風速
    wind_span = soup.find("span", class_=re.compile(r"wind"))
    if wind_span:
        info["wind_speed"] = _safe_float(wind_span.get_text(strip=True))

    # 水面状況
    water_span = soup.find("span", class_=re.compile(r"water"))
    if water_span:
        text = water_span.get_text(strip=True)
        info["water_condition"] = _WATER_MAP.get(text, "calm")

    return info


def _parse_entries(soup: BeautifulSoup) -> list:
    """出走表から6艇の選手・艇・エンジン情報をパースする。"""
    entries = []

    # boatrace.jp の出走表テーブル構造
    tbody = soup.find("tbody", class_=re.compile(r"is-w495"))
    if not tbody:
        tbody = soup.find("table", class_=re.compile(r"entry|runner|before"))
        if tbody:
            tbody = tbody.find("tbody")

    if not tbody:
        return entries

    for tr in tbody.find_all("tr", recursive=False):
        entry = _parse_entry_row(tr)
        if entry:
            entries.append(entry)

    return entries


def _parse_entry_row(tr) -> Optional[dict]:
    """出走表の1行をパースして艇情報を返す。"""
    try:
        tds = tr.find_all("td")
        if len(tds) < 3:
            return None

        # 枠番
        frame_td = tr.find("td", class_=re.compile(r"is-boatColor|frame|waku"))
        frame_num = _safe_int(frame_td.get_text(strip=True)) if frame_td else None
        if not frame_num or frame_num < 1 or frame_num > 6:
            return None

        # 選手名・ID
        player_a = tr.find("a", href=re.compile(r"torikumi|rider|player"))
        player_name = player_a.get_text(strip=True) if player_a else ""
        player_id = ""
        if player_a:
            m = re.search(r"(?:rid|player_id|id)=(\d+)", player_a.get("href", ""))
            if m:
                player_id = m.group(1)

        # 級別
        rank_td = tr.find("td", class_=re.compile(r"rank|class"))
        rank = rank_td.get_text(strip=True) if rank_td else ""

        # 勝率・連対率
        rate_tds = tr.find_all("td", class_=re.compile(r"rate|wins"))
        wins_rate = _safe_float(rate_tds[0].get_text(strip=True)) if len(rate_tds) > 0 else 0.0
        place_rate = _safe_float(rate_tds[1].get_text(strip=True)) if len(rate_tds) > 1 else 0.0

        return {
            "frame_number": frame_num,
            "player_name": player_name,
            "player_id": player_id,
            "rank": rank,
            "wins_rate": wins_rate,
            "place_rate": place_rate,
            "avg_start_timing": 0.0,
            "recent_results": [],
            "boat_number": "",
            "boat_wins_rate": 0.0,
            "engine_number": "",
            "engine_wins_rate": 0.0,
            "exhibition_time": 0.0,
        }
    except Exception as exc:
        logger.debug(f"エントリー行パースエラー: {exc}")
        return None


def fetch_race_result(race_id: str) -> dict:
    """
    レース終了後の結果・配当情報を取得する。

    Args:
        race_id: "20260808_01_01" 形式のレースID

    Returns:
        dict: {
            "race_id": ...,
            "first_place": 1, "second_place": 3, "third_place": 5,
            "payoff_win": 240, "payoff_exacta": 1820, "payoff_trifecta": 15200,
            ...
        }
    """
    parts = race_id.split("_")
    if len(parts) != 3:
        logger.error(f"不正なレースID: {race_id}")
        return {}

    date_str, venue_code, race_num_str = parts
    race_number = int(race_num_str)

    session = _make_session()
    url = f"{BASE_URL}/owpc/pc/race/raceresult"
    params = {"hd": date_str, "jcd": venue_code, "rno": race_number}
    soup = _get(session, url, params=params)

    if soup is None:
        return {}

    return _parse_race_result(soup, race_id)


def _parse_race_result(soup: BeautifulSoup, race_id: str) -> dict:
    """結果ページから着順・配当をパースする。"""
    result = {"race_id": race_id}

    # 着順テーブル
    result_tbody = soup.find("tbody", class_=re.compile(r"is-result|result"))
    if result_tbody:
        rows = result_tbody.find_all("tr")
        for i, row in enumerate(rows[:3]):
            tds = row.find_all("td")
            if tds:
                place_boat = _safe_int(tds[-1].get_text(strip=True))
                key = ["first_place", "second_place", "third_place"][i]
                result[key] = place_boat

    # 配当テーブル
    payoff_tables = soup.find_all("table", class_=re.compile(r"payoff|odds|haito"))
    for table in payoff_tables:
        rows = table.find_all("tr")
        for row in rows:
            th = row.find("th")
            td = row.find("td")
            if not th or not td:
                continue
            label = th.get_text(strip=True)
            amount = _safe_int(td.get_text(strip=True).replace(",", ""))
            if "単勝" in label or "Win" in label:
                result["payoff_win"] = amount
            elif "複勝" in label or "Place" in label:
                if "payoff_place_1" not in result:
                    result["payoff_place_1"] = amount
                else:
                    result["payoff_place_2"] = amount
            elif "2連単" in label or "Exacta" in label:
                result["payoff_exacta"] = amount
            elif "2連複" in label or "Quinella" in label:
                result["payoff_quinella"] = amount
            elif "3連単" in label or "Trifecta" in label:
                result["payoff_trifecta"] = amount
            elif "3連複" in label or "Trio" in label:
                result["payoff_trio"] = amount

    return result


def scrape_player_stats(player_id: str) -> dict:
    """
    選手の通算成績を取得する。

    Returns:
        dict: {
            "player_id": ...,
            "name": ...,
            "rank": ...,
            "wins_rate": ...,   # 勝率
            "place_rate": ...,  # 連対率
        }
    """
    session = _make_session()
    url = f"{BASE_URL}/owpc/pc/data/racersearch/detail"
    params = {"toban": player_id}
    soup = _get(session, url, params=params)

    stats = {"player_id": player_id}
    if soup is None:
        return stats

    # 選手名
    name_h3 = soup.find("h3", class_=re.compile(r"name|racer"))
    if name_h3:
        stats["name"] = name_h3.get_text(strip=True)

    # 成績テーブル
    for tr in soup.find_all("tr"):
        th = tr.find("th")
        td = tr.find("td")
        if not th or not td:
            continue
        label = th.get_text(strip=True)
        value = td.get_text(strip=True)
        if "勝率" in label:
            stats["wins_rate"] = _safe_float(value)
        elif "連対率" in label:
            stats["place_rate"] = _safe_float(value)
        elif "級別" in label or "ランク" in label:
            stats["rank"] = value

    return stats

