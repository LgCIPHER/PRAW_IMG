# Reddit Image Scraper

An asynchronous Python tool for scraping image URLs from Reddit subreddits with validation, duplicate removal, and CSV management.

## Quick Start

```bash
# 1. Install dependencies
pip install asyncpraw aiohttp opencv-python numpy tqdm aiofiles

# 2. Create sub_list.csv with subreddit names
Pixiv
Art
DigitalPainting

# 3. Run the script
python main.py
```

On first run, enter your Reddit credentials. Config will be saved in `reddit_config.json`.

### Example `sub_list.csv`

```
Pixiv
Art
DigitalPainting
ImaginaryLandscapes
AnimeSketch
```

### Example Output (`new_img.csv`)

```
subreddit,url,width,height,size_bytes
Pixiv,https://i.redd.it/example1.jpg,1200,1600,245678
Art,https://preview.redd.it/example2.png,800,600,134567
DigitalPainting,https://i.redd.it/example3.jpeg,1920,1080,456789
```

### Example Command-Line Interaction

```
Select an operation:
1. Scrape New Images
2. Clean Existing CSVs
3. Combined (Scrape + Clean)
4. Clean Specific Subreddit
Enter choice [1-4]: 1
```

### Workflow Diagram

```mermaid
graph TD;
    A[Start] --> B[Read sub_list.csv];
    B --> C[Authenticate with Reddit API];
    C --> D[Fetch subreddit posts];
    D --> E[Validate images];
    E --> F[Filter formats & domains];
    F --> G[Detect duplicates & deleted];
    G --> H[Save results to CSV];
    H --> I[Generate logs];
    I --> J[Cleanup operation (optional)];
    J --> K[End];
```

---

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

- **asyncpraw** – Reddit API wrapper
- **aiohttp** – Async HTTP requests
- **opencv-python** – Image processing
- **numpy** – Image data arrays
- **tqdm** – Progress bars
- **aiofiles** – Async file operations

## Usage

- **Scrape New Images** – Collect, validate, filter, save results
- **Clean Existing CSVs** – Validate and remove invalid/duplicate links
- **Combined** – Scrape + clean in sequence
- **Clean Specific Subreddit** – Clean one subreddit’s CSV

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
