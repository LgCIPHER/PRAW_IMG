"""Retry handler with exponential backoff for network operations."""

import asyncio
import functools
import logging
import random
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

T = TypeVar('T')

@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True
    jitter_factor: float = 0.1  # 10% jitter

class RetryHandler:
    """Handles retry logic with exponential backoff"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.logger = logging.getLogger(__name__)
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and optional jitter
        
        Args:
            attempt: Current attempt number (1-indexed)
            
        Returns:
            float: Delay in seconds before next retry
        """
        # Calculate base exponential delay
        delay = min(
            self.config.base_delay * (2 ** (attempt - 1)),
            self.config.max_delay
        )
        
        # Add jitter if enabled
        if self.config.jitter:
            jitter_range = delay * self.config.jitter_factor
            delay += random.random() * jitter_range
            
        return delay
        
    def _is_retryable(self, exception: Exception) -> bool:
        """Determine if an exception is retryable
        
        Args:
            exception: Exception to check
            
        Returns:
            bool: True if the error should be retried
        """
        # Import here to avoid circular imports
        import aiohttp
        
        # Network errors are retryable
        retryable_types = (
            aiohttp.ClientError,
            aiohttp.ServerTimeoutError,
            ConnectionError,
            TimeoutError
        )
        
        if isinstance(exception, retryable_types):
            return True
        
        # HTTP errors: retry 5xx and 429 (rate limit)
        if isinstance(exception, aiohttp.ClientResponseError):
            return exception.status >= 500 or exception.status == 429
        
        return False
    
    async def retry_async(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute async function with retry logic
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Any: Function result
            
        Raises:
            Exception: Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            try:
                return await func(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                if not self._is_retryable(e):
                    raise
                
                if attempt < self.config.max_retries - 1:
                    delay = self.calculate_delay(attempt + 1)
                    self.logger.warning(
                        f"Attempt {attempt + 1}/{self.config.max_retries} failed for {func.__name__}: {str(e)}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(
                        f"All {self.config.max_retries} retries failed for {func.__name__}: {str(e)}"
                    )
        
        raise last_exception
    
    async def download_image(self, url: str, session: Any) -> Optional[bytes]:
        """Download image with automatic retry"""
        async with session.get(url) as response:
            if response.status != 200:
                raise ValueError(f"HTTP {response.status}")
            return await response.read()


def with_retry(config: Optional[RetryConfig] = None):
    """Decorator to retry async functions with exponential backoff.
    
    Args:
        config: Optional RetryConfig instance for customizing retry behavior
        
    Returns:
        Callable: Decorated function with retry behavior
    """
    retry_config = config or RetryConfig()
    
    def decorator(func: Callable[..., Any]):
        # Create handler inside wrapper to avoid circular imports
        handler = RetryHandler(retry_config)
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await handler.retry_async(func, *args, **kwargs)
        return wrapper
    return decorator