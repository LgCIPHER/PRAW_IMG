# Reddit Image Scraper

A Python script that downloads image URLs from specified Reddit subreddits and saves them to CSV files for further analysis or processing.

## Features

- Scrapes image URLs from multiple subreddits
- Filters for specific image formats (JPG, PNG)
- Removes deleted images automatically
- Prevents duplicate image collection
- Exports results to CSV files (Excel-compatible)
- Secure credential management via JSON config

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

The script creates a `reddit_config.json` file:

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
    "post_limit": 50,
    "default_subreddit": "Pixiv",
    "supported_formats": ["jpg", "png"]
  }
}
```

## Usage

### Basic Usage

```bash
python Reddit_API.py
```

### What the Script Does

1. Reads subreddit names from `sub_list.csv`
2. For each subreddit, scrapes the top posts for image URLs
3. Validates images (removes deleted/broken links)
4. Filters out duplicates within the same subreddit
5. Saves results to individual CSV files: `{subreddit}_img_list.csv`
6. Creates a summary file: `new_img.csv` with newly found images

### Output Files

- `{subreddit}_img_list.csv` - Complete list of image URLs for each subreddit
- `new_img.csv` - URLs of images found in the current run
- `reddit_config.json` - Secure credential storage (auto-generated)

## Functions

### Main Functions

- `Reddit_API()` - Main scraping function that processes all subreddits
- `scan_csv()` - Validates existing CSV files and removes broken links

### Utility Functions

- `create_token()` - Handles credential input during first setup
- `read_token()` - Loads credentials from JSON config file
- `check_deleted_img()` - Validates if image URLs are still accessible
- `compare_img()` - Compares images to detect duplicates
- `past_list()` - Loads previously scraped URLs from CSV files

## Settings

You can modify these variables in the script:

- `POST_SEARCH_AMOUNT` - Number of posts to check per subreddit (default: 200)
- Image formats - Currently supports JPG and PNG
- Domain filtering - Currently excludes i.imgur.com links

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

### Common Issues

- **"Failed to load credentials"** - Run the script to create initial config file
- **"Image failed"** - Network issues or broken image links (automatically skipped)
- **Rate limiting** - Reddit may temporarily limit requests if too frequent

### Maintenance

- Run `scan_csv()` function periodically to clean up broken links
- Check CSV files for any URLs that may have become inaccessible

## Contributing

Feel free to submit issues or pull requests to improve the functionality.
