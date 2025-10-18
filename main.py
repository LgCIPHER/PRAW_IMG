"""Entry point for Reddit Image Scraper"""

import asyncio
import logging
from pathlib import Path
import os
from datetime import datetime

from reddit_scraper.scraper import RedditImageScraper
from reddit_scraper.core.base import EventManager
from reddit_scraper.core.commands import (
    ScrapeImagesCommand,
    CleanCsvCommand,
    CombinedCommand,
    ScrapeSpecificCommand
)
from reddit_scraper.core.base import ScraperEvent, EventManager, ProgressStats

# Set up event handlers
async def on_progress_update(event: ScraperEvent) -> None:
    """Handle progress update events."""
    stats: ProgressStats = event.data["stats"]
    stats.calculate_eta()
    print(f"\rProcessing {stats.current_subreddit}: "
          f"Batch {stats.current_batch}/{stats.total_batches} "
          f"({stats.processed_posts}/{stats.total_posts} posts) "
          f"[{stats.processed_subreddits}/{stats.total_subreddits} subreddits] "
          f"ETA: {stats.estimated_completion_time.strftime('%H:%M:%S') if stats.estimated_completion_time else 'calculating...'}",
          end="")

async def main():
    """Main entry point"""
    print("Reddit Image Scraper")
    print("="*50)
    print("1. Scrape new images")
    print("2. Clean existing CSV files")
    print("3. Both (scrape then clean)")
    print("4. Clean specific subreddit's CSV")
    print("5. Scrape specific subreddit")
    print("="*50)
    
    # Set up logging with UTF-8 encoding
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('reddit_scraper.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # Initialize components
    config_path = os.path.join(Path(__file__).parent, "reddit_config.json")
    scraper = RedditImageScraper(config_path)
    event_manager = EventManager()
    
    # Set up event handlers
    event_manager.subscribe("progress_update", on_progress_update)
    scraper.set_event_manager(event_manager)
    
    try:
        choice = input("Enter your choice (1-5): ").strip()
        
        # Create appropriate command based on user choice
        command: Optional[ScraperCommand] = None
        
        if choice == "1":
            command = ScrapeImagesCommand(scraper)
        elif choice == "2":
            command = CleanCsvCommand(scraper)
        elif choice == "3":
            command = CombinedCommand(scraper)
        elif choice == "4":
            subreddit = input("Enter subreddit name: ").strip()
            command = CleanCsvCommand(scraper, subreddit)
        elif choice == "5":
            subreddit = input("Enter subreddit name: ").strip()
            command = ScrapeSpecificCommand(scraper, subreddit)
        else:
            print("Invalid choice. Running scraper...")
            command = ScrapeImagesCommand(scraper)
        
        # Execute the command
        await command.execute()
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        # Ensure proper cleanup of resources
        if hasattr(scraper, 'image_processor') and scraper.image_processor:
            if hasattr(scraper.image_processor, 'session') and scraper.image_processor.session:
                await scraper.image_processor.session.close()
        
        if hasattr(scraper, 'reddit') and scraper.reddit:
            await scraper.reddit.close()

if __name__ == "__main__":
    asyncio.run(main())