"""Rate limiting functionality for Reddit API calls."""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
import logging

class RateLimiter:
    """Handles rate limiting for API calls with adaptive backoff."""
    
    def __init__(self, calls_per_minute: int = 60, initial_delay: float = 1.0):
        self.calls_per_minute = calls_per_minute
        self.calls: List[datetime] = []
        self.delay = initial_delay
        self.min_delay = 0.5
        self.max_delay = 5.0
        self.backoff_factor = 1.5
        self.success_reduction = 0.9
        self.last_error: Optional[datetime] = None
        self.logger = logging.getLogger(__name__)

    async def acquire(self) -> None:
        """Wait if necessary to respect rate limits."""
        now = datetime.now()
        
        # Remove old calls
        self.calls = [t for t in self.calls if now - t < timedelta(minutes=1)]
        
        if len(self.calls) >= self.calls_per_minute:
            wait_time = 60 - (now - self.calls[0]).total_seconds()
            self.logger.debug(f"Rate limit reached. Waiting {wait_time:.2f} seconds")
            await asyncio.sleep(wait_time)
        
        # Apply current delay
        await asyncio.sleep(self.delay)
        self.calls.append(now)

    def report_success(self) -> None:
        """Report successful API call to reduce delay."""
        if self.last_error is None or \
           datetime.now() - self.last_error > timedelta(minutes=5):
            self.delay = max(
                self.min_delay,
                self.delay * self.success_reduction
            )
            self.logger.debug(f"Success reported. New delay: {self.delay:.2f}s")

    def report_error(self) -> None:
        """Report API error to increase delay."""
        self.delay = min(
            self.max_delay,
            self.delay * self.backoff_factor
        )
        self.last_error = datetime.now()
        self.logger.warning(f"Error reported. New delay: {self.delay:.2f}s")