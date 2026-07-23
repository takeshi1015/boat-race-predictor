"""
Scraper package initialization
"""

from scraper.boat_race_scraper import BoatRaceScraper
from scraper.specialty_scraper import SpecialtyScraper
from scraper.social_scraper import SocialScraper

__all__ = [
    "BoatRaceScraper",
    "SpecialtyScraper",
    "SocialScraper",
]
