"""Data management for Reddit Image Scraper."""

import os
import csv
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
import logging

DEFAULT_SUBREDDITS_FILE = "sub_list.csv"
DEFAULT_RESULTS_FILE = "new_img.csv"

@dataclass
class RedditPost:
    """Represents a Reddit post with image."""
    subreddit: str
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    size: Optional[int] = None
    metadata: Dict[str, any] = field(default_factory=dict)

class DataManager:
    """Handles all data persistence operations."""
    
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        self.logger = logging.getLogger(__name__)
        
    def get_file_path(self, filename: str) -> str:
        """Get absolute path for a file."""
        return os.path.join(self.base_dir, filename)
        
    def read_subreddit_list(self, file_path: Optional[str] = None) -> List[str]:
        """Read and validate subreddit names from CSV.
        
        Args:
            file_path: Optional path to subreddits file. If not provided,
                      uses default path.
        """
        file_path = file_path or self.get_file_path(DEFAULT_SUBREDDITS_FILE)
        subreddits = []
        
        if not os.path.exists(file_path):
            self.logger.error(f"Subreddit list file not found: {file_path}")
            return subreddits
            
        try:
            with open(file_path, mode='r', encoding='utf-8-sig') as f:
                for line in f:
                    subreddit = line.strip()
                    if subreddit and not subreddit.startswith('#'):
                        subreddits.append(subreddit)
            return subreddits
        except Exception as e:
            self.logger.error(f"Error reading subreddit list: {e}")
            return []

    def save_results(self, posts: List[RedditPost], subreddit: str) -> None:
        """Save processed posts to CSV file."""
        file_path = self.get_file_path(f"{subreddit}_img_list.csv")
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Write to CSV
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=['subreddit', 'url', 'width', 'height', 'size'])
                writer.writeheader()
                for post in posts:
                    writer.writerow({
                        'subreddit': post.subreddit,
                        'url': post.url,
                        'width': post.width or '',
                        'height': post.height or '',
                        'size': post.size or ''
                    })
            
            self.logger.info(f"Saved {len(posts)} results to {file_path}")
        except Exception as e:
            self.logger.error(f"Error saving results to {file_path}: {e}")
            raise

    def read_results(self, subreddit: str) -> List[RedditPost]:
        """Read processed posts from CSV file."""
        file_path = self.get_file_path(f"{subreddit}_img_list.csv")
        posts = []
        
        if not os.path.exists(file_path):
            self.logger.warning(f"No results file found for r/{subreddit}")
            return posts
            
        try:
            with open(file_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    post = RedditPost(
                        subreddit=row['subreddit'],
                        url=row['url'],
                        width=int(row['width']) if row.get('width') else None,
                        height=int(row['height']) if row.get('height') else None,
                        size=int(row['size']) if row.get('size') else None
                    )
                    posts.append(post)
            return posts
        except Exception as e:
            self.logger.error(f"Error reading results from {file_path}: {e}")
            return []
        
    def _validate_subreddit_name(self, name: str) -> bool:
        """Validate subreddit name format."""
        return (len(name) <= 50 and 
                name.replace('_', '').replace('-', '').isalnum())
                
    def read_existing_urls(self, file_path: str) -> Set[str]:
        """Read existing URLs from CSV file."""
        urls = set()
        
        if not os.path.exists(file_path):
            self.logger.info(f"No existing file found: {file_path}")
            return urls
            
        try:
            with open(file_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('url'):
                        urls.add(row['url'].lower())
                        
            self.logger.info(f"✓ Loaded {len(urls)} existing URLs from {os.path.basename(file_path)}")
            return urls
            
        except Exception as e:
            self.logger.error(f"Error reading URLs: {e}")
            return urls

    def save_error_log(self, subreddit: str, errors: List[str]) -> None:
        """Save error messages to log file."""
        if not errors:
            return
            
        try:
            error_log_file = self.get_file_path(f"{subreddit}_errors.log")
            with open(error_log_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(errors))
                
            self.logger.info(f"Error details saved to {subreddit}_errors.log")
            
        except Exception as e:
            self.logger.error(f"Failed to save error log for {subreddit}: {e}")

    async def clean_all_csvs(self) -> bool:
        """Clean all subreddit CSV files"""
        from .cleaner import CSVCleaner  # Lazy import to avoid circular dependencies
        
        # Get list of subreddits
        subreddits = await self.read_subreddit_list(self.get_file_path("sub_list.csv"))
        if not subreddits:
            self.logger.error("No subreddits found to scan")
            return False

        # Create cleaner inside async context
        async with CSVCleaner() as cleaner:
            # Process each subreddit's CSV
            for subreddit in subreddits:
                cleaner.stats.total_subreddits += 1
                csv_path = self.get_file_path(f"{subreddit}_img_list.csv")
                
                if not os.path.exists(csv_path):
                    self.logger.warning(f"Skipping r/{subreddit}: No CSV file found")
                    continue
                    
                await cleaner.clean_subreddit_csv(csv_path, subreddit)

            # Print final statistics
            cleaner.stats.print_summary()

        return True

    async def clean_subreddit_csv(self, subreddit: str) -> bool:
        """Clean a specific subreddit's CSV file"""
        from .cleaner import CSVCleaner  # Lazy import to avoid circular dependencies
        
        csv_path = self.get_file_path(f"{subreddit}_img_list.csv")
        if not os.path.exists(csv_path):
            self.logger.error(f"CSV file not found for r/{subreddit}")
            return False

        # Create cleaner inside async context
        async with CSVCleaner() as cleaner:
            cleaner.stats.total_subreddits += 1
            result = await cleaner.clean_subreddit_csv(csv_path, subreddit)
            
            # Print statistics for single subreddit clean
            cleaner.stats.print_summary()
            
        return result