"""Unit tests for Reddit Image Scraper"""

import pytest
import asyncio
from unittest.mock import Mock, patch
import os
import json
from pathlib import Path

from reddit_scraper.config import ConfigManager, ConfigValidationError
from reddit_scraper.image_processor import ImageProcessor, ImageValidationResult
from reddit_scraper.scraper import RedditImageScraper

# Fixture for test configuration
@pytest.fixture
def test_config():
    return {
        "reddit_credentials": {
            "client_id": "test_id",
            "client_secret": "test_secret",
            "user_agent": "test_agent",
            "username": "test_user",
            "password": "test_pass"
        },
        "scraping_settings": {
            "post_limit": 10,
            "search_type": "top",
            "supported_formats": ["jpg", "png"],
            "excluded_domains": ["test.com"],
            "enable_duplicate_detection": True,
            "enable_deleted_image_check": True,
            "batch_size": 5,
            "min_image_size": 1024,
            "hash_config": {
                "enable_hash_comparison": True,
                "hash_file": "test_hashes.json",
                "hash_threshold": 5,
                "hash_type": "average"
            }
        }
    }

# Fixture for test image processor
@pytest.fixture
async def image_processor():
    processor = ImageProcessor(min_size_bytes=1024)
    async with processor:
        yield processor

# Test configuration validation
async def test_config_validation(test_config, tmp_path):
    # Write test config to temporary file
    config_path = tmp_path / "test_config.json"
    with open(config_path, "w") as f:
        json.dump(test_config, f)
    
    # Test valid configuration
    config_manager = ConfigManager(str(config_path))
    assert await config_manager.load_and_validate_config()
    
    # Test invalid configuration
    invalid_config = test_config.copy()
    del invalid_config["reddit_credentials"]["client_id"]
    with open(config_path, "w") as f:
        json.dump(invalid_config, f)
    
    with pytest.raises(ConfigValidationError):
        await config_manager.load_and_validate_config()

# Test image validation
async def test_image_validation(image_processor):
    # Test valid image URL
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = b"fake_image_data"
        mock_get.return_value.__aenter__.return_value = mock_response
        
        result = await image_processor.validate_image("http://test.com/image.jpg")
        assert isinstance(result, ImageValidationResult)

# Test batch processing
async def test_batch_processing(image_processor):
    urls = [f"http://test.com/image{i}.jpg" for i in range(5)]
    
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = b"fake_image_data"
        mock_get.return_value.__aenter__.return_value = mock_response
        
        results = await image_processor.process_image_batch(urls)
        assert len(results) == len(urls)
        
# Test error handling
async def test_error_handling(image_processor):
    with patch("aiohttp.ClientSession.get") as mock_get:
        # Simulate network error
        mock_get.side_effect = aiohttp.ClientError()
        
        result = await image_processor.validate_image("http://test.com/error.jpg")
        assert not result.is_valid
        assert result.message is not None

if __name__ == "__main__":
    pytest.main([__file__])