"""
Scraper package initialization
"""

from scraper.boat_race_scraper import BoatRaceScraper
from scraper.specialty_scraper import SpecialtyScraper
from scraper.social_scraper import SocialScraper
from scraper.web_scraper import WebScraper
from scraper.api_client import APIClient
from scraper.csv_importer import CSVImporter

__all__ = [
    "BoatRaceScraper",
    "SpecialtyScraper",
    "SocialScraper",
    "WebScraper",
    "APIClient",
    "CSVImporter",
]
