"""Retry handler with exponential backoff for network operations"""

import asyncio
import logging
from typing import Callable, TypeVar, Optional, Any
from functools import wraps
import random

T = TypeVar('T')

class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter


class RetryHandler:
    """Handles retry logic with exponential backoff"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.logger = logging.getLogger(__name__)
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and optional jitter
        
        Args:
            attempt: Current attempt number (0-indexed)
        
        Returns:
            Delay in seconds
        """
        # Calculate exponential delay
        delay = min(
            self.config.base_delay * (self.config.exponential_base ** attempt),
            self.config.max_delay
        )
        
        # Add jitter to prevent thundering herd
        if self.config.jitter:
            delay = delay * (0.5 + random.random())
        
        return delay
    
    async def retry_async(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute async function with retry logic
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
        
        Returns:
            Function result
        
        Raises:
            Exception: Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                return await func(*args, **kwargs)
            
            except asyncio.TimeoutError as e:
                last_exception = e
                if attempt < self.config.max_attempts - 1:
                    delay = self.calculate_delay(attempt)
                    self.logger.warning(
                        f"Timeout on attempt {attempt + 1}/{self.config.max_attempts}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(
                        f"Failed after {self.config.max_attempts} attempts (timeout)"
                    )
            
            except Exception as e:
                last_exception = e
                # Check if error is retryable
                if not self._is_retryable(e):
                    raise
                
                if attempt < self.config.max_attempts - 1:
                    delay = self.calculate_delay(attempt)
                    self.logger.warning(
                        f"Error on attempt {attempt + 1}/{self.config.max_attempts}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(
                        f"Failed after {self.config.max_attempts} attempts: {e}"
                    )
        
        raise last_exception
    
    def _is_retryable(self, exception: Exception) -> bool:
        """Determine if an exception is retryable
        
        Args:
            exception: Exception to check
        
        Returns:
            True if the error should be retried
        """
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


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0
):
    """Decorator to add retry logic to async functions
    
    Usage:
        @with_retry(max_attempts=3, base_delay=1.0)
        async def my_function():
            # Your code here
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay
            )
            handler = RetryHandler(config)
            return await handler.retry_async(func, *args, **kwargs)
        return wrapper
    return decorator


# Example usage in ImageProcessor
class EnhancedImageProcessor:
    """ImageProcessor with built-in retry logic"""
    
    def __init__(self, min_size_bytes: int = 10240):
        self.min_size_bytes = min_size_bytes
        self.logger = logging.getLogger(__name__)
        self.retry_handler = RetryHandler(
            RetryConfig(max_attempts=3, base_delay=1.0, max_delay=10.0)
        )
    
    @with_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def download_image(self, url: str, session: Any) -> Optional[bytes]:
        """Download image with automatic retry"""
        async with session.get(url) as response:
            if response.status != 200:
                raise ValueError(f"HTTP {response.status}")
            return await response.read()
    
    async def validate_image(self, url: str, session: Any):
        """Validate image with retry logic"""
        try:
            image_data = await self.download_image(url, session)
            if image_data:
                # Perform validation
                return {"is_valid": True, "size": len(image_data)}
            return {"is_valid": False, "reason": "Download failed"}
        except Exception as e:
            self.logger.error(f"Failed to validate image {url}: {e}")
            return {"is_valid": False, "reason": str(e)}