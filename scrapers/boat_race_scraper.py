"""
ボートレースデータスクレイパー
ボートレース情報をWebから取得
"""

import requests
import logging
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from utils.logger import setup_logger

logger = setup_logger(__name__)


class BoatRaceScraper:
    """ボートレースデータ取得"""
    
    BASE_URL = "https://boatrace.jp"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_today_races(self):
        """当日のレース情報を取得"""
        logger.info("当日のレース情報を取得中...")
        try:
            races = self._fetch_races(datetime.now())
            logger.info(f"当日レース情報を取得: {len(races)}レース")
            return races
        except Exception as e:
            logger.error(f"当日レース取得エラー: {e}", exc_info=True)
            return []
    
    def get_tomorrow_races(self):
        """翌日のレース情報を取得"""
        logger.info("翌日のレース情報を取得中...")
        try:
            tomorrow = datetime.now() + timedelta(days=1)
            races = self._fetch_races(tomorrow)
            logger.info(f"翌日レース情報を取得: {len(races)}レース")
            return races
        except Exception as e:
            logger.error(f"翌日レース取得エラー: {e}", exc_info=True)
            return []
    
    def _fetch_races(self, date):
        """指定日付のレース情報を取得"""
        races = []
        try:
            # 公式サイトからレース一覧を取得
            url = f"{self.BASE_URL}/race"
            params = {'hd': date.strftime('%Y%m%d')}
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # レース情報をパース
            race_elements = soup.find_all('tr', class_='is-race')
            for element in race_elements:
                race = self._parse_race_element(element, date)
                if race:
                    races.append(race)
            
            return races
        except Exception as e:
            logger.error(f"レース情報取得エラー: {e}")
            return []
    
    def _parse_race_element(self, element, date):
        """レース要素をパース"""
        try:
            race_data = {}
            
            # レースID・場所・レース番号を抽出
            race_link = element.find('a')
            if race_link:
                href = race_link.get('href', '')
                # URLから情報を抽出: /race/20260723/01/01
                parts = href.strip('/').split('/')
                if len(parts) >= 4:
                    race_data['date'] = parts[2]
                    race_data['place_code'] = parts[3]
                    race_data['race_number'] = int(parts[4])
            
            # 時刻を抽出
            time_elem = element.find('td', class_='txt-time')
            if time_elem:
                race_data['start_time'] = time_elem.get_text(strip=True)
            
            # 天気を抽出
            weather_elem = element.find('td', class_='txt-weather')
            if weather_elem:
                race_data['weather'] = weather_elem.get_text(strip=True)
            
            # 水面状況を抽出
            water_elem = element.find('td', class_='txt-water')
            if water_elem:
                race_data['water_condition'] = water_elem.get_text(strip=True)
            
            return race_data if race_data else None
        except Exception as e:
            logger.debug(f"レース要素パースエラー: {e}")
            return None
    
    def get_race_details(self, place_code, race_number, date):
        """レース詳細情報を取得"""
        try:
            url = f"{self.BASE_URL}/race/{date}/{place_code}/{race_number}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            details = self._parse_race_details(soup)
            return details
        except Exception as e:
            logger.error(f"レース詳細取得エラー: {e}")
            return None
    
    def _parse_race_details(self, soup):
        """レース詳細をパース"""
        try:
            details = {
                'participants': [],
                'odds': {}
            }
            
            # 出走情報を抽出
            rider_rows = soup.find_all('tr', class_='is-runner')
            for row in rider_rows:
                participant = self._parse_participant(row)
                if participant:
                    details['participants'].append(participant)
            
            # オッズを抽出
            odds_table = soup.find('table', class_='odds-table')
            if odds_table:
                details['odds'] = self._parse_odds(odds_table)
            
            return details
        except Exception as e:
            logger.error(f"レース詳細パースエラー: {e}")
            return None
    
    def _parse_participant(self, row):
        """出走者情報をパース"""
        try:
            participant = {}
            
            # 枠番を取得
            frame_cell = row.find('td', class_='txt-frame')
            if frame_cell:
                participant['frame_number'] = int(frame_cell.get_text(strip=True))
            
            # 選手情報を取得
            rider_link = row.find('a', class_='txt-rider')
            if rider_link:
                participant['rider_name'] = rider_link.get_text(strip=True)
                participant['rider_id'] = rider_link.get('href', '').split('/')[-1]
            
            # 艇情報を取得
            boat_link = row.find('a', class_='txt-boat')
            if boat_link:
                participant['boat_number'] = int(boat_link.get_text(strip=True))
            
            return participant if participant else None
        except Exception as e:
            logger.debug(f"出走者パースエラー: {e}")
            return None
    
    def _parse_odds(self, odds_table):
        """オッズをパース"""
        odds = {}
        try:
            # 勝率オッズを抽出
            win_odds = odds_table.find('tbody', class_='is-win-odds')
            if win_odds:
                rows = win_odds.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        number = cells[0].get_text(strip=True)
                        odd = cells[1].get_text(strip=True)
                        odds[f'win_{number}'] = odd
            
            return odds
        except Exception as e:
            logger.debug(f"オッズパースエラー: {e}")
            return odds
    
    def close(self):
        """セッションを閉じる"""
        self.session.close()


if __name__ == "__main__":
    scraper = BoatRaceScraper()
    try:
        # 当日レース
        today_races = scraper.get_today_races()
        print(f"当日レース: {len(today_races)}件")
        
        # 翌日レース
        tomorrow_races = scraper.get_tomorrow_races()
        print(f"翌日レース: {len(tomorrow_races)}件")
    finally:
        scraper.close()
