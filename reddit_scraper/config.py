"""Configuration management for Reddit Image Scraper"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import logging

@dataclass
class HashConfig:
    """Configuration for image hash comparison settings"""
    enable_hash_comparison: bool = True
    hash_file: str = "image_hashes.json"
    hash_threshold: int = 5
    hash_type: str = "average"

@dataclass
class ScrapingConfig:
    """Configuration for scraping settings"""
    post_limit: int = 20
    search_type: str = "top"
    supported_formats: List[str] = field(default_factory=lambda: ["jpg", "png", "jpeg"])
    excluded_domains: List[str] = field(default_factory=lambda: ["i.imgur.com"])
    enable_duplicate_detection: bool = True
    enable_deleted_image_check: bool = True
    batch_size: int = 10
    min_image_size: int = 10240
    hash_config: HashConfig = field(default_factory=HashConfig)

@dataclass
class PerformanceConfig:
    """Configuration for performance settings"""
    request_timeout_seconds: int = 30
    retry_attempts: int = 3
    rate_limit_delay: float = 1.0
    max_workers: int = 4
    max_memory_mb: int = 500
    reddit_api_retries: int = 3
    reddit_api_retry_delay: int = 5

@dataclass
class OutputConfig:
    """Configuration for output settings"""
    csv_encoding: str = "utf-8-sig"
    summary_filename: str = "new_img.csv"
    log_level: str = "INFO"
    save_error_logs: bool = True

class ConfigManager:
    """Manages configuration loading and validation"""
    
    def __init__(self, config_path: str):
        self.dir_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        if os.path.basename(config_path) == config_path:
            self.config_path = os.path.join(self.dir_path, config_path)
        else:
            self.config_path = config_path
        self.reddit_credentials: Dict[str, str] = {}
        self.scraping_config = ScrapingConfig()
        self.performance_config = PerformanceConfig()
        self.output_config = OutputConfig()
        self.logger = logging.getLogger(__name__)

    async def load_config(self) -> bool:
        """Load configuration from file"""
        try:
            if not os.path.exists(self.config_path):
                await self._create_default_config()
                return True

            with open(self.config_path, 'r') as config_file:
                config_data = json.load(config_file)

            # Load credentials
            self.reddit_credentials = config_data.get("reddit_credentials", {})
            
            # Load scraping config
            scraping_dict = config_data.get("scraping_settings", {})
            
            # FIXED: Handle hash_config properly
            hash_config_dict = scraping_dict.pop("hash_config", {})
            hash_config = HashConfig(**hash_config_dict) if hash_config_dict else HashConfig()
            
            # Create scraping config with hash_config
            self.scraping_config = ScrapingConfig(
                **scraping_dict,
                hash_config=hash_config
            )
            
            # Load other configs
            performance_dict = config_data.get("performance_settings", {})
            output_dict = config_data.get("output_settings", {})
            
            self.performance_config = PerformanceConfig(**performance_dict)
            self.output_config = OutputConfig(**output_dict)
            
            self.logger.info("[SUCCESS] Loaded configuration from reddit_config.json")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return False

    async def _create_default_config(self) -> None:
        """Create default configuration file"""
        self.logger.info("Creating new config file...")
        
        # Get credentials interactively
        self.reddit_credentials = await self._get_credentials()
        
        # Convert dataclasses to dict, handling nested dataclass
        scraping_dict = asdict(self.scraping_config)
        
        config_data = {
            "reddit_credentials": self.reddit_credentials,
            "scraping_settings": scraping_dict,
            "performance_settings": asdict(self.performance_config),
            "output_settings": asdict(self.output_config)
        }
        
        with open(self.config_path, 'w') as config_file:
            json.dump(config_data, config_file, indent=4)
            
        self.logger.info(f"✓ Configuration created: {self.config_path}")

    async def _get_credentials(self) -> Dict[str, str]:
        """Get Reddit API credentials interactively"""
        print("Setting up Reddit API credentials...")
        print("(You can find these at: https://www.reddit.com/prefs/apps)")
        
        creds = {
            "client_id": input("Enter your Reddit client_id: "),
            "client_secret": input("Enter your Reddit client_secret: "),
            "user_agent": input("Enter your user_agent (e.g., MyBot/1.0): "),
            "username": input("Enter your Reddit username: "),
            "password": input("Enter your Reddit password: ")
        }
        
        return creds

    def validate_config(self) -> bool:
        """Validate the loaded configuration with detailed feedback"""
        required_creds = {
            "client_id": "Client ID from your Reddit App",
            "client_secret": "Client Secret from your Reddit App",
            "user_agent": "User Agent string (e.g., 'MyBot/1.0')",
            "username": "Reddit username",
            "password": "Reddit password"
        }
        
        # Check if credentials exist
        missing_creds = []
        empty_creds = []
        
        for key, description in required_creds.items():
            if key not in self.reddit_credentials:
                missing_creds.append(f"Missing {description} ({key})")
            elif not self.reddit_credentials[key]:
                empty_creds.append(f"Empty {description} ({key})")
        
        if missing_creds or empty_creds:
            if missing_creds:
                self.logger.error("\nMissing credentials:")
                for error in missing_creds:
                    self.logger.error(f"  ✗ {error}")
            
            if empty_creds:
                self.logger.error("\nEmpty credentials:")
                for error in empty_creds:
                    self.logger.error(f"  ✗ {error}")
                    
            self.logger.error("\nPlease update your reddit_config.json with the correct credentials")
            self.logger.error("You can find these at: https://www.reddit.com/prefs/apps")
            return False
            
        # Validate credential format
        format_errors = []
        
        if len(self.reddit_credentials["client_id"]) < 20:
            format_errors.append("Client ID seems too short (should be ~22 characters)")
            
        if len(self.reddit_credentials["client_secret"]) < 25:
            format_errors.append("Client Secret seems too short (should be ~30 characters)")
            
        if not any(char.isdigit() for char in self.reddit_credentials["user_agent"]):
            format_errors.append("User Agent should include a version number (e.g., 'MyBot/1.0')")
            
        if format_errors:
            self.logger.error("\nPossible credential format issues:")
            for error in format_errors:
                self.logger.error(f"  ! {error}")
        
        # Validate scraping settings
        setting_errors = []
        
        if self.scraping_config.post_limit <= 0:
            setting_errors.append("Post limit must be greater than 0")
            
        if not self.scraping_config.supported_formats:
            setting_errors.append("No supported image formats specified")
            
        if setting_errors:
            self.logger.error("\nConfiguration errors:")
            for error in setting_errors:
                self.logger.error(f"  ✗ {error}")
            return False
        
        if format_errors:
            self.logger.warning("\nCredentials accepted but may have format issues")
            self.logger.warning("If you experience authentication problems, please verify your credentials")
            
        return True