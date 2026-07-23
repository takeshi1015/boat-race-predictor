"""
Boat Race Official Site Scraper (boatrace.jp)
"""

import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import config
from utils.logger import logger


class BoatRaceScraper:
    """Scraper for boatrace.jp official site"""
    
    def __init__(self):
        """Initialize scraper"""
        self.base_url = config.BOATRACE_BASE_URL
        self.schedule_url = config.BOATRACE_SCHEDULE_URL
        self.headers = {
            "User-Agent": config.USER_AGENT
        }
        self.timeout = config.REQUEST_TIMEOUT
        self.max_retries = config.MAX_RETRIES
        self.retry_backoff = config.RETRY_BACKOFF
        
        # Optional: Setup Selenium for JavaScript-heavy sites
        self.driver = None
    
    def get_race_schedule(self, date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Get race schedule for specific date
        
        Args:
            date: Date to get schedule for (default: today)
            
        Returns:
            List of race information
        """
        if date is None:
            date = datetime.now()
        
        date_str = date.strftime("%Y%m%d")
        logger.info(f"Fetching race schedule for {date_str}")
        
        try:
            # Example endpoint for boatrace.jp
            url = f"{self.base_url}/cgi-bin/race/race_list.cgi?d={date_str}"
            response = self._fetch_with_retry(url)
            
            if response is None:
                logger.warning(f"Failed to fetch schedule for {date_str}")
                return []
            
            races = self._parse_schedule(response.text)
            logger.info(f"Found {len(races)} races for {date_str}")
            return races
            
        except Exception as e:
            logger.error(f"Error fetching race schedule: {e}")
            return []
    
    def get_race_details(self, race_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed race information
        
        Args:
            race_id: Race ID (format: venue_date_race_number)
            
        Returns:
            Race details dictionary
        """
        logger.info(f"Fetching race details for {race_id}")
        
        try:
            url = f"{self.base_url}/cgi-bin/race/race.cgi?rc={race_id}"
            response = self._fetch_with_retry(url)
            
            if response is None:
                return None
            
            race_details = self._parse_race_details(response.text, race_id)
            return race_details
            
        except Exception as e:
            logger.error(f"Error fetching race details: {e}")
            return None
    
    def get_player_stats(self, player_id: str) -> Optional[Dict[str, Any]]:
        """
        Get player statistics
        
        Args:
            player_id: Player ID
            
        Returns:
            Player statistics dictionary
        """
        logger.info(f"Fetching player stats for {player_id}")
        
        try:
            url = f"{self.base_url}/cgi-bin/rider/rider.cgi?rid={player_id}"
            response = self._fetch_with_retry(url)
            
            if response is None:
                return None
            
            player_stats = self._parse_player_stats(response.text)
            player_stats["player_id"] = player_id
            return player_stats
            
        except Exception as e:
            logger.error(f"Error fetching player stats: {e}")
            return None
    
    def get_boat_stats(self, venue: str, boat_number: int) -> Optional[Dict[str, Any]]:
        """
        Get boat statistics
        
        Args:
            venue: Venue code
            boat_number: Boat number (1-6)
            
        Returns:
            Boat statistics dictionary
        """
        logger.info(f"Fetching boat stats for {venue} boat {boat_number}")
        
        try:
            url = f"{self.base_url}/cgi-bin/boat/boat.cgi?v={venue}&b={boat_number}"
            response = self._fetch_with_retry(url)
            
            if response is None:
                return None
            
            boat_stats = self._parse_boat_stats(response.text)
            boat_stats["venue"] = venue
            boat_stats["boat_number"] = boat_number
            return boat_stats
            
        except Exception as e:
            logger.error(f"Error fetching boat stats: {e}")
            return None
    
    def get_race_results(self, date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Get race results for specific date
        
        Args:
            date: Date to get results for
            
        Returns:
            List of race results
        """
        if date is None:
            date = datetime.now() - timedelta(days=1)
        
        date_str = date.strftime("%Y%m%d")
        logger.info(f"Fetching race results for {date_str}")
        
        try:
            url = f"{self.base_url}/cgi-bin/race/race_result.cgi?d={date_str}"
            response = self._fetch_with_retry(url)
            
            if response is None:
                return []
            
            results = self._parse_results(response.text)
            logger.info(f"Found {len(results)} results for {date_str}")
            return results
            
        except Exception as e:
            logger.error(f"Error fetching race results: {e}")
            return []
    
    # ============================================================================
    # Helper Methods
    # ============================================================================
    
    def _fetch_with_retry(self, url: str) -> Optional[requests.Response]:
        """
        Fetch URL with retry logic
        
        Args:
            url: URL to fetch
            
        Returns:
            Response object or None if failed
        """
        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_backoff ** attempt
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to fetch {url} after {self.max_retries} attempts")
                    return None
    
    def _parse_schedule(self, html: str) -> List[Dict[str, Any]]:
        """Parse race schedule from HTML"""
        soup = BeautifulSoup(html, "html.parser")
        races = []
        
        # This is a template - actual parsing depends on boatrace.jp structure
        try:
            race_table = soup.find("table", {"class": "race_list"})
            if race_table:
                for row in race_table.find_all("tr")[1:]:
                    cols = row.find_all("td")
                    if len(cols) >= 5:
                        race_data = {
                            "race_number": cols[0].text.strip(),
                            "time": cols[1].text.strip(),
                            "grade": cols[2].text.strip(),
                            "distance": cols[3].text.strip(),
                            "entries": cols[4].text.strip(),
                        }
                        races.append(race_data)
        except Exception as e:
            logger.error(f"Error parsing schedule: {e}")
        
        return races
    
    def _parse_race_details(self, html: str, race_id: str) -> Dict[str, Any]]:
        """Parse race details from HTML"""
        soup = BeautifulSoup(html, "html.parser")
        race_details = {"race_id": race_id}
        
        try:
            # Extract race conditions
            conditions = soup.find("div", {"class": "race_conditions"})
            if conditions:
                race_details["weather"] = conditions.find("span", {"class": "weather"}).text if conditions.find("span", {"class": "weather"}) else ""
                race_details["wind_speed"] = conditions.find("span", {"class": "wind"}).text if conditions.find("span", {"class": "wind"}) else ""
                race_details["water_surface"] = conditions.find("span", {"class": "water"}).text if conditions.find("span", {"class": "water"}) else ""
            
            # Extract entries
            entries = []
            entry_table = soup.find("table", {"class": "entry_list"})
            if entry_table:
                for row in entry_table.find_all("tr")[1:]:
                    cols = row.find_all("td")
                    if len(cols) >= 5:
                        entry = {
                            "position": cols[0].text.strip(),
                            "player_id": cols[1].text.strip(),
                            "player_name": cols[2].text.strip(),
                            "boat_number": cols[3].text.strip(),
                        }
                        entries.append(entry)
            race_details["entries"] = entries
            
        except Exception as e:
            logger.error(f"Error parsing race details: {e}")
        
        return race_details
    
    def _parse_player_stats(self, html: str) -> Dict[str, Any]]:
        """Parse player statistics from HTML"""
        soup = BeautifulSoup(html, "html.parser")
        player_stats = {}
        
        try:
            # Extract statistics
            stats_div = soup.find("div", {"class": "player_stats"})
            if stats_div:
                player_stats["win_rate"] = self._extract_float(stats_div, "win_rate", 0.0)
                player_stats["place_rate"] = self._extract_float(stats_div, "place_rate", 0.0)
                player_stats["payoff_rate"] = self._extract_float(stats_div, "payoff_rate", 0.0)
                player_stats["avg_speed"] = self._extract_float(stats_div, "avg_speed", 0.0)
            
        except Exception as e:
            logger.error(f"Error parsing player stats: {e}")
        
        return player_stats
    
    def _parse_boat_stats(self, html: str) -> Dict[str, Any]]:
        """Parse boat statistics from HTML"""
        soup = BeautifulSoup(html, "html.parser")
        boat_stats = {}
        
        try:
            stats_div = soup.find("div", {"class": "boat_stats"})
            if stats_div:
                boat_stats["boat_win_rate"] = self._extract_float(stats_div, "win_rate", 0.0)
                boat_stats["boat_place_rate"] = self._extract_float(stats_div, "place_rate", 0.0)
                boat_stats["boat_age"] = self._extract_int(stats_div, "age", 0)
            
        except Exception as e:
            logger.error(f"Error parsing boat stats: {e}")
        
        return boat_stats
    
    def _parse_results(self, html: str) -> List[Dict[str, Any]]:
        """Parse race results from HTML"""
        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        try:
            result_table = soup.find("table", {"class": "result_list"})
            if result_table:
                for row in result_table.find_all("tr")[1:]:
                    cols = row.find_all("td")
                    if len(cols) >= 6:
                        result = {
                            "race_number": cols[0].text.strip(),
                            "1st": cols[1].text.strip(),
                            "2nd": cols[2].text.strip(),
                            "3rd": cols[3].text.strip(),
                            "odds": cols[4].text.strip(),
                            "payoff": cols[5].text.strip(),
                        }
                        results.append(result)
        except Exception as e:
            logger.error(f"Error parsing results: {e}")
        
        return results
    
    @staticmethod
    def _extract_float(element, class_name: str, default: float = 0.0) -> float:
        """Extract float value from HTML element"""
        try:
            elem = element.find(class_=class_name)
            if elem:
                return float(elem.text.strip().replace("%", ""))
        except (ValueError, AttributeError):
            pass
        return default
    
    @staticmethod
    def _extract_int(element, class_name: str, default: int = 0) -> int:
        """Extract integer value from HTML element"""
        try:
            elem = element.find(class_=class_name)
            if elem:
                return int(elem.text.strip())
        except (ValueError, AttributeError):
            pass
        return default
    
    def close(self):
        """Close driver if using Selenium"""
        if self.driver:
            self.driver.quit()
            logger.info("Selenium driver closed")
