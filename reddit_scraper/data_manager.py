"""Data management for Reddit Image Scraper"""

import os
import aiocsv
from dataclasses import dataclass
from typing import List, Dict, Set, Optional
import logging
import aiofiles

@dataclass
class RedditPost:
    """Represents a Reddit post with image"""
    id: int
    subreddit_name: str
    post_title: str
    reddit_link: str
    processed: bool = False

class DataManager:
    """Handles all data persistence operations"""
    
    def __init__(self):
        # Get the parent directory (PRAW_IMG folder)
        self.dir_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        self.logger = logging.getLogger(__name__)
        self.cleaner = None  # Lazy initialization of CSVCleaner
        
    def get_file_path(self, filename: str) -> str:
        """Get absolute path for a file"""
        return os.path.join(self.dir_path, filename)
        
    async def read_subreddit_list(self, file_path: str) -> List[str]:
        """Read and validate subreddit names from CSV"""
        subreddits = []
        
        if not os.path.exists(file_path):
            self.logger.error(f"Subreddit list file not found: {file_path}")
            return subreddits
        
        try:
            async with aiofiles.open(file_path, mode='r', encoding='utf-8-sig') as f:
                content = await f.read()
                for line_num, line in enumerate(content.splitlines(), 1):
                    sub = line.strip()
                    if sub and not sub.startswith('#'):
                        if self._validate_subreddit_name(sub):
                            subreddits.append(sub)
                        else:
                            self.logger.warning(f"Invalid subreddit name on line {line_num}: {sub}")
                            
            self.logger.info(f"✓ Found {len(subreddits)} subreddits to process")
            return subreddits
            
        except Exception as e:
            self.logger.error(f"Error reading subreddit list: {e}")
            return subreddits

    def _validate_subreddit_name(self, name: str) -> bool:
        """Validate subreddit name format"""
        return (len(name) <= 50 and 
                name.replace('_', '').replace('-', '').isalnum())

    async def read_existing_urls(self, file_path: str) -> Set[str]:
        """Read existing URLs from CSV file"""
        urls = set()
        
        if not os.path.exists(file_path):
            self.logger.info(f"No existing file found: {file_path}")
            return urls
            
        try:
            async with aiofiles.open(file_path, mode='r', encoding='utf-8-sig') as f:
                reader = aiocsv.AsyncDictReader(f)
                async for row in reader:
                    if row.get('reddit_link'):
                        urls.add(row['reddit_link'].lower())
                        
            self.logger.info(f"✓ Loaded {len(urls)} existing URLs from {os.path.basename(file_path)}")
            return urls
            
        except Exception as e:
            self.logger.error(f"Error reading URLs: {e}")
            return urls

    async def save_posts(self, posts: List[RedditPost], file_path: str, 
                        description: str = "URLs", append: bool = False) -> bool:
        """Save posts to CSV file"""
        if not posts:
            self.logger.info(f"No {description.lower()} to save")
            return True
            
        try:
            mode = "a" if append and os.path.exists(file_path) else "w"
            headers = ['id', 'subreddit_name', 'post_title', 'reddit_link']
            
            async with aiofiles.open(file_path, mode=mode, encoding='utf-8-sig', 
                                   newline='') as f:
                writer = aiocsv.AsyncDictWriter(f, fieldnames=headers)
                
                if mode == "w":
                    await writer.writeheader()
                    
                for post in posts:
                    row = {h: getattr(post, h) for h in headers}
                    await writer.writerow(row)
                    
            self.logger.info(f"✓ Saved {len(posts)} {description.lower()} to {os.path.basename(file_path)}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving {description.lower()} to {file_path}: {e}")
            return False

    async def save_error_log(self, subreddit: str, errors: List[str]) -> None:
        """Save error messages to log file"""
        if not errors:
            return
            
        try:
            error_log_file = self.get_file_path(f"{subreddit}_errors.log")
            async with aiofiles.open(error_log_file, 'w', encoding='utf-8') as f:
                await f.write('\n'.join(errors))
                
            self.logger.info(f"Error details saved to {subreddit}_errors.log")
            
        except Exception as e:
                        self.logger.error(f"Failed to save error log for {subreddit}: {e}")

    async def clean_all_csvs(self) -> bool:
        """Clean all subreddit CSV files"""
        from .cleaner import CSVCleaner  # Lazy import to avoid circular dependencies
        
        if self.cleaner is None:
            self.cleaner = CSVCleaner()

        # Get list of subreddits
        subreddits = await self.read_subreddit_list(self.get_file_path("sub_list.csv"))
        if not subreddits:
            self.logger.error("No subreddits found to scan")
            return False

        # Process each subreddit's CSV
        for subreddit in subreddits:
            self.cleaner.stats.total_subreddits += 1
            csv_path = self.get_file_path(f"{subreddit}_img_list.csv")
            
            if not os.path.exists(csv_path):
                self.logger.warning(f"Skipping r/{subreddit}: No CSV file found")
                continue
                
            await self.cleaner.clean_subreddit_csv(csv_path, subreddit)

        # Print final statistics
        self.cleaner.stats.print_summary()
        return True

    async def clean_subreddit_csv(self, subreddit: str) -> bool:
        """Clean a specific subreddit's CSV file"""
        from .cleaner import CSVCleaner  # Lazy import to avoid circular dependencies
        
        if self.cleaner is None:
            self.cleaner = CSVCleaner()

        csv_path = self.get_file_path(f"{subreddit}_img_list.csv")
        if not os.path.exists(csv_path):
            self.logger.error(f"CSV file not found for r/{subreddit}")
            return False

        self.cleaner.stats.total_subreddits += 1
        result = await self.cleaner.clean_subreddit_csv(csv_path, subreddit)
        
        # Print statistics for single subreddit clean
        self.cleaner.stats.print_summary()
        return result