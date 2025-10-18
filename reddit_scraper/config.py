"""Configuration validation and management for Reddit Image Scraper"""

from typing import List, Dict, Any, Optional
import json
import os
from dataclasses import dataclass, field, asdict
import logging
import jsonschema
from .base import RedditScraperException

class ConfigValidationError(RedditScraperException):
    """Raised when configuration validation fails"""
    pass

@dataclass
class HashConfig:
    """Configuration for image hash comparison settings"""
    enable_hash_comparison: bool = True
    hash_file: str = "image_hashes.json"
    hash_threshold: int = 5
    hash_type: str = "average"  # can be "average", "perceptual", "difference", or "wavelet"
    hash_size: int = 8  # Added from core config

    @staticmethod
    def schema() -> Dict[str, Any]:
        """JSON schema for hash configuration validation"""
        return {
            "type": "object",
            "properties": {
                "enable_hash_comparison": {"type": "boolean"},
                "hash_file": {"type": "string"},
                "hash_threshold": {"type": "integer", "minimum": 0},
                "hash_type": {"type": "string", "enum": ["average", "perceptual", "difference", "wavelet"]},
                "hash_size": {"type": "integer", "minimum": 4}
            },
            "required": ["enable_hash_comparison", "hash_file", "hash_threshold", "hash_type", "hash_size"]
        }

@dataclass
class ScrapingConfig:
    """Configuration for scraping settings"""
    post_limit: int = 100  # Updated from core config
    sort_type: str = "top"  # Type of sorting (hot, new, top, rising)
    sort_time: str = "all"  # Time filter for top/controversial (hour, day, week, month, year, all)
    supported_formats: List[str] = field(default_factory=lambda: ["jpg", "png", "jpeg"])
    excluded_domains: List[str] = field(default_factory=lambda: [])  # Empty by default like core config
    enable_duplicate_detection: bool = True
    enable_deleted_image_check: bool = True
    batch_size: int = 10
    min_image_size: int = 10240  # 10KB minimum size
    max_memory_percent: float = 75.0  # Added from core config
    max_cpu_percent: float = 80.0  # Added from core config
    hash_config: HashConfig = field(default_factory=HashConfig)

    @staticmethod
    def schema() -> Dict[str, Any]:
        """JSON schema for scraping configuration validation"""
        return {
            "type": "object",
            "properties": {
                "post_limit": {"type": "integer", "minimum": 1},
                "sort_type": {"type": "string", "enum": ["hot", "new", "top", "rising"]},
                "sort_time": {"type": "string", "enum": ["hour", "day", "week", "month", "year", "all"]},
                "supported_formats": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1
                },
                "excluded_domains": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "enable_duplicate_detection": {"type": "boolean"},
                "enable_deleted_image_check": {"type": "boolean"},
                "batch_size": {"type": "integer", "minimum": 1},
                "min_image_size": {"type": "integer", "minimum": 0},
                "max_memory_percent": {"type": "number", "minimum": 0, "maximum": 100},
                "max_cpu_percent": {"type": "number", "minimum": 0, "maximum": 100},
                "hash_config": HashConfig.schema()
            },
            "required": [
                "post_limit", "search_type", "supported_formats", "excluded_domains",
                "enable_duplicate_detection", "enable_deleted_image_check", "batch_size",
                "min_image_size", "max_memory_percent", "max_cpu_percent", "hash_config"
            ]
        }

