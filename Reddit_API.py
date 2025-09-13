from praw import Reddit
import os.path
from pathlib import Path
import json
import requests
import cv2 as cv
import numpy as np

"""Start Global variables"""
dir_path = os.path.dirname(os.path.realpath(__file__))  # Path of this file

past_result = []
# already_done = []
last_sub_url_list = []
new_img_lst = []

# lst_img_name = "Nilou_Mains_img_list.csv"
lst_img_name = ""
lst_img_dir = ""
# lst_img_dir = os.path.join(dir_path, lst_img_name)

lst_sub_name = "sub_list.csv"
lst_sub_dir = os.path.join(dir_path, lst_sub_name)

new_lst_img_name = "new_img.csv"
new_lst_img_dir = os.path.join(dir_path, new_lst_img_name)
"""End Global variables"""


def create_folder(folder_path):  # Create directory if it doesn't exist to save images
    CHECK_FOLDER = os.path.isdir(folder_path)
    # If folder doesn't exist, then create it.
    if not CHECK_FOLDER:
        os.makedirs(folder_path)


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


def read_token(dir_path):
    """Read credentials from JSON config file"""
    config_path = os.path.join(dir_path, "reddit_config.json")
    
    try:
        # Try to read existing config file
        with open(config_path, 'r') as config_file:
            config_data = json.load(config_file)
            print("✓ Loaded credentials from reddit_config.json")
            return config_data["reddit_credentials"]
            
    except FileNotFoundError:
        print("reddit_config.json not found. Creating new config...")
        
        # Get credentials from user
        creds = create_token()
        
        # Create full config structure with your current settings
        config_data = {
            "reddit_credentials": creds,
            "scraping_settings": {
                "post_limit": 50,
                "default_subreddit": "Pixiv",
                "supported_formats": ["jpg", "png"],
                "exclude_domains": ["i.imgur.com"]
            }
        }
        
        # Save to JSON file
        try:
            with open(config_path, 'w') as config_file:
                json.dump(config_data, config_file, indent=4)
            print(f"✓ Config file created: {config_path}")
            print("✓ Your credentials are now saved securely!")
            return creds
        except Exception as e:
            print(f"Error creating config file: {e}")
            return creds
    
    except json.JSONDecodeError:
        print("Error: reddit_config.json file is corrupted")
        print("Please delete it and run the script again")
        return None
    except Exception as e:
        print(f"Error reading config file: {e}")
        return None


def name_progress(url_str, sub_path, sub):
    url_name_lst = url_str.split("/")
    pic_name = url_name_lst[3]
    pic_name_lst = pic_name.split(".")
    pic_id = pic_name_lst[0]
    pic_type = pic_name_lst[1]

    img_name = f"{sub_path}{sub}-{pic_id}.{pic_type}"
    img_path = os.path.join(sub_path, img_name)


def html_to_img(url_str, resize=False):
    # Getting image from HTML page
    resp = requests.get(url_str, stream=True).raw
    image = np.asarray(bytearray(resp.read()), dtype="uint8")
    image = cv.imdecode(image, cv.IMREAD_COLOR)

    if resize == True:
        # Could do transforms on images like resize!
        image = cv.resize(image, (352, 627))

    return image


def check_deleted_img(url_str):
    deleted_flag = False

    img = html_to_img(url_str)
    [h, w] = [img.shape[0], img.shape[1]]

    if [h, w] != [60, 130]:
        pass
    else:
        deleted_flag = True

    return deleted_flag


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


def past_list(lst_img_dir):
    past_list = []

    with open(lst_img_dir, mode="r", encoding="utf-8-sig") as f_past_result:
        for line in f_past_result:
            url = line.strip()
            past_list.append(url)

    return past_list


def check_available(url_str, already_done):
    exist_flag = False

    for url_done in already_done:
        if url_str == url_done:
            exist_flag = True

    return exist_flag


