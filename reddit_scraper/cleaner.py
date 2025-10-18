"""Cleans CSV files by removing dead or invalid image URLs"""

import os
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Set
import aiofiles
import aiocsv
import json
from tqdm import tqdm

from .image_processor import ImageProcessor
from .memory_optimizer import MemoryEfficientCSVCleaner

@dataclass
class CleaningStats:
    """Statistics for cleaning operation"""
    total_subreddits: int = 0
    total_images_checked: int = 0
    total_removed: int = 0
    total_errors: int = 0
    subreddits_with_errors: Set[str] = field(default_factory=set)

    def print_summary(self):
        """Print cleaning statistics summary"""
        print("\n" + "="*50)
        print("CSV Cleaning Complete!")
        print(f"✓ Processed {self.total_subreddits} subreddits")
        print(f"✓ Checked {self.total_images_checked} total images")
        print(f"✓ Removed {self.total_removed} dead links")
        print(f"\nErrors encountered: {self.total_errors}")
        if self.subreddits_with_errors:
            print("\nSubreddits with errors:")
            for sub in sorted(self.subreddits_with_errors):
                print(f"  - r/{sub}")
        print("="*50)

@dataclass
class CleaningResult:
    """Result of cleaning operation for a single file"""
    valid_posts: List[Dict]
    removed_count: int
    error_urls: List[str]
    error_messages: List[str]

class CSVCleaner:
    """Handles cleaning of CSV files containing Reddit image URLs"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.image_processor = None
        
    async def __aenter__(self):
        """Set up async context"""
        self.image_processor = ImageProcessor()
        await self.image_processor.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up async context"""
        if self.image_processor:
            await self.image_processor.__aexit__(exc_type, exc_val, exc_tb)
            self.image_processor = None
        self.stats = CleaningStats()
        self.memory_cleaner = MemoryEfficientCSVCleaner(max_memory_mb=500)

    async def clean_subreddit_csv(self, file_path: str, subreddit_name: str) -> bool:
        """Clean a single subreddit's CSV file with proper async operations"""
        if not os.path.exists(file_path):
            self.logger.warning(f"File not found: {file_path}")
            return False

        try:
            # Load existing data using aiocsv
            posts_data = []
            
            async with aiofiles.open(file_path, mode='r', encoding='utf-8-sig') as f:
                reader = aiocsv.AsyncDictReader(f)
                async for row in reader:
                    posts_data.append(row)

            if not posts_data:
                self.logger.info(f"No data found in {os.path.basename(file_path)}")
                return True

            self.logger.info(f"Scanning {len(posts_data)} URLs in {os.path.basename(file_path)}")
            self.stats.total_images_checked += len(posts_data)

            # Process URLs in batches
            batch_size = 10
            error_log = []
            valid_posts = []
            
            for i in tqdm(range(0, len(posts_data), batch_size),
                            desc=f"Cleaning r/{subreddit_name}",
                            unit="batch"):
                    batch = posts_data[i:i + batch_size]
                    result = await self._process_url_batch(batch, self.image_processor)
                    
                    valid_posts.extend(result.valid_posts)
                    self.stats.total_removed += result.removed_count
                    
                    # Log errors
                    for url, msg in zip(result.error_urls, result.error_messages):
                        error_log.append(f"{url}: {msg}")

            # Renumber entries
            for i, post in enumerate(valid_posts, 1):
                post['id'] = str(i)

            # Save cleaned data using aiocsv
            headers = ['id', 'subreddit_name', 'post_title', 'reddit_link']
            async with aiofiles.open(file_path, mode='w', encoding='utf-8-sig', newline='') as f:
                writer = aiocsv.AsyncDictWriter(f, fieldnames=headers)
                await writer.writeheader()
                
                for post in valid_posts:
                    await writer.writerow(post)

            # Save error log if there were any errors
            if error_log:
                error_log_path = os.path.splitext(file_path)[0] + '_errors.log'
                async with aiofiles.open(error_log_path, mode='w', encoding='utf-8') as f:
                    await f.write('\n'.join(error_log))
                self.stats.subreddits_with_errors.add(subreddit_name)
                self.stats.total_errors += len(error_log)

            removed = len(posts_data) - len(valid_posts)
            self.logger.info(f"✓ {subreddit_name}: Kept {len(valid_posts)}, Removed {removed}")
            if error_log:
                self.logger.info(f"  Error details saved to {os.path.basename(error_log_path)}")

            return True

        except Exception as e:
            self.logger.error(f"Error processing {os.path.basename(file_path)}: {e}")
            self.stats.subreddits_with_errors.add(subreddit_name)
            self.stats.total_errors += 1
            return False

    async def _process_url_batch(self, posts: List[Dict], 
                               img_processor: ImageProcessor) -> CleaningResult:
        """Process a batch of URLs and return results"""
        valid_posts = []
        error_urls = []
        error_messages = []
        removed_count = 0

        for post in posts:
            try:
                url = post['reddit_link']
                # First check if the URL format is valid
                if not ImageProcessor.is_valid_format(url, ['jpg', 'png', 'jpeg']):
                    removed_count += 1
                    error_urls.append(url)
                    error_messages.append("Invalid image format")
                    continue

                # Then check if the image is accessible
                if not img_processor.session or img_processor.session.closed:
                    await img_processor.__aenter__()

                try:
                    async with img_processor.session.get(url) as response:
                        if response.status != 200:
                            removed_count += 1
                            error_urls.append(url)
                            error_messages.append(f"HTTP {response.status}")
                            continue

                        # Image accessible and valid
                        valid_posts.append(post)
                except:
                    removed_count += 1
                    error_urls.append(url)
                    error_messages.append("Download failed")

            except Exception as e:
                removed_count += 1
                error_urls.append(post.get('reddit_link', 'Unknown URL'))
                error_messages.append(str(e))

        return CleaningResult(valid_posts, removed_count, error_urls, error_messages)