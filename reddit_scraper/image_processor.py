"""Image processing functionality for Reddit Image Scraper"""

import cv2 as cv
import numpy as np
import aiohttp
import asyncio
from typing import Tuple, Optional
import logging
from dataclasses import dataclass
from typing import List
import time
from functools import wraps

@dataclass
class ImageValidationResult:
    """Result of image validation"""
    is_valid: bool
    is_deleted: bool
    error_message: Optional[str] = None

class ImageProcessor:
    """Handles image downloading and validation"""
    
    def __init__(self, min_size_bytes: int = 10240):
        self.min_size_bytes = min_size_bytes
        self.session = None
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        """Set up async context"""
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up async context"""
        if self.session:
            await self.session.close()

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
                return ImageValidationResult(False, True, "Failed to download image")

            # Check if image is deleted (60x130 is Reddit's deleted image size)
            if image.shape[0] == 60 and image.shape[1] == 130:
                return ImageValidationResult(False, True, "Image is deleted")

            # Check minimum size
            if not self._check_image_size(image):
                return ImageValidationResult(False, False, "Image too small")

            return ImageValidationResult(True, False)

        except Exception as e:
            return ImageValidationResult(False, False, str(e))

    def _check_image_size(self, image: np.ndarray) -> bool:
        """Check if image meets minimum size requirements"""
        try:
            return image.nbytes >= self.min_size_bytes
        except Exception:
            return False

    @staticmethod
    def is_valid_format(url: str, supported_formats: List[str]) -> bool:
        """Check if URL points to a supported image format"""
        try:
            url_lower = url.lower()
            is_valid = any(f".{fmt}" in url_lower for fmt in supported_formats)
            if not is_valid:
                logging.getLogger(__name__).info(f"Invalid format URL: {url}")
            return is_valid
        except Exception as e:
            logging.getLogger(__name__).error(f"Error checking format for URL {url}: {e}")
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