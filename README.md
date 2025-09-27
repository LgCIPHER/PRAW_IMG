# Reddit Image Scraper

An asynchronous Python tool for scraping image URLs from Reddit subreddits with validation, duplicate removal, and CSV management.

## Features

- Asynchronous for performance
- Object-oriented structure
- Progress visualization
- Image format filters (JPG, PNG, JPEG)
- Duplicate and deleted image detection
- Domain-based filtering
- Excel-compatible CSV output (UTF-8-sig)
- Secure credential storage

## Requirements

Install with pip:

```bash
pip install asyncpraw aiohttp opencv-python numpy tqdm aiofiles
```

### Reddit API Setup

1. Go to [Reddit App Preferences](https://www.reddit.com/prefs/apps)
2. Create a **script** app
3. Save `client_id` and `client_secret`

## First Run

1. Create `sub_list.csv` with subreddit names:

```
Pixiv
Art
DigitalPainting
```

2. Run `python main.py` and enter:

   - Client ID, Client Secret, User Agent, Username, Password

3. Config saved in `reddit_config.json`

## Usage

- **Scrape New Images**: Collect posts, validate, filter, and save to `{subreddit}_img_list.csv` and `new_img.csv`
- **Clean Existing CSVs**: Validate and remove invalid or duplicate links
- **Combined**: Scrape + clean in sequence
- **Clean Specific Subreddit**: Clean one subreddit’s CSV

### Output

- `{subreddit}_img_list.csv` – Subreddit results
- `new_img.csv` – Latest run
- `reddit_config.json` – Config and credentials
- `{subreddit}_errors.log` – Failed validations
- `reddit_scraper.log` – General logs

## Project Structure

```
project/
├── main.py                  # Main script
├── sub_list.csv             # Subreddits list
├── reddit_config.json       # Config file
├── reddit_scraper/          # Core package
│   ├── auth.py              # Authentication
│   ├── config.py            # Config management
│   ├── data_manager.py      # Data operations
│   ├── image_processor.py   # Image validation
│   ├── cleaner.py           # CSV cleaning
│   └── scraper.py           # Scraping logic
└── .gitignore               # Prevents exposing credentials
```

## Key Settings

- `post_limit`: posts per subreddit (default 100)
- `supported_formats`: [jpg, png, jpeg]
- `excluded_domains`: e.g., ["i.imgur.com"]
- `batch_size`: parallel image checks (default 10)
- `min_image_size`: minimum image size (10KB)
- `retry_attempts`: failed request retries (default 3)
- `rate_limit_delay`: delay between requests (default 1s)

## Security

- Credentials stored locally in `reddit_config.json`
- Protected with `.gitignore`
- Never share your config file

## Excel Integration

- CSVs use UTF-8-sig encoding
- One URL per row, easy to filter and import into Excel

## Troubleshooting

- **API errors**: Check credentials
- **Rate limits**: Increase `rate_limit_delay`
- **Image errors**: Deleted or inaccessible (auto-retried)

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
