"""Centralized HTTP session management for efficient connection pooling"""

import aiohttp
import asyncio
from typing import Optional
import logging

class SessionManager:
    """Manages a single aiohttp session for the entire application
    
    This prevents the overhead of creating multiple sessions and
    provides efficient connection pooling across all HTTP requests.
    """
    
    _instance = None
    _session = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SessionManager, cls).__new__(cls)
            cls._instance.logger = logging.getLogger(__name__)
        return cls._instance
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared session
        
        Returns:
            aiohttp.ClientSession: Configured session with optimal settings
        """
        async with self._lock:
            if self._session is None or self._session.closed:
                # Configure timeouts
                timeout = aiohttp.ClientTimeout(
                    total=30,  # Total timeout
                    connect=10,  # Connection timeout
                    sock_read=20  # Socket read timeout
                )
                
                # Configure connection limits
                connector = aiohttp.TCPConnector(
                    limit=100,  # Max total connections
                    limit_per_host=30,  # Max connections per host
                    ttl_dns_cache=300,  # DNS cache TTL
                    enable_cleanup_closed=True
                )
                
                self._session = aiohttp.ClientSession(
                    timeout=timeout,
                    connector=connector,
                    headers={'User-Agent': 'RedditImageScraper/2.0'}
                )
                
                self.logger.info("Created new HTTP session with connection pooling")
            
            return self._session
    
    async def close(self):
        """Close the shared session"""
        async with self._lock:
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
                self.logger.info("Closed HTTP session")
    
    async def __aenter__(self):
        """Support async context manager"""
        return await self.get_session()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up on context exit"""
        # Don't close session here - it's shared
        pass


class ImageProcessor:
    """Enhanced ImageProcessor using shared session"""
    
    def __init__(self, min_size_bytes: int = 10240, hash_config: Optional[dict] = None):
        self.min_size_bytes = min_size_bytes
        self.logger = logging.getLogger(__name__)
        self.session_manager = SessionManager()
        self.hash_processor = None
        
        if hash_config is not None:
            from .image_hash import ImageHashProcessor
            self.hash_processor = ImageHashProcessor(
                hash_file=hash_config["hash_file"],
                hash_threshold=hash_config["hash_threshold"]
            )
    
    async def __aenter__(self):
        """Get session on context enter"""
        self.session = await self.session_manager.get_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Session is managed globally, so no cleanup needed here"""
        pass
    
    async def download_image(self, url: str) -> Optional[bytes]:
        """Download image using shared session"""
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    self.logger.warning(
                        f"Failed to download {url}: Status {response.status}"
                    )
                    return None
                return await response.read()
        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout downloading {url}")
            return None
        except aiohttp.ClientError as e:
            self.logger.error(f"Client error downloading {url}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error downloading {url}: {e}")
            return None


# Usage example in main.py cleanup
async def cleanup_resources():
    """Properly close all shared resources"""
    session_manager = SessionManager()
    await session_manager.close()
    logging.info("All resources cleaned up")