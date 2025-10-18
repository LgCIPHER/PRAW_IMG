"""Enhanced image processing with batch operations and error handling"""

import cv2 as cv
import numpy as np
import aiohttp
import asyncio
import io
from typing import Dict, List, Optional, Tuple, Any
import logging
from dataclasses import dataclass
from functools import wraps
import time
import psutil
from contextlib import asynccontextmanager
from PIL import Image

from .base import ProcessingStatistics, RedditScraperException
from .image_hash import ImageHashProcessor, HashComparisonResult

class ImageProcessingError(RedditScraperException):
    """Base exception for image processing errors"""
    pass

class DownloadError(ImageProcessingError):
    """Raised when image download fails"""
    pass

class ValidationError(ImageProcessingError):
    """Raised when image validation fails"""
    pass
from .image_hash import ImageHashProcessor, HashComparisonResult

@dataclass
class ImageValidationResult:
    """Result of image validation"""
    is_valid: bool
    is_deleted: bool
    width: Optional[int] = None
    height: Optional[int] = None
    size: Optional[int] = None
    is_similar: bool = False
    similar_to: Optional[str] = None
    hash_difference: Optional[int] = None
    message: Optional[str] = None
    skip_reason: str = ""  # Added for CSV cleaning process

class ImageProcessor:
    """Handles image downloading and validation"""
    
    def __init__(self, config_manager = None):
        self.min_size_bytes = getattr(config_manager.scraping_config, "min_image_size", 10240) if config_manager else 10240
        self.session = None
        self.logger = logging.getLogger(__name__)
        self.hash_processor = None
        
        # Initialize hash processor if config is provided
        if config_manager and hasattr(config_manager.scraping_config, "hash_config"):
            hash_config = config_manager.scraping_config.hash_config
            self.hash_processor = ImageHashProcessor(
                hash_file=hash_config.hash_file,
                hash_threshold=hash_config.hash_threshold,
                session=self.session  # Pass our session to the hash processor
            )

    async def __aenter__(self):
        """Set up async context"""
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # Update hash processor's session if it exists
            if self.hash_processor:
                self.hash_processor.session = self.session
                self.hash_processor._owns_session = False
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up async context"""
        try:
            if self.hash_processor:
                # Ensure hash processor saves any pending changes
                self.hash_processor._save_hashes()
                # Clear the session reference but don't close it
                self.hash_processor.session = None
                
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
            raise

    def rate_limit(calls_per_second: float = 1.0):
        """Decorator for rate limiting"""
        min_interval = 1.0 / calls_per_second
        last_called = [0.0]
        
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                elapsed = time.time() - last_called[0]
                left_to_wait = min_interval - elapsed
                
                if left_to_wait > 0:
                    await asyncio.sleep(left_to_wait)
                    
                ret = await func(*args, **kwargs)
                last_called[0] = time.time()
                return ret
            return wrapper
        return decorator

    @rate_limit(calls_per_second=2)
    async def download_image(self, url: str) -> Optional[np.ndarray]:
        """Download image from URL"""
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    self.logger.warning(f"Failed to download image {url}: Status {response.status}")
                    return None
                    
                data = await response.read()
                image = np.asarray(bytearray(data), dtype="uint8")
                return cv.imdecode(image, cv.IMREAD_COLOR)
                
        except Exception as e:
            self.logger.error(f"Error downloading image {url}: {e}")
            return None

    async def validate_image(self, url: str) -> ImageValidationResult:
        """Validate image from URL"""
        try:
            image = await self.download_image(url)
            if image is None:
                return ImageValidationResult(
                    is_valid=False, 
                    is_deleted=True,
                    message="Failed to download image",
                    skip_reason="download_failed",
                    width=None,
                    height=None,
                    size=0
                )

            # Get image dimensions
            height, width = image.shape[:2]
            size = image.nbytes

            # Check if image is deleted (60x130 is Reddit's deleted image size)
            if height == 60 and width == 130:
                return ImageValidationResult(
                    is_valid=False, 
                    is_deleted=True,
                    message="Image is deleted",
                    skip_reason="deleted",
                    width=width,
                    height=height,
                    size=size
                )

            # Get image dimensions
            height, width = image.shape[:2]
            size = image.nbytes

            # Check minimum size
            if not self._check_image_size(image):
                return ImageValidationResult(
                    is_valid=False, 
                    is_deleted=False,
                    message="Image too small",
                    skip_reason="too_small",
                    width=width,
                    height=height,
                    size=size
                )

            # Perform hash comparison if enabled
            if self.hash_processor and self.hash_processor.session:
                hash_result = await self.hash_processor.compare_image(url)
                if hash_result.is_similar:
                    return ImageValidationResult(
                        is_valid=False,
                        is_deleted=False,
                        is_similar=True,
                        similar_to=hash_result.similar_to,
                        hash_difference=hash_result.hash_difference,
                        message=f"Similar to existing image (difference: {hash_result.hash_difference})",
                        skip_reason="duplicate",
                        width=width,
                        height=height,
                        size=size
                    )
                
                # Add hash to database for valid images
                await self.hash_processor.add_image_hash(url)

            return ImageValidationResult(
                is_valid=True, 
                is_deleted=False,
                message="Image is valid",
                skip_reason="",  # Empty string for valid images
                width=width,
                height=height,
                size=size
            )

        except Exception as e:
            return ImageValidationResult(
                is_valid=False, 
                is_deleted=False,
                message=str(e),
                skip_reason="error"
            )

    def _check_image_size(self, image: np.ndarray) -> bool:
        """Check if image meets minimum size requirements"""
        try:
            return image.nbytes >= self.min_size_bytes
        except Exception:
            return False

    def is_valid_format(self, url: str, supported_formats: List[str]) -> bool:
        """Check if URL points to a supported image format"""
        try:
            # Skip non-url entries
            if not url or not isinstance(url, str):
                return False
                
            # Skip gallery links
            if '/gallery/' in url:
                return False
            
            # Skip video links    
            if 'v.redd.it' in url:
                return False
                
            # Check for image extensions
            url_lower = url.lower()
            is_valid = any(f".{fmt}" in url_lower for fmt in supported_formats)
            if not is_valid:
                self.logger.info(f"Invalid format URL: {url}")
            return is_valid
            
        except Exception as e:
            self.logger.error(f"Error checking format for URL {url}: {e}")
            return False

    async def compare_images(self, url1: str, url2: str) -> bool:
        """Compare two images for duplicates"""
        try:
            img1 = await self.download_image(url1)
            img2 = await self.download_image(url2)
            
            if img1 is None or img2 is None:
                return False
                
            if img1.shape != img2.shape:
                return False
                
            difference = cv.subtract(img1, img2)
            b, g, r = cv.split(difference)
            return cv.countNonZero(b) == 0 and cv.countNonZero(g) == 0 and cv.countNonZero(r) == 0
            
        except Exception as e:
            self.logger.error(f"Error comparing images: {e}")
            return False