"""
ボートレース公式サイトのスクレイピングモジュール
"""

from utils.logger import setup_logger

logger = setup_logger(__name__)

# 公式サイトURL
BOATRACE_SCHEDULE_URL = "https://boatrace.jp/race/schedule"

# 場コードから場名へのマッピング
PLACE_CODE_TO_NAME = {
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

NAME_TO_PLACE_CODE = {v: k for k, v in PLACE_CODE_TO_NAME.items()}


def scrape_boatrace_schedule() -> list:
    """
    ボートレース公式サイトから本日の開催スケジュールをスクレイピング。

    Returns:
        開催中の会場名リスト（スクレイピング失敗時は空リスト）
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(BOATRACE_SCHEDULE_URL, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        return parse_venue_data(soup)

    except Exception as e:
        logger.warning(f"公式サイトのスクレイピングに失敗しました: {e}")
        return []


def parse_venue_data(soup) -> list:
    """
    BeautifulSoup でパースされたHTMLから開催場所リストを抽出。

    Args:
        soup: BeautifulSoup オブジェクト

    Returns:
        開催中の会場名リスト
    """
    operating_venues = []

    try:
        # 公式サイトの開催場リンク（href="/race/resultlist?jcd=XX&..."）を探す
        links = soup.find_all("a", href=True)
        for link in links:
            href = link.get("href", "")
            # 場コードを含むリンクを検索
            for code, name in PLACE_CODE_TO_NAME.items():
                if f"jcd={code}" in href and name not in operating_venues:
                    operating_venues.append(name)
                    break

        # 別の形式（テキストから場名を直接検索）
        if not operating_venues:
            for name in PLACE_CODE_TO_NAME.values():
                if soup.find(string=lambda t: t and name in t):
                    if name not in operating_venues:
                        operating_venues.append(name)

    except Exception as e:
        logger.warning(f"HTML パースに失敗しました: {e}")

    return operating_venues