class ConfigValidator:
    """Configuration validation utility"""
    
    @staticmethod
    def validate_reddit_credentials(config: Dict[str, Any]) -> List[str]:
        """Validate Reddit API credentials
        
        Args:
            config: Dictionary containing Reddit credentials
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        required_fields = {
            'client_id': 'Client ID',
            'client_secret': 'Client Secret',
            'user_agent': 'User Agent',
            'username': 'Username',
            'password': 'Password'
        }
        
        for field, display_name in required_fields.items():
            if not config.get(field):
                errors.append(f"Missing {display_name}")
            elif len(str(config[field]).strip()) == 0:
                errors.append(f"Empty {display_name}")
        
        return errors

    @staticmethod
    def validate_config_schema(config: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
        """Validate configuration against JSON schema
        
        Args:
            config: Configuration dictionary to validate
            schema: JSON schema to validate against
            
        Returns:
            List of validation error messages (empty if valid)
        """
        try:
            jsonschema.validate(instance=config, schema=schema)
            return []
        except jsonschema.exceptions.ValidationError as e:
            return [str(e)]

class ConfigManager:
    """Manages configuration loading, validation, and access"""
    
    def __init__(self, config_path: str):
        # Get the parent directory (PRAW_IMG folder)
        self.dir_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        
        # Ensure config_path is in parent directory if only filename is provided
        if os.path.basename(config_path) == config_path:
            self.config_path = os.path.join(self.dir_path, config_path)
        else:
            self.config_path = config_path
            
        self.logger = logging.getLogger(__name__)
        self.reddit_credentials: Dict[str, str] = {}
        self.scraping_config = ScrapingConfig()
        self.validator = ConfigValidator()

    async def load_and_validate_config(self) -> bool:
        """Load and validate configuration from file
        
        Returns:
            bool: True if configuration is valid, False otherwise
            
        Raises:
            ConfigValidationError: If configuration is invalid
        """
        try:
            # Load configuration file
            if not os.path.exists(self.config_path):
                raise ConfigValidationError(f"Configuration file not found: {self.config_path}")
                
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Validate Reddit credentials
            cred_errors = self.validator.validate_reddit_credentials(
                config.get('reddit_credentials', {})
            )
            if cred_errors:
                raise ConfigValidationError(
                    "Invalid Reddit credentials",
                    {'errors': cred_errors}
                )
            
            # Validate scraping configuration
            scraping_errors = self.validator.validate_config_schema(
                config.get('scraping_settings', {}),
                ScrapingConfig.schema()
            )
            if scraping_errors:
                raise ConfigValidationError(
                    "Invalid scraping configuration",
                    {'errors': scraping_errors}
                )
            
            # Store validated configuration
            self.reddit_credentials = config['reddit_credentials']
            self.scraping_config = ScrapingConfig(**config['scraping_settings'])
            
            self.logger.info("Configuration loaded and validated successfully")
            return True
            
        except json.JSONDecodeError as e:
            raise ConfigValidationError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            raise ConfigValidationError(f"Error loading configuration: {str(e)}")

    def create_default_config(self) -> bool:
        """Create a default configuration file
        
        Returns:
            bool: True if file was created successfully, False otherwise
        """
        try:
            default_config = {
                "reddit_credentials": {
                    "client_id": "",
                    "client_secret": "",
                    "user_agent": "RedditImageScraper/1.0",
                    "username": "",
                    "password": ""
                },
                "scraping_settings": {
                    "post_limit": 100,
                    "search_type": "top",
                    "supported_formats": ["jpg", "png", "jpeg"],
                    "excluded_domains": ["i.imgur.com", "v.redd.it"],
                    "enable_duplicate_detection": True,
                    "enable_deleted_image_check": True,
                    "batch_size": 10,
                    "min_image_size": 10240,
                    "hash_config": {
                        "enable_hash_comparison": True,
                        "hash_file": "image_hashes.json",
                        "hash_threshold": 5,
                        "hash_type": "average"
                    }
                }
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(default_config, f, indent=4)
            
            self.logger.info(f"Created default configuration at {self.config_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating default configuration: {e}")
            return False

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
    """Enhanced configuration manager with validation."""
    
    def __init__(self, config_path: str):
        # Get the parent directory (PRAW_IMG folder)
        self.dir_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        
        # Ensure config_path is in parent directory if only filename is provided
        if os.path.basename(config_path) == config_path:
            self.config_path = os.path.join(self.dir_path, config_path)
        else:
            self.config_path = config_path
            
        self.logger = logging.getLogger(__name__)
        self.reddit_credentials: Dict[str, str] = {}
        self.scraping_config = ScrapingConfig()
        self.performance_config = PerformanceConfig()
        self.output_config = OutputConfig()

    async def load(self) -> bool:
        """Load and validate configuration from file."""
        try:
            if not os.path.exists(self.config_path):
                await self._create_default_config()
                return True

            with open(self.config_path, 'r') as f:
                config = json.load(f)

            # Load credentials from either reddit_credentials or reddit section
            self.reddit_credentials = config.get('reddit_credentials') or config.get('reddit', {})
            
            # Load scraping config from either scraping_settings or scraper section
            scraping_dict = config.get('scraping_settings') or config.get('scraper', {})
            hash_config_dict = scraping_dict.pop('hash_config', {})
            hash_config = HashConfig(**hash_config_dict) if hash_config_dict else HashConfig()
            self.scraping_config = ScrapingConfig(**scraping_dict, hash_config=hash_config)
            
            # Load other configs
            self.performance_config = PerformanceConfig(**config.get('performance_settings', {}))
            self.output_config = OutputConfig(**config.get('output_settings', {}))

            # Validate everything
            if not self.validate_config():
                return False

            self.logger.info("[SUCCESS] Configuration loaded and validated")
            return True

        except json.JSONDecodeError as e:
            raise ConfigValidationError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            raise ConfigValidationError(f"Error loading configuration: {str(e)}")

    async def _create_default_config(self) -> None:
        """Create default configuration file"""
        self.logger.info("Creating new config file...")
        
        # Get credentials interactively
        self.reddit_credentials = await self._get_credentials()
        
        config_data = {
            "reddit_credentials": self.reddit_credentials,
            "scraping_settings": asdict(self.scraping_config),
            "performance_settings": asdict(self.performance_config),
            "output_settings": asdict(self.output_config)
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(config_data, f, indent=4)
            
        self.logger.info(f"✓ Configuration created: {self.config_path}")

    async def _get_credentials(self) -> Dict[str, str]:
        """Get Reddit API credentials interactively"""
        print("Setting up Reddit API credentials...")
        print("(You can find these at: https://www.reddit.com/prefs/apps)")
        
        return {
            "client_id": input("Enter your Reddit client_id: "),
            "client_secret": input("Enter your Reddit client_secret: "),
            "user_agent": input("Enter your user_agent (e.g., MyBot/1.0): "),
            "username": input("Enter your Reddit username: "),
            "password": input("Enter your Reddit password: ")
        }

    def validate_config(self) -> bool:
        """Validate the loaded configuration with detailed feedback"""
        required_creds = {
            "client_id": "Client ID from your Reddit App",
            "client_secret": "Client Secret from your Reddit App",
            "user_agent": "User Agent string (e.g., 'MyBot/1.0')",
            "username": "Reddit username",
            "password": "Reddit password"
        }
        
        # Check credentials
        missing_creds = []
        empty_creds = []
        format_errors = []
        
        for key, description in required_creds.items():
            if key not in self.reddit_credentials:
                missing_creds.append(f"Missing {description} ({key})")
            elif not self.reddit_credentials[key]:
                empty_creds.append(f"Empty {description} ({key})")
        
        # Validate credential formats
        if self.reddit_credentials:
            if len(self.reddit_credentials.get("client_id", "")) < 20:
                format_errors.append("Client ID seems too short (should be ~22 characters)")
                
            if len(self.reddit_credentials.get("client_secret", "")) < 25:
                format_errors.append("Client Secret seems too short (should be ~30 characters)")
                
            if not any(char.isdigit() for char in self.reddit_credentials.get("user_agent", "")):
                format_errors.append("User Agent should include a version number (e.g., 'MyBot/1.0')")
        
        # Log credential issues
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
        
        if format_errors:
            self.logger.warning("\nPossible credential format issues:")
            for error in format_errors:
                self.logger.warning(f"  ! {error}")
            self.logger.warning("If you experience authentication problems, please verify your credentials")
        
        # Validate settings
        setting_errors = []
        
        # Scraping settings
        if self.scraping_config.post_limit <= 0:
            setting_errors.append("Post limit must be greater than 0")
        if not self.scraping_config.supported_formats:
            setting_errors.append("No supported image formats specified")
        if self.scraping_config.max_memory_percent > 90:
            setting_errors.append("max_memory_percent should not exceed 90%")
        if self.scraping_config.max_cpu_percent > 90:
            setting_errors.append("max_cpu_percent should not exceed 90%")
            
        # Performance settings
        if self.performance_config.max_workers < 1:
            setting_errors.append("max_workers must be at least 1")
        if self.performance_config.request_timeout_seconds < 5:
            setting_errors.append("request_timeout_seconds should be at least 5 seconds")
            
        if setting_errors:
            self.logger.error("\nConfiguration validation errors:")
            for error in setting_errors:
                self.logger.error(f"  ✗ {error}")
            return False
        
        return True

    async def save(self) -> None:
        """Save current configuration to file."""
        try:
            config_data = {
                "reddit_credentials": self.reddit_credentials,
                "scraping_settings": asdict(self.scraping_config),
                "performance_settings": asdict(self.performance_config),
                "output_settings": asdict(self.output_config)
            }

            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=4)
        except Exception as e:
            raise ConfigValidationError(f"Error saving config: {str(e)}")

    @property
    def settings(self) -> Dict[str, Any]:
        """Get the current configuration settings."""
        return {
            "scraping": self.scraping_config,
            "performance": self.performance_config,
            "output": self.output_config,
        }

    def get_reddit_credentials(self) -> Dict[str, str]:
        """Get Reddit API credentials."""
        if not self.reddit_credentials:
            raise ConfigValidationError("Reddit credentials not loaded")
        return self.reddit_credentials

    def get_post_limit(self) -> int:
        """Get the configured post limit."""
        return self.scraping_config.post_limit