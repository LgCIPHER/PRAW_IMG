# Reddit Image Scraper

A Python script that efficiently scrapes image URLs from specified Reddit subreddits, with progress tracking and comprehensive validation, saving them to CSV files for further analysis or processing.

## Features

- Scrapes image URLs from multiple subreddits with progress visualization
- Filters for specific image formats (JPG, PNG, JPEG)
- Advanced duplicate detection and removal
- Automatic deleted image detection and filtering
- Domain-based filtering (configurable excluded domains)
- Progress bars for real-time scraping status
- Excel-compatible CSV output with proper encoding
- Secure credential and configuration management via JSON
- Bulk CSV cleanup and maintenance tools

## Requirements

### Python Libraries

Install the required libraries using pip:

```bash
pip install praw requests opencv-python numpy
```

- **PRAW** (Python Reddit API Wrapper) - Reddit API access
- **requests** - HTTP requests for image validation
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
    "post_limit": 20,
    "search_type": "top",
    "supported_formats": ["jpg", "png", "jpeg"],
    "excluded_domains": ["i.imgur.com"],
    "enable_duplicate_detection": true,
    "enable_deleted_image_check": true
  },
  "performance_settings": {
    "request_timeout_seconds": 30,
    "retry_attempts": 5,
    "rate_limit_delay": 1.0
  },
  "output_settings": {
    "csv_encoding": "utf-8-sig",
    "summary_filename": "new_img.csv"
  }
}
```

## Usage

### Basic Usage

```bash
python Reddit_API.py
```

### What the Script Does

The script offers three main operation modes:

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
   - Checks each URL for validity and accessibility
   - Removes broken or deleted image links
   - Updates CSV files with clean data

3. **Combined Operation**
   - Performs both scraping and cleaning in sequence
   - Ensures completely clean and up-to-date results

### Output Files

- `{subreddit}_img_list.csv` - Complete list of image URLs for each subreddit
- `new_img.csv` - URLs of images found in the current run
- `reddit_config.json` - Secure credential storage (auto-generated)

## Functions

### Key Functions

#### Core Functions

- `main()` - Entry point with interactive mode selection
- `Reddit_API()` - Main scraping function with progress tracking
- `scan_csv()` - CSV file maintenance and cleanup

#### Configuration Management

- `create_token()` - Interactive credential setup
- `load_config()` - Loads or creates configuration
- `create_default_config()` - Generates default configuration

#### Subreddit Processing

- `process_subreddit()` - Handles individual subreddit scraping
- `read_subreddit_list()` - Loads and validates subreddit names
- `scan_subreddit_csv()` - Cleans individual subreddit files

#### Image Processing

- `check_deleted_img()` - Validates image accessibility
- `safe_check_deleted_img()` - Robust image checking with retries
- `compare_img()` - OpenCV-based image comparison
- `html_to_img()` - Converts URL to image array

#### File Operations

- `save_urls_to_csv()` - Writes URLs with error handling
- `past_list()` - Loads existing URLs with validation

## Configuration Options

All settings are managed through `reddit_config.json`:

### Scraping Settings

- `post_limit` - Number of posts to check per subreddit (default: 20)
- `search_type` - Post sorting method (default: "top")
- `supported_formats` - Image formats to collect (jpg, png, jpeg)
- `excluded_domains` - Domains to skip (e.g., ["i.imgur.com"])
- `enable_duplicate_detection` - Compare images for duplicates
- `enable_deleted_image_check` - Verify image accessibility

### Performance Settings

- `request_timeout_seconds` - HTTP request timeout
- `retry_attempts` - Number of retries for failed requests
- `rate_limit_delay` - Delay between requests to avoid rate limiting

### Output Settings

- `csv_encoding` - File encoding for CSV files
- `summary_filename` - Name of the combined results file

## Security Notes

- Credentials are stored locally in `reddit_config.json`
- The script creates a `.gitignore` file to prevent credential files from being committed
- Never share your `reddit_config.json` file

## File Structure

```
project/
├── Reddit_API.py          # Main script
├── sub_list.csv           # List of subreddits to scrape
├── reddit_config.json     # Credentials (auto-generated)
├── {subreddit}_img_list.csv  # Results for each subreddit
├── new_img.csv            # Latest scraping results
└── .gitignore             # Prevents committing sensitive files
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
