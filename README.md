# Reddit Image Scraper

An asynchronous Python application that efficiently scrapes image URLs from Reddit subreddits, with comprehensive validation, progress tracking, and CSV file management.

## Features

- Asynchronous processing for improved performance
- Object-oriented design with clear separation of concerns
- Progress visualization for all operations
- Filters for specific image formats (JPG, PNG, JPEG)
- Advanced duplicate detection and removal
- Automatic deleted image detection and filtering
- Domain-based filtering (configurable excluded domains)
- Excel-compatible CSV output with proper encoding
- Comprehensive CSV maintenance tools
- Secure credential and configuration management

## Requirements

### Python Libraries

Install the required libraries using pip:

```bash
pip install asyncpraw aiohttp opencv-python numpy tqdm aiofiles
```

- **asyncpraw** - Asynchronous Reddit API Wrapper
- **aiohttp** - Asynchronous HTTP requests
- **opencv-python** - Image processing and comparison
- **numpy** - Array operations for image data
- **tqdm** - Progress bar visualization
- **aiofiles** - Asynchronous file operations
- **opencv-python** - Image processing and comparison
- **numpy** - Array operations for image data

### Reddit API Setup

1. Go to [Reddit App Preferences](https://www.reddit.com/prefs/apps)
2. Click "Create App" or "Create Another App"
3. Choose "script" as the app type
4. Note down your `client_id` and `client_secret`

## Configuration

### First Run Setup

1. Create a `sub_list.csv` file with the subreddits you want to scrape (one per line):

```
Pixiv
Art
DigitalPainting
```

2. Run the script - it will prompt you to enter your Reddit credentials:

   - Client ID
   - Client Secret
   - User Agent (e.g., "MyRedditBot/1.0")
   - Reddit Username
   - Reddit Password

3. Your credentials will be securely saved to `reddit_config.json`

### Configuration File Structure

The script creates a `reddit_config.json` file with comprehensive settings:

```json
{
  "reddit_credentials": {
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "user_agent": "your_user_agent",
    "username": "your_username",
    "password": "your_password"
  },
  "scraping_settings": {
    "post_limit": 100,
    "search_type": "top",
    "supported_formats": ["jpg", "png", "jpeg"],
    "excluded_domains": ["i.imgur.com", "v.redd.it"],
    "enable_duplicate_detection": true,
    "enable_deleted_image_check": true,
    "batch_size": 10,
    "min_image_size": 10240
  },
  "performance_settings": {
    "request_timeout_seconds": 30,
    "retry_attempts": 3,
    "rate_limit_delay": 1.0,
    "max_workers": 4,
    "max_memory_mb": 500,
    "reddit_api_retries": 3,
    "reddit_api_retry_delay": 5
  },
  "output_settings": {
    "csv_encoding": "utf-8-sig",
    "summary_filename": "new_img.csv",
    "log_level": "INFO",
    "save_error_logs": true
  }
}
```

## Usage

### Running the Script

```bash
python main.py
```

### Available Operations

The script provides four operation modes:

1. **Scrape New Images**

   - Reads subreddit names from `sub_list.csv`
   - Connects to Reddit using secure credentials
   - For each subreddit:
     - Scrapes top posts with progress visualization
     - Validates images and checks for deletions
     - Filters by supported formats and domains
     - Detects and removes duplicates
   - Saves to individual CSV files: `{subreddit}_img_list.csv`
   - Creates a summary file: `new_img.csv`

2. **Clean Existing CSVs**

   - Scans all existing subreddit CSV files
   - Validates each image URL:
     - Checks format validity
     - Verifies image accessibility
     - Ensures minimum size requirements
   - Removes dead or invalid links
   - Updates CSV files with clean data
   - Generates error logs for failed validations

3. **Combined Operation**

   - Performs both scraping and cleaning in sequence
   - Ensures completely clean and up-to-date results

4. **Clean Specific Subreddit**
   - Cleans a single subreddit's CSV file
   - Provides detailed progress and results
   - Creates subreddit-specific error log

### Output Files

- `{subreddit}_img_list.csv` - Complete list of image URLs for each subreddit
- `new_img.csv` - URLs of images found in the current run
- `reddit_config.json` - Configuration and credentials
- `{subreddit}_errors.log` - Error details for failed validations
- `reddit_scraper.log` - General operation logs

## Project Structure

```
project/
├── main.py                 # Main entry point
├── sub_list.csv           # List of subreddits to scrape
├── reddit_config.json     # Configuration file
├── reddit_scraper/        # Package directory
│   ├── __init__.py       # Package initialization
│   ├── auth.py           # Authentication handling
│   ├── config.py         # Configuration management
│   ├── data_manager.py   # Data persistence operations
│   ├── image_processor.py # Image validation and processing
│   ├── cleaner.py        # CSV cleaning functionality
│   └── scraper.py        # Main scraping implementation
├── {subreddit}_img_list.csv  # Results for each subreddit
├── new_img.csv            # Latest scraping results
└── .gitignore            # Git ignore configuration
```

## Security Notes

- Credentials are stored locally in `reddit_config.json`
- The script creates a `.gitignore` file to prevent credential exposure
- Never share your `reddit_config.json` file

## Excel Integration

The CSV files are formatted for easy Excel integration:

- UTF-8-sig encoding for proper character display
- Consistent column structure
- Compatible with Excel's Data → From Text/CSV import feature

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Configuration Details

### Scraping Settings

- `post_limit` (int) - Number of posts to check per subreddit (default: 100)
- `search_type` (str) - Post sorting method (default: "top")
- `supported_formats` (list) - Image formats to collect (jpg, png, jpeg)
- `excluded_domains` (list) - Domains to skip (e.g., ["i.imgur.com", "v.redd.it"])
- `enable_duplicate_detection` (bool) - Compare images for duplicates
- `enable_deleted_image_check` (bool) - Verify image accessibility
- `batch_size` (int) - Number of images to process in parallel (default: 10)
- `min_image_size` (int) - Minimum image size in bytes (default: 10KB)

### Performance Settings

- `request_timeout_seconds` (int) - HTTP request timeout (default: 30)
- `retry_attempts` (int) - Number of retries for failed requests (default: 3)
- `rate_limit_delay` (float) - Delay between requests (default: 1.0)
- `max_workers` (int) - Maximum concurrent workers (default: 4)
- `max_memory_mb` (int) - Maximum memory usage in MB (default: 500)
- `reddit_api_retries` (int) - Reddit API retry attempts (default: 3)
- `reddit_api_retry_delay` (int) - Delay between API retries (default: 5)

### Output Settings

- `csv_encoding` (str) - File encoding for CSV files (default: "utf-8-sig")
- `summary_filename` (str) - Name of the combined results file
- `log_level` (str) - Logging level (default: "INFO")
- `save_error_logs` (bool) - Save detailed error logs (default: true)

## Security Notes

- Credentials are stored locally in `reddit_config.json`
- The script creates a `.gitignore` file to prevent credential files from being committed
- Never share your `reddit_config.json` file

## File Structure

```

project/
├── Reddit_API.py # Main script
├── sub_list.csv # List of subreddits to scrape
├── reddit_config.json # Credentials (auto-generated)
├── {subreddit}\_img_list.csv # Results for each subreddit
├── new_img.csv # Latest scraping results
└── .gitignore # Prevents committing sensitive files

```

## Excel Integration

The CSV files are formatted for easy import into Excel:

- UTF-8-sig encoding for proper character display
- One URL per row for easy filtering and analysis
- Compatible with Excel's Data → From Text/CSV import feature

## Troubleshooting

### Common Issues and Solutions

#### Authentication Issues

- **"Failed to connect to Reddit API"** - Verify credentials in config file
- **"NoneType object has no attribute 'name'"** - Check Reddit password and permissions
- **Rate limiting** - Adjust `rate_limit_delay` in config if encountering limits

#### Data Issues

- **"Failed to check image"** - Network issues or deleted images (auto-retried)
- **Duplicate images** - Enable `enable_duplicate_detection` in config
- **Missing files** - Create required CSV files before running

### Best Practices

#### Regular Maintenance

- Use option 2 or 3 in the menu to run cleanup regularly
- Monitor CSV files for growing size and duplicates
- Adjust performance settings based on your network conditions

#### Performance Optimization

- Set appropriate `post_limit` based on your needs
- Configure `retry_attempts` and `request_timeout_seconds` for reliability
- Use `rate_limit_delay` to balance speed and stability

## Contributing

Feel free to submit issues or pull requests to improve the functionality.
