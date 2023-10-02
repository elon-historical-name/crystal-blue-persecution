import multiprocessing
import os
from io import BytesIO
from time import sleep
from typing import Optional

import dotenv
from PIL import Image
from atproto import AsyncClient, Client
from atproto.xrpc_client.models.app.bsky.feed.defs import PostView
from reactivex import operators as ops
from reactivex.abc import DisposableBase
from reactivex.scheduler import ThreadPoolScheduler
from selenium.common import WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver

from accounts import get_accounts
from bsky_account_observer import BskyPostObserver
from selenium_webdriver_setup import setup_selenium

browser: Optional[WebDriver] = None
publisher_client: Optional[AsyncClient] = None
observation_client: Optional[AsyncClient] = None
observation_subscription: Optional[DisposableBase] = None


def setup_observation_client() -> Client:
    client = Client()
    client.login(
        login=os.environ.get("OBSERVER_LOGIN"),
        password=os.environ.get("OBSERVER_PASSWORD")
    )
    return client


def setup_publisher_client() -> Optional[Client]:
    if "PUBLISHER_LOGIN" in os.environ.keys() and "PUBLISHER_PASSWORD" in os.environ.keys():
        client = Client()
        client.login(
            login=os.environ.get("PUBLISHER_LOGIN"),
            password=os.environ.get("PUBLISHER_PASSWORD")
        )
        return client
    return None


def screenshot(post: PostView, retry: int = 0, retry_limit: int = 5) -> Optional[str]:
    global browser
    if browser is None:
        browser = setup_selenium()
    if browser is None:
        return None
    model_name = "app.bsky.feed.post"
    screenshots_dir = os.environ.get("SCREENSHOT_DIRECTORY")
    content_identifier = post.uri.replace(f"at://{post.author.did}/{model_name}/", "")
    screenshot_path = f"{screenshots_dir}/{post.author.handle}_{content_identifier}.png"
    url = f"https://bsky.app/profile/{post.author.handle}/post/{content_identifier}"
    try:
        browser.get(url)
        sleep(5)
        print(f"Storing Screenshot of {post.uri} from {post.author.handle}")
        browser.save_screenshot(
            screenshot_path
        )
    except WebDriverException as e:
        if retry >= retry_limit:
            raise e
        browser = None
        return screenshot(post, retry=retry+1, retry_limit=retry_limit)
    return screenshot_path


def repost_with_screenshot(posts: [str]):
    global publisher_client
    global observation_client
    global browser
    if observation_client is None:
        observation_client = setup_observation_client()
    if observation_client is None:
        print("Observation is disabled")
        return
    search_result = observation_client.app.bsky.feed.get_posts(
        params={
            "uris": posts
        }
    )
    for post in search_result.posts:
        if post.author.did not in (get_accounts()).values():
            continue
        if publisher_client is None:
            publisher_client = setup_publisher_client()

        model_name = "app.bsky.feed.post"
        content_identifier = post.uri.replace(f"at://{post.author.did}/{model_name}/", "")
        screenshot_path = screenshot(post)
        url = f"https://bsky.app/profile/{post.author.handle}/post/{content_identifier}"
        if screenshot_path is None:
            print(f"Unable to take screenshot of {url}")
            continue
        if publisher_client is None:
            continue
        image_bytes = BytesIO()
        # Convert shots to JPEG to compress them - BlueSky limits uploads to 1MB
        Image.open(screenshot_path).convert("RGB").save(
            image_bytes,
            format="jpeg",
            quality=70
        )
        retries = 0
        retry_limit = 10
        raw_image_bytes = image_bytes.getvalue()
        while retries < retry_limit:
            try:
                print(
                    f"Reposting using {os.environ.get('PUBLISHER_LOGIN')}"
                    f"\n\tScreenshot size: {len(raw_image_bytes)/1000/1000} MB"
                )
                publisher_client.send_image(
                    text=url,
                    image=raw_image_bytes,
                    image_alt=url
                )
                break
            except Exception as e:
                retries += 1
                if retries == retry_limit:
                    raise e
                sleep(10)


def main():
    print(
        f"Configuring."
        f"\n\tObserver: {os.environ.get('OBSERVER_LOGIN')} "
        f"\n\tPublisher: {os.environ.get('PUBLISHER_LOGIN')}"
    )
    global observation_subscription

    optimal_thread_count = multiprocessing.cpu_count()
    pool_scheduler = ThreadPoolScheduler(optimal_thread_count)

    observer = BskyPostObserver()
    observation_subscription = observer.posts(
        schedule_s=30.0,
        capacity=25  # This is the maximum supported by ATProto/BlueSky
    ).pipe(
        ops.subscribe_on(pool_scheduler)
    ).subscribe(
        on_next=lambda posts: repost_with_screenshot(posts=posts),
        scheduler=pool_scheduler
    )
    print("Starting observation")
    observer.start()


if __name__ == '__main__':
    dotenv.load_dotenv()
    main()
