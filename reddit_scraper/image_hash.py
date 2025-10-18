"""Image hashing functionality for detecting similar images"""

import imagehash
from PIL import Image
import json
import os
from typing import Dict, Optional, List, Tuple
import logging
from dataclasses import dataclass
import aiohttp
import io

@dataclass
class HashComparisonResult:
    """Result of image hash comparison"""
    is_similar: bool
    similar_to: Optional[str] = None
    hash_difference: Optional[int] = None
    error: Optional[str] = None

class ImageHashProcessor:
    """Handles perceptual image hashing and comparison"""
    
    def __init__(self, hash_file: str = 'image_hashes.json', hash_threshold: int = 5, session: Optional[aiohttp.ClientSession] = None):
        """Initialize the ImageHashProcessor.
        
        Args:
            hash_file (str): Path to the JSON file storing image hashes.
            hash_threshold (int): Maximum hash difference to consider images similar.
            session (Optional[aiohttp.ClientSession]): Existing aiohttp session to use.
        """
        self.hash_file = hash_file
        self.hash_threshold = hash_threshold
        self.hash_database: Dict[str, str] = self._load_hashes()
        self.logger = logging.getLogger(__name__)
        self.session = session
        self._owns_session = False
    
    async def __aenter__(self):
        """Set up async context"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            self._owns_session = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up async context"""
        if self.session and self._owns_session:
            await self.session.close()
            self.session = None
    
    def _load_hashes(self) -> Dict[str, str]:
        """Load existing hashes from the JSON file.
        
        Returns:
            Dict[str, str]: Dictionary mapping image URLs to their hashes.
        """
        if os.path.exists(self.hash_file):
            try:
                with open(self.hash_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def _save_hashes(self) -> None:
        """Save the current hash database to the JSON file."""
        with open(self.hash_file, 'w') as f:
            json.dump(self.hash_database, f, indent=4)
    
    async def compute_hash(self, url: str) -> Optional[str]:
        """Compute the perceptual hash of an image from its URL.
        
        Args:
            url (str): URL of the image.
            
        Returns:
            Optional[str]: Hexadecimal string representation of the hash,
                          or None if computation fails.
        """
        try:
            if not self.session:
                self.logger.error("Session not initialized. Use within async context manager.")
                return None
                
            async with self.session.get(url) as response:
                if response.status != 200:
                    self.logger.warning(f"Failed to download image {url}: Status {response.status}")
                    return None
                    
                data = await response.read()
                img = Image.open(io.BytesIO(data))
                
                # Convert to RGB if needed (handles PNG with transparency)
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])
                    img = background
                    
                # Compute average hash (can be adjusted to use other hash types)
                hash_value = str(imagehash.average_hash(img))
                return hash_value
                
        except Exception as e:
            self.logger.error(f"Error computing hash for {url}: {str(e)}")
            return None
    
    async def add_image_hash(self, url: str) -> Optional[str]:
        """Compute and store the hash for a new image.
        
        Args:
            url (str): URL of the image.
            
        Returns:
            Optional[str]: The computed hash value or None if computation fails.
        """
        hash_value = await self.compute_hash(url)
        if hash_value:
            self.hash_database[url] = hash_value
            self._save_hashes()
        return hash_value
    
    async def compare_image(self, url: str) -> HashComparisonResult:
        """Compare an image against the database of stored hashes.
        
        Args:
            url (str): URL of the image to compare.
            
        Returns:
            HashComparisonResult: Result of the comparison with details.
        """
        target_hash = await self.compute_hash(url)
        if not target_hash:
            return HashComparisonResult(
                is_similar=False,
                error="Failed to compute hash for target image"
            )
        
        target_hash_obj = imagehash.hex_to_hash(target_hash)
        best_match = None
        min_difference = float('inf')
        
        for stored_url, hash_str in self.hash_database.items():
            if stored_url != url:  # Don't compare with self
                try:
                    stored_hash = imagehash.hex_to_hash(hash_str)
                    difference = target_hash_obj - stored_hash
                    
                    if difference < min_difference:
                        min_difference = difference
                        best_match = stored_url
                        
                    if difference <= self.hash_threshold:
                        return HashComparisonResult(
                            is_similar=True,
                            similar_to=stored_url,
                            hash_difference=difference
                        )
                except Exception as e:
                    self.logger.warning(f"Error comparing hashes: {e}")
                    continue
        
        # If we found a best match but it's above threshold, include it in result
        if best_match:
            return HashComparisonResult(
                is_similar=False,
                similar_to=best_match,
                hash_difference=min_difference
            )
            
        return HashComparisonResult(is_similar=False)
    
    def remove_image_hash(self, url: str) -> bool:
        """Remove an image hash from the database.
        
        Args:
            url (str): URL of the image to remove.
            
        Returns:
            bool: True if the hash was removed, False if it wasn't found.
        """
        if url in self.hash_database:
            del self.hash_database[url]
            self._save_hashes()
            return True
        return False