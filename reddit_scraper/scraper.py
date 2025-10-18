"""Main Reddit Image Scraper implementation with dependency injection and state management."""

import asyncio
from typing import List, Set, Dict, Optional, Tuple
import logging
from dataclasses import dataclass, field
import os
from datetime import datetime
import asyncpraw

from .core.base import ScraperState, EventManager, ProgressStats, ScraperEvent
from .core.rate_limiter import RateLimiter
from .config import ConfigManager
from .image_processor import ImageProcessor
from .data_manager import DataManager, RedditPost
from .session_manager import SessionManager
from .retry import with_retry, RetryConfig

@dataclass
class ScrapingStats:
    """Statistics for scraping operation"""
    total_subreddits: int = 0
    total_posts_checked: int = 0
    total_new_images: int = 0
    errors: int = 0
    skipped_stats: Dict[str, int] = field(default_factory=lambda: {
        'wrong_format': 0,
        'duplicate': 0,
        'excluded_domain': 0,
        'deleted': 0,
        'validation_failed': 0,
        'similar': 0
    })
    start_time: datetime = field(default_factory=datetime.now)

class RedditImageScraper:
    """Main scraper class with dependency injection and state management"""
    def __init__(
        self,
        config_path: str,
        config_manager: Optional[ConfigManager] = None,
        image_processor: Optional[ImageProcessor] = None,
        data_manager: Optional[DataManager] = None,
        event_manager: Optional[EventManager] = None
    ):
        self.config_path = config_path
        self.config_manager = config_manager or ConfigManager(config_path)
        # Initialize image processor with configuration
        self.image_processor = image_processor or ImageProcessor(self.config_manager)
        self.data_manager = data_manager or DataManager()
        self.event_manager = event_manager or EventManager()
        self.rate_limiter = RateLimiter()
        self.state = ScraperState.INITIALIZING
        self.session_manager = SessionManager()
        self.reddit = None
        self.logger = logging.getLogger(__name__)
        self.stats = ScrapingStats()
        self._progress: Optional[ProgressStats] = None

    def set_event_manager(self, event_manager: EventManager) -> None:
        """Set the event manager for progress updates."""
        self.event_manager = event_manager

    async def _update_progress(self) -> None:
        """Update and publish progress."""
        if self._progress and self.event_manager:
            await self.event_manager.publish(
                ScraperEvent("progress_update", {"stats": self._progress})
            )

    @with_retry(RetryConfig(max_retries=3, base_delay=1.0))
    async def _process_post(self, post: asyncpraw.models.Submission) -> Optional[RedditPost]:
        """Process a single Reddit post."""
        await self.rate_limiter.acquire()
        
        try:
            # Check if URL has a valid image format
            if not hasattr(self.config_manager.scraping_config, 'supported_formats'):
                self.config_manager.scraping_config.supported_formats = ['jpg', 'jpeg', 'png', 'gif']
            # Get supported formats from config or use defaults
            supported_formats = getattr(self.config_manager.scraping_config, 'supported_formats', ['jpg', 'jpeg', 'png', 'gif'])

            # Check if it's a valid image format
            if not self.image_processor.is_valid_format(post.url, supported_formats):
                self.stats.skipped_stats['wrong_format'] += 1
                return None
                
            if hasattr(post, 'is_video') and post.is_video:
                self.stats.skipped_stats['wrong_format'] += 1
                return None
                
            # Check domain exclusions
            if post.domain in self.config_manager.scraping_config.excluded_domains:
                self.stats.skipped_stats['excluded_domain'] += 1
                return None
            
            # Validate image using the processor
            try:
                result = await self.image_processor.validate_image(post.url)
                
                if result.is_valid:
                    return RedditPost(
                        subreddit=post.subreddit.display_name,
                        url=post.url,
                        width=result.width,
                        height=result.height,
                        size=result.size
                    )
                else:
                    reason = result.skip_reason or 'validation_failed'
                    self.stats.skipped_stats[reason] += 1
                    self.logger.debug(f"Image validation failed for {post.url}: {result.message} (reason: {reason})")
            except AttributeError as e:
                self.logger.error(f"Session error while validating image {post.url}: {str(e)}")
                self.stats.errors += 1
                raise
                
        except Exception as e:
            self.logger.error(f"Error processing post {post.url}: {str(e)}")
            self.stats.errors += 1
            self.rate_limiter.report_error()
        
        return None

    async def initialize(self) -> None:
        """Initialize the scraper and its dependencies."""
        try:
            self.state = ScraperState.LOADING_CONFIG
            await self.config_manager.load()
            
            self.state = ScraperState.CONNECTING
            self.reddit = await self.session_manager.create_reddit_session(self.config_manager)
            
            # Initialize image processor session
            await self.image_processor.__aenter__()
            
            # Initialize progress tracking
            subreddits = self.data_manager.read_subreddit_list()
            self._progress = ProgressStats(
                total_subreddits=len(subreddits),
                processed_subreddits=0,
                total_posts=0,
                processed_posts=0,
                current_batch=0,
                total_batches=0,
                batch_size=0,
                start_time=datetime.now()
            )
        except Exception as e:
            self.state = ScraperState.ERROR
            self.logger.error(f"Initialization failed: {e}")
            raise

    async def run(self) -> None:
        """Run the image scraping process."""
        try:
            await self.initialize()
            self.state = ScraperState.SCRAPING
            
            # Ensure image processor session is active
            if not self.image_processor or not self.image_processor.session:
                self.logger.info("Reinitializing image processor session")
                await self.image_processor.__aenter__()
            
            subreddits = self.data_manager.read_subreddit_list()
            self.stats.total_subreddits = len(subreddits)
            
            for subreddit_name in subreddits:
                self._progress.current_subreddit = subreddit_name
                await self._update_progress()
                
                try:
                    await self._process_subreddit(subreddit_name)
                except Exception as e:
                    self.logger.error(f"Error processing subreddit {subreddit_name}: {str(e)}")
                    self.stats.errors += 1
                    
                    # If we encounter a session error, try to reinitialize the session
                    if "session" in str(e).lower():
                        self.logger.info("Attempting to reinitialize session after error")
                        await self.image_processor.__aenter__()
            
            self.state = ScraperState.COMPLETED
            await self._print_final_stats()
            
        except Exception as e:
            self.state = ScraperState.ERROR
            self.logger.error(f"Scraping process failed: {str(e)}")
            raise
        finally:
            await self.cleanup()

    async def run_specific(self, subreddit_name: str) -> None:
        """Run the scraping process for a specific subreddit."""
        try:
            await self.initialize()
            self.state = ScraperState.SCRAPING
            
            self.stats.total_subreddits = 1
            self._progress.current_subreddit = subreddit_name
            await self._update_progress()
            
            try:
                await self._process_subreddit(subreddit_name)
            except Exception as e:
                self.logger.error(f"Error processing subreddit {subreddit_name}: {str(e)}")
                self.stats.errors += 1
            
            self.state = ScraperState.COMPLETED
            await self._print_final_stats()
            
        except Exception as e:
            self.state = ScraperState.ERROR
            self.logger.error(f"Scraping process failed: {str(e)}")
            raise
        finally:
            await self.cleanup()

    async def _process_subreddit(self, subreddit_name: str) -> None:
        """Process a single subreddit."""
        subreddit = await self.reddit.subreddit(subreddit_name)
        posts = []
        
        # Get sort type from config
        sort_type = getattr(self.config_manager.scraping_config, 'sort_type', 'hot')
        sort_time = getattr(self.config_manager.scraping_config, 'sort_time', 'all')
        limit = self.config_manager.get_post_limit()
        batch_size = getattr(self.config_manager.scraping_config, 'batch_size', 10)
        
        # Get posts based on sort type
        if sort_type == 'top':
            async for post in subreddit.top(time_filter=sort_time, limit=limit):
                posts.append(post)
        elif sort_type == 'hot':
            async for post in subreddit.hot(limit=limit):
                posts.append(post)
        elif sort_type == 'new':
            async for post in subreddit.new(limit=limit):
                posts.append(post)
        elif sort_type == 'rising':
            async for post in subreddit.rising(limit=limit):
                posts.append(post)
        
        # Calculate total posts and batches
        self._progress.total_posts = len(posts)
        self._progress.batch_size = batch_size
        self._progress.total_batches = (len(posts) + batch_size - 1) // batch_size
        self._progress.current_batch = 0
        
        # Process posts in batches
        new_posts: List[RedditPost] = []
        for i in range(0, len(posts), batch_size):
            self._progress.current_batch += 1
            batch = posts[i:i + batch_size]
            
            # Process batch concurrently
            tasks = [self._process_post(post) for post in batch]
            batch_results = await asyncio.gather(*tasks)
            
            # Filter out None results
            valid_results = [result for result in batch_results if result]
            new_posts.extend(valid_results)
            
            # Update progress
            self.stats.total_posts_checked += len(batch)
            self._progress.processed_posts += len(batch)
            await self._update_progress()
        
        # Save results for this subreddit
        if new_posts:
            self.data_manager.save_results(new_posts, subreddit_name)
            self.stats.total_new_images += len(new_posts)
        
        self._progress.processed_subreddits += 1
        await self._update_progress()

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.reddit:
            await self.reddit.close()
        if self.image_processor and self.image_processor.session:
            await self.image_processor.session.close()

    async def _print_final_stats(self) -> None:
        """Print final scraping statistics"""
        print("\n" + "="*50)
        if self.state == ScraperState.COMPLETED:
            print("Operation Completed Successfully!")
        else:
            print("Operation Completed with Errors")
            
        print(f"✓ Processed {self.stats.total_subreddits} subreddits")
        print(f"✓ Checked {self.stats.total_posts_checked} posts")
        print(f"✓ Found {self.stats.total_new_images} new images")
        
        print("\nSkipped images:")
        for reason, count in self.stats.skipped_stats.items():
            if count > 0:
                print(f"  - {reason.replace('_', ' ').title()}: {count}")
        
        if self.stats.errors > 0:
            print(f"\nErrors encountered: {self.stats.errors}")
            print("Check the log file for details")
            
        print("="*50)

    async def clean_csvs(self, specific_subreddit: Optional[str] = None) -> None:
        """Clean CSV files by validating all URLs."""
        self.state = ScraperState.CLEANING
        
        try:
            # Initialize image processor with async context
            async with ImageProcessor(self.config_manager) as img_processor:
                subreddits = [specific_subreddit] if specific_subreddit else self.data_manager.read_subreddit_list()
                
                for subreddit in subreddits:
                    self.logger.info(f"Cleaning CSV for {subreddit}")
                    posts = self.data_manager.read_results(subreddit)
                    
                    valid_posts: List[RedditPost] = []
                    for post in posts:
                        result = await img_processor.validate_image(post.url)
                        if result.is_valid:
                            valid_posts.append(post)
                        else:
                            self.stats.skipped_stats[result.skip_reason] += 1
                    
                    self.data_manager.save_results(valid_posts, subreddit)
            
            self.state = ScraperState.COMPLETED
            await self._print_final_stats()
            
        except Exception as e:
            self.state = ScraperState.ERROR
            self.logger.error(f"Cleaning process failed: {str(e)}")
            raise