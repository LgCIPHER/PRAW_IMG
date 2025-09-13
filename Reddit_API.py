from praw import Reddit
import os.path
from pathlib import Path
import json
import requests
import cv2 as cv
import numpy as np
import time
from functools import wraps
import logging
import requests.adapters
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

"""Start Global variables"""
dir_path = os.path.dirname(os.path.realpath(__file__))  # Path of this file

lst_sub_name = "sub_list.csv"
lst_sub_dir = os.path.join(dir_path, lst_sub_name)

new_lst_img_name = "new_img.csv"
new_lst_img_dir = os.path.join(dir_path, new_lst_img_name)
"""End Global variables"""

def setup_logging(config):
    """Setup logging configuration"""
    log_level = config.get("output_settings", {}).get("log_level", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('reddit_scraper.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def create_token():
    """Create credentials by getting input from user"""
    creds = {}
    print("Setting up Reddit API credentials...")
    print("(You can find these at: https://www.reddit.com/prefs/apps)")
    
    creds["client_id"] = input("Enter your Reddit client_id: ")
    creds["client_secret"] = input("Enter your Reddit client_secret: ")
    creds["user_agent"] = input("Enter your user_agent (e.g., MyBot/1.0): ")
    creds["username"] = input("Enter your Reddit username: ")
    creds["password"] = input("Enter your Reddit password: ")
    
    return creds

def load_config(dir_path):
    """Load complete configuration including credentials and settings"""
    config_path = os.path.join(dir_path, "reddit_config.json")
    
    try:
        with open(config_path, 'r') as config_file:
            config_data = json.load(config_file)
            print("✓ Loaded configuration from reddit_config.json")
            return config_data
    except FileNotFoundError:
        return create_default_config(config_path)

def create_default_config(config_path):
    """Create default configuration with user input"""
    print("reddit_config.json not found. Creating new config...")
    
    # Get credentials from user (keep your existing create_token logic)
    creds = create_token()
    
    # Create enhanced config structure
    config_data = {
        "reddit_credentials": creds,
        "scraping_settings": {
            "post_limit": 20,
            "search_type": "top",
            "supported_formats": ["jpg", "png", "jpeg"],
            "excluded_domains": ["i.imgur.com"],
            "enable_duplicate_detection": True,
            "enable_deleted_image_check": True
        },
        "performance_settings": {
            "request_timeout_seconds": 30,
            "retry_attempts": 3,
            "rate_limit_delay": 1.0
        },
        "output_settings": {
            "csv_encoding": "utf-8-sig",
            "summary_filename": "new_img.csv"
        }
    }
    
    # Save configuration
    with open(config_path, 'w') as config_file:
        json.dump(config_data, config_file, indent=4)
    
    print(f"✓ Configuration created: {config_path}")
    return config_data

def create_session_with_retries():
    """Create requests session with connection pooling and retries"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def html_to_img(url_str, session=None, resize=False):
    # Getting image from HTML page
    if session is None:
        session = requests
    
    resp = session.get(url_str, stream=True, timeout=30).raw
    image = np.asarray(bytearray(resp.read()), dtype="uint8")
    image = cv.imdecode(image, cv.IMREAD_COLOR)

    if resize == True:
        # Could do transforms on images like resize!
        image = cv.resize(image, (352, 627))

    return image

def create_reddit_client(credentials):
    """Create and test Reddit client connection"""
    try:
        reddit = Reddit(
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            user_agent=credentials["user_agent"],
            username=credentials["username"],
            password=credentials["password"],
        )
        # Test the connection by getting user info
        user = reddit.user.me()
        print(f"✓ Connected to Reddit as: {user.name}")
        return reddit
    except Exception as e:
        print(f"Failed to connect to Reddit API: {e}")
        print("Please check your credentials in reddit_config.json")
        return reddit

def read_subreddit_list(file_path):
    """Read and validate subreddit names from CSV"""
    subreddits = []
    
    if not os.path.exists(file_path):
        print(f"Subreddit list file not found: {file_path}")
        print("Please create a 'sub_list.csv' file with one subreddit name per line")
        return subreddits
    
    try:
        with open(file_path, mode="r", encoding="utf-8-sig") as f:
            for line_num, line in enumerate(f, 1):
                sub = line.strip()
                if sub and not sub.startswith('#'):
                    # Basic validation for subreddit names
                    if len(sub) <= 50 and sub.replace('_', '').replace('-', '').isalnum():
                        subreddits.append(sub)
                    else:
                        print(f"Warning: Invalid subreddit name on line {line_num}: {sub}")
        print(f"✓ Found {len(subreddits)} subreddits to process")
    except Exception as e:
        print(f"Error reading subreddit list: {e}")
    
    return subreddits

def process_subreddit(reddit, subreddit_name, config, dir_path):
    """Process a single subreddit and return new images found"""
    print(f"\n--- Processing r/{subreddit_name} ---")

    # Create session for this subreddit
    session = create_session_with_retries()

    # Get configuration values
    post_limit = config["scraping_settings"]["post_limit"]
    supported_formats = config["scraping_settings"]["supported_formats"]
    excluded_domains = config["scraping_settings"]["excluded_domains"]
    
    # Initialize lists
    new_images = []
    count = 0
    
    # Set up file paths
    lst_img_name = f"{subreddit_name}_img_list.csv"
    lst_img_dir = os.path.join(dir_path, lst_img_name)
    
    # Load existing URLs
    past_result = past_list(lst_img_dir)
    already_done_set = set(past_result)
    
    try:
        subreddit = reddit.subreddit(subreddit_name)
        submissions = list(subreddit.top(limit=post_limit))
        
        # Search for posts
        for submission in tqdm(submissions, desc=f"Processing r/{subreddit_name}"):
            url_str = str(submission.url.lower())
            
            # Check if it's an image with supported format
            if any(f".{fmt}" in url_str for fmt in supported_formats):
                
                # Check if we already have this URL
                if url_str not in already_done_set:
                    domain_name = submission.domain
                    
                    # Skip excluded domains
                    if domain_name not in excluded_domains:
                        try:
                            # Check if image is deleted
                            deleted_flag = check_deleted_img(url_str, session)
                            
                            if not deleted_flag:
                                # Add to our lists
                                new_images.append(url_str)
                                already_done_set.add(url_str)
                                count += 1
                                print(f"ID-{count}-Added: {url_str}")
                            else:
                                print(f"Skipped deleted image: {url_str}")
                                
                        except Exception as e:
                            print(f"Error processing {url_str}: {e}")
                    else:
                        print(f"Skipped excluded domain: {domain_name}")
                else:
                    print(f"Already exists: {url_str}")
        
        # Save the complete list for this subreddit
        save_urls_to_csv(already_done_set, lst_img_dir, f"{subreddit_name} images")
        
        print(f"✓ Found {count} new images in r/{subreddit_name}")
        return new_images, already_done_set
        
    except Exception as e:
        print(f"Error accessing r/{subreddit_name}: {e}")
        return [], already_done_set

def rate_limit(calls_per_second=1):
    """Decorator to rate limit function calls"""
    min_interval = 1.0 / calls_per_second
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            ret = func(*args, **kwargs)
            last_called[0] = time.time()
            return ret
        return wrapper
    return decorator

def is_valid_image_url(url, supported_formats):
    """Check if URL points to a supported image format"""
    try:
        url_lower = url.lower()
        return any(f".{fmt}" in url_lower for fmt in supported_formats)
    except Exception:
        return False

@rate_limit(calls_per_second=2)  # Max 2 requests per second
def check_deleted_img(url_str, session=None):
    deleted_flag = False

    img = html_to_img(url_str, session)
    [h, w] = [img.shape[0], img.shape[1]]

    if [h, w] != [60, 130]:
        pass
    else:
        deleted_flag = True

    return deleted_flag

def safe_check_deleted_img(url_str, max_retries=3):
    """Safely check if image is deleted with retry logic"""
    for attempt in range(max_retries):
        try:
            return check_deleted_img(url_str)
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                print(f"Failed to check image after {max_retries} attempts: {url_str}")
                return True  # Treat as deleted if we can't check
            time.sleep(1)  # Brief delay before retry
        except Exception as e:
            print(f"Unexpected error checking image {url_str}: {e}")
            return True
    return True

def compare_img(url_str, url_list):
    ignore_flag = False

    img_1 = html_to_img(url_str)
    [h_1, w_1] = [img_1.shape[0], img_1.shape[1]]

    print(f"Start comparing--{url_str}")

    for url_done in url_list:
        img_2 = html_to_img(url_done)
        [h_2, w_2] = [img_2.shape[0], img_2.shape[1]]

        if [h_1, w_1] == [h_2, w_2]:
            print(f"--Comparing with--{url_done}")
            difference = cv.subtract(img_1, img_2)
            b, g, r = cv.split(difference)
            total_difference = (
                cv.countNonZero(b) + cv.countNonZero(g) + cv.countNonZero(r)
            )
            if total_difference == 0:
                ignore_flag = True

    return ignore_flag

def save_urls_to_csv(urls, file_path, description="URLs"):
    """Save URLs to CSV file with error handling"""
    if isinstance(urls, set):
        urls = list(urls)
    
    if not urls:
        print(f"No {description.lower()} to save")
        return True
    
    try:
        with open(file_path, mode="w", encoding="utf-8-sig") as f:
            for url in urls:
                f.write(f"{url}\n")
        print(f"✓ Saved {len(urls)} {description.lower()} to {os.path.basename(file_path)}")
        return True
    except Exception as e:
        print(f"Error saving {description.lower()} to {file_path}: {e}")
        return False

def past_list(lst_img_dir):
    """Read URLs from existing CSV file with error handling"""
    past_urls = []
    
    # Check if file exists first
    if not os.path.exists(lst_img_dir):
        print(f"No existing file found: {lst_img_dir}")
        return past_urls
    
    try:
        with open(lst_img_dir, mode="r", encoding="utf-8-sig") as f_past_result:
            for line_num, line in enumerate(f_past_result, 1):
                url = line.strip()
                if url and not url.startswith('#'):  # Skip empty lines and comments
                    past_urls.append(url)
        print(f"✓ Loaded {len(past_urls)} existing URLs from {os.path.basename(lst_img_dir)}")
    except FileNotFoundError:
        print(f"File not found: {lst_img_dir}")
    except UnicodeDecodeError as e:
        print(f"Encoding error reading {lst_img_dir}: {e}")
    except Exception as e:
        print(f"Error reading {lst_img_dir}: {e}")
    
    return past_urls

def Reddit_API():
    """Main scraping function"""
    # Load configuration
    config = load_config(dir_path)  # Use your updated config function
    if not config:
        print("Failed to load configuration. Exiting...")
        return

    # Setup logging after config is loaded
    logger = setup_logging(config)
    logger.info("Starting Reddit Image Scraper...")

    # Create Reddit client
    reddit = create_reddit_client(config["reddit_credentials"])
    if not reddit:
        return
    
    # Get list of subreddits to process
    subreddits_to_process = read_subreddit_list(lst_sub_dir)
    if not subreddits_to_process:
        print("No valid subreddits found. Exiting...")
        return
    
    # Process all subreddits
    all_new_images = []
    total_processed = 0
    
    for subreddit_name in subreddits_to_process:
        new_images, all_images = process_subreddit(reddit, subreddit_name, config, dir_path)
        all_new_images.extend(new_images)
        total_processed += len(new_images)
    
    # Save summary file with all new images
    if all_new_images:
        summary_filename = config["output_settings"]["summary_filename"]
        summary_path = os.path.join(dir_path, summary_filename)
        save_urls_to_csv(all_new_images, summary_path, "new images summary")
    
    # Final summary
    print(f"\n{'='*50}")
    print(f"✓ Scraping Complete!")
    print(f"✓ Processed {len(subreddits_to_process)} subreddits")
    print(f"✓ Found {total_processed} new images total")
    if all_new_images:
        print(f"✓ Summary saved to: {summary_filename}")
    print(f"{'='*50}")

def scan_csv():
    """Scan and clean existing CSV files - restructured"""
    print("Starting CSV cleanup scan...")
    
    # Get list of subreddits to scan
    subreddits_to_scan = read_subreddit_list(lst_sub_dir)
    if not subreddits_to_scan:
        print("No subreddits found to scan")
        return
    
    total_removed = 0
    
    for sub in subreddits_to_scan:
        removed_count = scan_subreddit_csv(sub)
        total_removed += removed_count
    
    print(f"\n✓ CSV cleanup complete! Removed {total_removed} broken URLs total")

def scan_subreddit_csv(subreddit_name):
    """Scan and clean a single subreddit's CSV file"""
    lst_img_name = f"{subreddit_name}_img_list.csv"
    lst_img_dir = os.path.join(dir_path, lst_img_name)
    
    print(f"\n--- Scanning {lst_img_name} ---")
    
    # Load existing URLs
    already_done_set = past_list(lst_img_dir)
    if not already_done_set:
        print(f"No URLs found in {lst_img_name}")
        return 0
    
    valid_urls = []
    removed_count = 0
    
    for i, url_str in enumerate(already_done_set, 1):
        try:
            deleted_flag = check_deleted_img(url_str)
            
            if not deleted_flag:
                valid_urls.append(url_str)
                print(f"ID-{i}: ✓ Keep - {url_str}")
            else:
                removed_count += 1
                print(f"ID-{i}: ✗ Remove - {url_str}")
                
        except Exception as e:
            removed_count += 1
            print(f"ID-{i}: ✗ Error checking - {url_str}: {e}")
    
    # Save cleaned list
    save_urls_to_csv(valid_urls, lst_img_dir, f"cleaned {subreddit_name} images")
    
    print(f"✓ {subreddit_name}: Kept {len(valid_urls)}, Removed {removed_count}")
    return removed_count

def main():
    """Main entry point with user options"""
    print("Reddit Image Scraper")
    print("1. Scrape new images")
    print("2. Clean existing CSV files") 
    print("3. Both (scrape then clean)")
    
    try:
        choice = input("Enter your choice (1-3): ").strip()
        
        if choice == "1":
            Reddit_API()
        elif choice == "2":
            scan_csv()
        elif choice == "3":
            Reddit_API()
            print("\nNow cleaning CSV files...")
            scan_csv()
        else:
            print("Invalid choice. Running scraper...")
            Reddit_API()
            
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
