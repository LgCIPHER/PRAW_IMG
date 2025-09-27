"""Entry point for Reddit Image Scraper"""

import asyncio
import logging
from pathlib import Path
import os

from reddit_scraper.scraper import RedditImageScraper

async def main():
    """Main entry point"""
    print("Reddit Image Scraper")
    print("="*50)
    print("1. Scrape new images")
    print("2. Clean existing CSV files")
    print("3. Both (scrape then clean)")
    print("4. Clean specific subreddit's CSV")
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
    
    # Initialize scraper
    config_path = os.path.join(Path(__file__).parent, "reddit_config.json")
    scraper = RedditImageScraper(config_path)
    
    try:
        choice = input("Enter your choice (1-4): ").strip()
        
        if choice == "1":
            await scraper.run()
        elif choice == "2":
            await scraper.clean_csvs()
        elif choice == "3":
            await scraper.run()
            print("\nNow cleaning CSV files...")
            await scraper.clean_csvs()
        elif choice == "4":
            subreddit = input("Enter subreddit name: ").strip()
            await scraper.clean_csvs(subreddit)
        else:
            print("Invalid choice. Running scraper...")
            await scraper.run()
            
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