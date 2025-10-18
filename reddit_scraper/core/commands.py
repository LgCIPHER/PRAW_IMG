"""Command implementations for Reddit Image Scraper."""

from typing import Optional
from .base import ScraperCommand, ScraperState
from ..scraper import RedditImageScraper

class ScrapeImagesCommand(ScraperCommand):
    """Command for scraping new images."""
    def __init__(self, scraper: RedditImageScraper):
        self.scraper = scraper

    async def execute(self) -> None:
        """Execute the scrape images command."""
        await self.scraper.run()

class CleanCsvCommand(ScraperCommand):
    """Command for cleaning CSV files."""
    def __init__(self, scraper: RedditImageScraper, subreddit: Optional[str] = None):
        self.scraper = scraper
        self.subreddit = subreddit

    async def execute(self) -> None:
        """Execute the clean CSV command."""
        await self.scraper.clean_csvs(self.subreddit)

class CombinedCommand(ScraperCommand):
    """Command for scraping and then cleaning."""
    def __init__(self, scraper: RedditImageScraper):
        self.scraper = scraper

    async def execute(self) -> None:
        """Execute both scrape and clean commands in sequence."""
        await self.scraper.run()
        print("\nNow cleaning CSV files...")
        await self.scraper.clean_csvs()

class ScrapeSpecificCommand(ScraperCommand):
    """Command for scraping a specific subreddit."""
    def __init__(self, scraper: RedditImageScraper, subreddit: str):
        self.scraper = scraper
        self.subreddit = subreddit

    async def execute(self) -> None:
        """Execute the scrape specific subreddit command."""
        await self.scraper.run_specific(self.subreddit)