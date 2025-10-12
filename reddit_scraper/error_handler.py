"""Enhanced error handling and logging for Reddit Image Scraper"""

import logging
import sys
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import json
from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorContext:
    """Structured error context for better debugging"""
    
    def __init__(
        self,
        operation: str,
        subreddit: Optional[str] = None,
        url: Optional[str] = None,
        post_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.operation = operation
        self.subreddit = subreddit
        self.url = url
        self.post_id = post_id
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            "timestamp": self.timestamp,
            "operation": self.operation,
            "subreddit": self.subreddit,
            "url": self.url,
            "post_id": self.post_id,
            "metadata": self.metadata
        }
    
    def __str__(self) -> str:
        """Human-readable string representation"""
        parts = [f"Operation: {self.operation}"]
        if self.subreddit:
            parts.append(f"Subreddit: r/{self.subreddit}")
        if self.url:
            parts.append(f"URL: {self.url}")
        if self.post_id:
            parts.append(f"Post ID: {self.post_id}")
        if self.metadata:
            parts.append(f"Metadata: {self.metadata}")
        return " | ".join(parts)


class EnhancedLogger:
    """Enhanced logger with structured error context"""
    
    def __init__(self, name: str, log_dir: str = "logs"):
        self.logger = logging.getLogger(name)
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Set up handlers if not already configured
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Set up file and console handlers with proper formatting"""
        self.logger.setLevel(logging.DEBUG)
        
        # Console handler - INFO and above
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        
        # File handler - DEBUG and above
        log_file = self.log_dir / f"scraper_{datetime.now():%Y%m%d}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        
        # Error file handler - ERROR and above only
        error_file = self.log_dir / f"errors_{datetime.now():%Y%m%d}.log"
        error_handler = logging.FileHandler(error_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n'
            'Exception: %(exc_info)s\n',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        error_handler.setFormatter(error_format)
        
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(error_handler)
    
    def log_with_context(
        self,
        level: ErrorSeverity,
        message: str,
        context: Optional[ErrorContext] = None,
        exc_info: bool = False
    ):
        """Log message with structured context
        
        Args:
            level: Error severity level
            message: Log message
            context: Optional error context
            exc_info: Include exception info
        """
        log_message = message
        if context:
            log_message = f"{message}\nContext: {context}"
        
        log_func = getattr(self.logger, level.value.lower())
        log_func(log_message, exc_info=exc_info)
    
    def log_error(
        self,
        message: str,
        context: Optional[ErrorContext] = None,
        exc_info: bool = True
    ):
        """Convenience method for error logging"""
        self.log_with_context(ErrorSeverity.ERROR, message, context, exc_info)
    
    def log_warning(self, message: str, context: Optional[ErrorContext] = None):
        """Convenience method for warning logging"""
        self.log_with_context(ErrorSeverity.WARNING, message, context)
    
    def log_info(self, message: str, context: Optional[ErrorContext] = None):
        """Convenience method for info logging"""
        self.log_with_context(ErrorSeverity.INFO, message, context)


class ErrorTracker:
    """Track and aggregate errors for reporting"""
    
    def __init__(self):
        self.errors: Dict[str, list] = {
            "network": [],
            "validation": [],
            "authentication": [],
            "file_io": [],
            "other": []
        }
    
    def add_error(
        self,
        error_type: str,
        message: str,
        context: Optional[ErrorContext] = None
    ):
        """Add an error to the tracker"""
        error_entry = {
            "message": message,
            "context": context.to_dict() if context else None,
            "timestamp": datetime.now().isoformat()
        }
        
        category = error_type if error_type in self.errors else "other"
        self.errors[category].append(error_entry)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get error summary"""
        return {
            category: len(errors)
            for category, errors in self.errors.items()
        }
    
    def export_to_file(self, filepath: str):
        """Export errors to JSON file for analysis"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.errors, f, indent=2)


# Usage example in scraper
class EnhancedRedditScraper:
    """Scraper with enhanced error handling"""
    
    def __init__(self):
        self.logger = EnhancedLogger(__name__)
        self.error_tracker = ErrorTracker()
    
    async def process_post(self, post, subreddit: str):
        """Process a single post with detailed error context"""
        context = ErrorContext(
            operation="process_post",
            subreddit=subreddit,
            url=post.url,
            post_id=post.id,
            metadata={"title": post.title}
        )
        
        try:
            # Process the post
            result = await self._validate_post(post)
            return result
        
        except ConnectionError as e:
            self.logger.log_error(
                f"Network error processing post: {str(e)}",
                context=context
            )
            self.error_tracker.add_error("network", str(e), context)
            raise
        
        except ValueError as e:
            self.logger.log_warning(
                f"Validation error: {str(e)}",
                context=context
            )
            self.error_tracker.add_error("validation", str(e), context)
            return None
        
        except Exception as e:
            self.logger.log_error(
                f"Unexpected error processing post: {str(e)}",
                context=context,
                exc_info=True
            )
            self.error_tracker.add_error("other", str(e), context)
            raise
    
    async def _validate_post(self, post):
        """Validate post (example)"""
        # Your validation logic here
        pass
    
    def print_error_summary(self):
        """Print summary of errors encountered"""
        summary = self.error_tracker.get_summary()
        print("\n" + "="*50)
        print("Error Summary:")
        for category, count in summary.items():
            if count > 0:
                print(f"  {category.capitalize()}: {count} errors")
        print("="*50)
        
        # Export detailed errors
        self.error_tracker.export_to_file("error_details.json")
        print("Detailed error log saved to error_details.json")