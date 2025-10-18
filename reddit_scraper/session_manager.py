"""Centralized session management for HTTP and Reddit API connections."""

import aiohttp
import asyncio
import logging
from typing import Optional
import asyncpraw
from .config import ConfigManager

class SessionManager:
    """Manages sessions for both HTTP and Reddit API connections."""
    
    _instance = None
    _session: Optional[aiohttp.ClientSession] = None
    _reddit: Optional[asyncpraw.Reddit] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SessionManager, cls).__new__(cls)
            cls._instance.logger = logging.getLogger(__name__)
        return cls._instance
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared HTTP session."""
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
                    raise_for_status=True,
                    headers={'User-Agent': 'RedditImageScraper/2.0'}
                )
                
                self.logger.info("Created new HTTP session with connection pooling")
            
            return self._session

    async def create_reddit_session(self, config_manager: ConfigManager) -> asyncpraw.Reddit:
        """Create and initialize a Reddit API session."""
        try:
            credentials = config_manager.get_reddit_credentials()
            
            if not all(credentials.get(key) for key in ['client_id', 'client_secret', 'user_agent']):
                raise ValueError("Missing required Reddit credentials")
            
            self._reddit = asyncpraw.Reddit(**credentials)
            
            # Test the connection
            user = await self._reddit.user.me()
            if user is None:
                raise ValueError("Failed to authenticate with Reddit")
                
            self.logger.info(f"Successfully authenticated as: {user.name}")
            return self._reddit
            
        except Exception as e:
            self.logger.error(f"Failed to create Reddit session: {str(e)}")
            raise
    
    async def close(self):
        """Close all shared sessions."""
        async with self._lock:
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
                self.logger.info("Closed HTTP session")
            
            if self._reddit:
                await self._reddit.close()
                self._reddit = None
                self.logger.info("Closed Reddit session")
    
    async def __aenter__(self):
        """Support async context manager"""
        return await self.get_session()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up on context exit"""
        # Don't close session here - it's shared
        pass


    async def __aenter__(self):
        """Support async context manager"""
        return await self.get_session()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up on context exit"""
        # Don't close session here - it's shared
        pass