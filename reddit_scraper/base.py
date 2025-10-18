"""Base exceptions and utilities for Reddit Image Scraper"""

from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

@dataclass
class ProcessingStatistics:
    """Comprehensive statistics tracking for image processing"""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_subreddits: int = 0
    total_posts_checked: int = 0
    total_new_images: int = 0
    errors: int = 0
    
    # Detailed statistics
    skipped_stats: Dict[str, int] = field(default_factory=lambda: {
        'wrong_format': 0,
        'duplicate': 0,
        'excluded_domain': 0,
        'deleted': 0,
        'similar': 0
    })
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    processing_times: Dict[str, float] = field(default_factory=dict)
    memory_usage: Dict[str, float] = field(default_factory=dict)
    
    def record_error(self, error_type: str) -> None:
        """Record an error occurrence by type"""
        self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1
        self.errors += 1
    
    def record_processing_time(self, operation: str, duration: float) -> None:
        """Record processing time for an operation"""
        self.processing_times[operation] = self.processing_times.get(operation, 0) + duration
    
    def record_memory_usage(self, component: str, usage_mb: float) -> None:
        """Record memory usage for a component"""
        self.memory_usage[component] = usage_mb
    
    def finalize(self) -> None:
        """Record end time and finalize statistics"""
        self.end_time = datetime.now()

class RedditScraperException(Exception):
    """Base exception for Reddit Image Scraper"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}