def Reddit_API():
    # Higher number = Longer runtime
    POST_SEARCH_AMOUNT = 20
    
    sub = "Pixiv"  # Search for images in this Subreddit

    creds = read_token(dir_path)
    if not creds:
        print("Failed to load credentials. Exiting...")
        return

    reddit = Reddit(
        client_id=creds["client_id"],
        client_secret=creds["client_secret"],
        user_agent=creds["user_agent"],
        username=creds["username"],
        password=creds["password"],
    )

    with open(lst_sub_dir, mode="r", encoding="utf-8-sig") as f_source:
        for line in f_source:
            sub = line.strip()
            subreddit = reddit.subreddit(sub)

            count = 0
            already_done = []

            lst_img_name = f"{sub}_img_list.csv"
            lst_img_dir = os.path.join(dir_path, lst_img_name)

            past_result = past_list(lst_img_dir)
            for url in past_result:
                already_done.append(url)

            print(f"\nStarting {sub} subreddit!\n")

            # Searching for Hot post
            # for submission in subreddit.hot(limit=POST_SEARCH_AMOUNT):
            for submission in subreddit.top(
                limit=POST_SEARCH_AMOUNT
            ):  # Searching for Top (of all time) post
                # Get URL from Reddit post
                url_str = str(submission.url.lower())
                # print(f"Test: {url_str}\n")

                # Only getting Images
                if "jpg" in url_str or "png" in url_str:
                    exist_flag = False

                    exist_flag = check_available(url_str, already_done)

                    if exist_flag == False:
                        if url_str not in already_done:
                            domain_name = submission.domain

                            if domain_name != "i.imgur.com":
                                try:
                                    deleted_flag = False

                                    deleted_flag = check_deleted_img(url_str)

                                    if not deleted_flag:
                                        ignore_flag = False

                                        # ignore_flag = compare_img(url_str, last_sub_url_list)

                                        if not ignore_flag:
                                            new_img_lst.append(url_str)
                                            already_done.append(url_str)
                                            count += 1
                                            print(
                                                f"ID-{count}-Add--successfully--{url_str}"
                                            )
                                    else:
                                        print("Deleted img")

                                except Exception as e:
                                    print(f"Image failed. {url_str}")
                                    print(e)

                            else:
                                print("Can't deal with Imgur link yet!")
                    else:
                        print(f"--Pass--{url_str}")

            for url_done in already_done:
                last_sub_url_list.append(url_done)

            print(f"{count} new picture has been added!\n")

            print(f"Finish scraping {sub}!")

            print(f"Start writing into '{new_lst_img_name}' file ")

            with open(new_lst_img_dir, mode="w", encoding="utf-8-sig") as f_result:
                for url_new in new_img_lst:
                    img_path_str = str(url_new) + "\n"
                    f_result.write(img_path_str)

            print(f"Done writing into {new_lst_img_name}!")

            print(f"Start writing into '{lst_img_name}' file")

            with open(lst_img_dir, mode="w", encoding="utf-8-sig") as f_result:
                for url_done in already_done:
                    img_path_str = str(url_done) + "\n"
                    f_result.write(img_path_str)

            print(f"Done writing into {lst_img_name}!")

    print("Finish running!")


def scan_csv():
    # count = 0

    already_done = []

    with open(lst_sub_dir, mode="r", encoding="utf-8-sig") as f_source:
        for line in f_source:
            sub = line.strip()
            lst_img_name = f"{sub}_img_list.csv"
            lst_img_dir = os.path.join(dir_path, lst_img_name)

            id = 1
            count = 0

            print(f"\nStart scanning '{lst_img_name}' file!")

            already_done = []

            past_result = past_list(lst_img_dir)
            for url in past_result:
                already_done.append(url)

            for line in already_done:
                url_str = line.strip()
                try:
                    deleted_flag = False

                    deleted_flag = check_deleted_img(url_str)

                    if not deleted_flag:
                        print(f"ID-{id}-Keep--{url_str}")
                        id += 1
                        # ignore_flag = False

                        # ignore_flag = compare_img(url_str, already_done)

                        # if ignore_flag:
                        #     already_done.remove(line)
                        #     count += 1
                        #     print(f"Remove--{url_str}")
                    else:
                        already_done.remove(line)
                        count += 1
                        print(f"Remove--{url_str}")
                except Exception as e:
                    print(f"Image failed. {url_str}")
                    print(e)

            print(f"Finish scanning {lst_img_name}!")

            print(f"{count} picture has been removed!\n")

            print("Start writing into csv file")

            with open(lst_img_dir, mode="w", encoding="utf-8-sig") as f_result:
                for url_done in already_done:
                    img_path_str = str(url_done) + "\n"
                    f_result.write(img_path_str)

            print("Finish writing into csv file")

    print("Finish running!")


def main():
    Reddit_API()
    # scan_csv()


if __name__ == "__main__":
    main()
