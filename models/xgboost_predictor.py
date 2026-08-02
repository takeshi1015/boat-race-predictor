"""
レース購入可能性判定モジュール

公式サイト情報に基づくリアルタイムフィルタリングロジック。
is_race_purchasable() と is_race_finished() を提供する。
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 購入締め切りまでの猶予（発走X分前まで購入可能）
PURCHASE_CUTOFF_MINUTES = 10


def is_race_purchasable(race_start_time: datetime, current_time: Optional[datetime] = None) -> bool:
    """
    レースが購入可能かを判定

    当日レースの購入可能条件:
    1. 発走予定時刻が「現在時刻から10分以上先」であること
    2. 発走時刻を過ぎていないこと

    Args:
        race_start_time: レース発走予定日時（JSTを前提）
        current_time:    現在日時（省略時は datetime.now()）

    Returns:
        True  購入可能（10分以上の余裕がある）
        False 購入不可（過去・10分未満）
    """
    if current_time is None:
        current_time = datetime.now()

    # 1. 既に発走時刻を過ぎている
    if race_start_time <= current_time:
        logger.debug(
            "購入不可: 発走済み %s <= 現在 %s",
            race_start_time.strftime("%H:%M"),
            current_time.strftime("%H:%M"),
        )
        return False

    # 2. 発走まで10分未満
    time_until_race = (race_start_time - current_time).total_seconds() / 60
    if time_until_race < PURCHASE_CUTOFF_MINUTES:
        logger.debug(
            "購入不可: 残り %.1f 分 (必要: %d 分以上)",
            time_until_race,
            PURCHASE_CUTOFF_MINUTES,
        )
        return False

    logger.debug(
        "購入可能: %s 発走 (あと %.1f 分)",
        race_start_time.strftime("%H:%M"),
        time_until_race,
    )
    return True


def is_race_finished(race_html: BeautifulSoup) -> bool:
    """
    レースが終了（着順確定）しているかを判定

    boatrace.jp のHTMLから「確」「確定」「結果」マークを検索し、
    結果表示エリアが存在するかを確認する。

    Args:
        race_html: レースページの BeautifulSoup オブジェクト

    Returns:
        True  終了済み（着順確定）
        False 未発走・発走中
    """
    # CSSクラスによる確定マーク検索
    confirmed_selectors = [
        ".is-result",
        ".is-fixed",
        ".kakutei",
        "[data-status='confirmed']",
        "[data-status='fixed']",
        ".result-label",
        ".race-result",
    ]
    for selector in confirmed_selectors:
        try:
            if race_html.select(selector):
                logger.debug("確定マーク検出 (selector: %s)", selector)
                return True
        except Exception:
            continue

    # テキストベースの確定マーク検索
    page_text = race_html.get_text()
    confirmed_texts = ["着順確定", "確定", "払戻金", "レース結果"]
    for text_mark in confirmed_texts:
        if text_mark in page_text:
            # 結果セクション内か確認
            result_sections = race_html.find_all(
                ["div", "table", "section"],
                class_=lambda c: c and any(
                    kw in c for kw in ["result", "kakutei", "pay", "return"]
                ),
            )
            if result_sections:
                logger.debug("着順確定テキスト検出: '%s'", text_mark)
                return True

    return False


def minutes_until_race(race_start_time: datetime, current_time: Optional[datetime] = None) -> float:
    """
    レース発走までの残り分数を返す

    Args:
        race_start_time: 発走予定日時
        current_time:    現在日時（省略時は datetime.now()）

    Returns:
        残り分数（負の場合は発走済み）
    """
    if current_time is None:
        current_time = datetime.now()
    return (race_start_time - current_time).total_seconds() / 60
