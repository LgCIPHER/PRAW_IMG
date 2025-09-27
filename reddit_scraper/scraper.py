"""Main Reddit Image Scraper implementation"""

import asyncio
from typing import List, Set, Dict, Optional, Tuple
import logging
from dataclasses import dataclass, field
import os
from tqdm import tqdm
import asyncpraw
from .auth import CredentialTester

from .config import ConfigManager
from .data_manager import DataManager, RedditPost
from .image_processor import ImageProcessor, ImageValidationResult
from .session_manager import SessionManager
from .retry_handler import with_retry
from .progress_manager import ProgressManager, ResumableOperation

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
        'similar': 0
    })

class RedditImageScraper:
    """Main class for Reddit image scraping operations"""
    
    def __init__(self, config_path: str):
        # Get the parent directory (PRAW_IMG folder)
        self.dir_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        self.config_manager = ConfigManager(config_path)
        self.data_manager = DataManager()
        self.session_manager = SessionManager()
        self.progress_manager = ProgressManager()
        self.image_processor = None
        self.reddit = None
        self.logger = logging.getLogger(__name__)
        self.stats = ScrapingStats()

    async def test_reddit_credentials(self) -> bool:
        """Test Reddit credentials by attempting to authenticate"""
        try:
            self.reddit = asyncpraw.Reddit(
                **self.config_manager.reddit_credentials
            )
            
            user = await self.reddit.user.me()
            if user is None:
                self.logger.error("Authentication failed: Could not get user information")
                return False
                
            # Test basic API access
            subreddit = await self.reddit.subreddit("announcements")
            async for _ in subreddit.hot(limit=1):
                break
                
            self.logger.info(f"[SUCCESS] Successfully authenticated as: {user.name}")
            self.logger.info("[SUCCESS] API access verified")
            return True
            
        except Exception as e:
            error_message = str(e).lower()
            
            if "client_id" in error_message or "client_secret" in error_message:
                self.logger.error("Client Authentication Error:")
                self.logger.error("The client_id or client_secret is incorrect")
            elif "permission" in error_message or "unauthorized" in error_message:
                self.logger.error("Permission Error:")
                self.logger.error("The username or password is incorrect")
            elif "ratelimit" in error_message:
                self.logger.error("Rate Limit Error:")
                self.logger.error("Too many requests. Please wait a few minutes and try again")
            elif "timeout" in error_message:
                self.logger.error("Connection Timeout:")
                self.logger.error("Could not connect to Reddit. Please check your internet connection")
            else:
                self.logger.error(f"Authentication Error: {str(e)}")
                self.logger.error("Please verify all credentials in reddit_config.json")
                
            # Log the actual error for debugging
            self.logger.debug(f"Original error: {str(e)}")
            return False

    async def initialize(self) -> bool:
        """Initialize the scraper"""
        try:
            # Load and validate configuration
            if not await self.config_manager.load_config():
                return False
                
            if not self.config_manager.validate_config():
                return False

            # Test credentials before initializing PRAW
            self.logger.info("Validating Reddit credentials...")
            credential_tester = CredentialTester()
            if not await credential_tester.validate_credentials(self.config_manager.reddit_credentials):
                return False

            # If credentials are valid, initialize PRAW client
            self.reddit = asyncpraw.Reddit(**self.config_manager.reddit_credentials)
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            return False

    @with_retry(max_attempts=3, base_delay=1.0)
    async def process_subreddit(self, subreddit_name: str) -> Tuple[List[RedditPost], Set[str]]:
        """Process a single subreddit"""
        self.logger.info(f"Starting processing of r/{subreddit_name}")
        
        # Set up file paths
        lst_img_name = f"{subreddit_name}_img_list.csv"
        lst_img_dir = self.data_manager.get_file_path(lst_img_name)
        
        if not os.path.exists(lst_img_dir):
            if not await self._should_create_subreddit_file(subreddit_name, lst_img_dir):
                return [], set()

        # Load existing URLs
        existing_urls = await self.data_manager.read_existing_urls(lst_img_dir)
        
        try:
            # Get subreddit submissions
            subreddit = await self.reddit.subreddit(subreddit_name)
            submissions = [s async for s in subreddit.top(
                limit=self.config_manager.scraping_config.post_limit
            )]
            
            # Pre-filter submissions
            candidate_submissions = []
            
            for submission in submissions:
                url = submission.url.lower()
                
                # Quick filtering
                if not ImageProcessor.is_valid_format(
                    url, self.config_manager.scraping_config.supported_formats):
                    self.stats.skipped_stats['wrong_format'] += 1
                    continue
                    
                if url in existing_urls:
                    self.stats.skipped_stats['duplicate'] += 1
                    continue
                    
                if submission.domain in self.config_manager.scraping_config.excluded_domains:
                    self.stats.skipped_stats['excluded_domain'] += 1
                    continue
                    
                candidate_submissions.append(submission)
            
            # Process candidates
            new_posts = []
            post_id = len(existing_urls) + 1
            
            # Only pass hash config if hash comparison is enabled
            hash_config = None
            if self.config_manager.scraping_config.hash_config.enable_hash_comparison:
                hash_config = {
                    "hash_file": self.config_manager.scraping_config.hash_config.hash_file,
                    "hash_threshold": self.config_manager.scraping_config.hash_config.hash_threshold
                }
            
            async with ImageProcessor(
                self.config_manager.scraping_config.min_image_size,
                hash_config=hash_config) as img_processor:
                for submission in tqdm(candidate_submissions,
                                     desc=f"Processing r/{subreddit_name}",
                                     unit="post"):
                    result = await img_processor.validate_image(submission.url)
                    
                    if result.is_valid:
                        post = RedditPost(
                            id=post_id,
                            subreddit_name=subreddit_name,
                            post_title=submission.title,
                            reddit_link=submission.url
                        )
                        new_posts.append(post)
                        existing_urls.add(submission.url.lower())
                        post_id += 1
                        self.stats.total_new_images += 1
                    elif result.is_deleted:
                        self.stats.skipped_stats['deleted'] += 1
                        self.logger.info(f"Skipped deleted image: {submission.url}")
                    elif result.is_similar:
                        self.stats.skipped_stats['similar'] += 1
                        self.logger.info(
                            f"Skipped similar image: {submission.url} "
                            f"(similar to {result.similar_to}, "
                            f"difference: {result.hash_difference})"
                        )
                        
            # Save new posts
            if new_posts:
                await self.data_manager.save_posts(
                    new_posts, lst_img_dir, f"new posts from r/{subreddit_name}", True)
                
            return new_posts, existing_urls
            
        except Exception as e:
            self.logger.error(f"Error processing r/{subreddit_name}: {e}")
            self.stats.errors += 1
            return [], existing_urls

    async def _should_create_subreddit_file(self, subreddit_name: str, 
                                          file_path: str) -> bool:
        """Ask user if they want to create a new CSV file"""
        while True:
            response = input(
                f"\nCSV file not found for r/{subreddit_name}.\n"
                f"Do you want to create {os.path.basename(file_path)} "
                f"and start scraping? (y/n): "
            ).lower().strip()
            
            if response in ['y', 'n']:
                return response == 'y'
            print("Please enter 'y' for yes or 'n' for no.")

    async def run(self):
        """Main execution method"""
        if not await self.initialize():
            return

        # Get list of subreddits
        subreddits = await self.data_manager.read_subreddit_list(
            self.data_manager.get_file_path("sub_list.csv")
        )
        
        if not subreddits:
            self.logger.error("No valid subreddits found")
            return

        # Process all subreddits
        all_new_posts = []
        
        for subreddit in subreddits:
            self.stats.total_subreddits += 1
            new_posts, _ = await self.process_subreddit(subreddit)
            all_new_posts.extend(new_posts)

        # Save summary
        if all_new_posts:
            summary_path = self.data_manager.get_file_path(
                self.config_manager.output_config.summary_filename
            )
            await self.data_manager.save_posts(
                all_new_posts, summary_path, "new images summary"
            )

        # Print final statistics
        self._print_final_stats()

    def _print_final_stats(self):
        """Print final scraping statistics"""
        print("\n" + "="*50)
        print("Scraping Complete!")
        print(f"✓ Processed {self.stats.total_subreddits} subreddits")
        print(f"✓ Found {self.stats.total_new_images} new images")
        print("\nSkipped images:")
        print(f"  - Wrong format: {self.stats.skipped_stats['wrong_format']}")
        print(f"  - Duplicates: {self.stats.skipped_stats['duplicate']}")
        print(f"  - Excluded domains: {self.stats.skipped_stats['excluded_domain']}")
        print(f"  - Deleted: {self.stats.skipped_stats['deleted']}")
        print(f"  - Similar images: {self.stats.skipped_stats['similar']}")
        print(f"Errors encountered: {self.stats.errors}")
        print("="*50)

    async def clean_csvs(self, specific_subreddit: str = None) -> bool:
        """Clean CSV files to remove dead links
        
        Args:
            specific_subreddit: If provided, only clean this subreddit's CSV.
                              If None, clean all subreddit CSVs.
        """
        try:
            if specific_subreddit:
                return await self.data_manager.clean_subreddit_csv(specific_subreddit)
            else:
                return await self.data_manager.clean_all_csvs()
        except Exception as e:
            self.logger.error(f"Error during CSV cleaning: {e}")
            return False