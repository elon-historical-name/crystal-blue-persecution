import asyncio
import logging
import os
import sys
from io import BytesIO
from typing import Optional

import dotenv
from PIL import Image
from atproto import AsyncClient
from atproto.exceptions import FirehoseError
from reactivex.abc import DisposableBase
from selenium.common import WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver

from bsky_account_observer import BskyPostObserver, ObservedPost
from bsky_api_extensions import fetch_handle
from event_loop import event_loop, async_io_scheduler
from selenium_webdriver_setup import setup_selenium
from telegram_publisher import publish_to_tg_channel

observation_subscription: Optional[DisposableBase] = None


async def setup_publisher_client() -> Optional[AsyncClient]:
    if "PUBLISHER_LOGIN" in os.environ.keys() and "PUBLISHER_PASSWORD" in os.environ.keys():
        client = AsyncClient()
        try:
            await client.login(
                login=os.environ.get("PUBLISHER_LOGIN"),
                password=os.environ.get("PUBLISHER_PASSWORD")
            )
        except Exception as e:
            logging.error(e)
            return None
        return client
    return None


async def take_screenshot(post: ObservedPost, retry: int = 0, retry_limit: int = 5) -> Optional[str]:
    screenshots_dir = os.environ.get("SCREENSHOT_DIRECTORY")
    screenshot_path = f"{screenshots_dir}/{post.commit_repo.replace(':', '-')}_{post.content_identifier}.png"
    browser: Optional[WebDriver] = None
    try:
        browser = await setup_selenium()
        if browser is None:
            return None
        browser.get(post.http_url_to_post)
        await asyncio.sleep(8.5)
        logging.info(f"Storing Screenshot of {post.http_url_to_post}")
        browser.save_screenshot(
            screenshot_path
        )
    except WebDriverException as e:
        if browser is not None:
            browser.quit()
        if retry == retry_limit:
            logging.error(
                f"Unrecoverable exception occurred on attempting to screenshot {post.http_url_to_post}; "
                f"attempt reconnect.",
                e
            )
            return await take_screenshot(post, retry=retry + 1, retry_limit=retry_limit)
        if retry > retry_limit:
            if browser is not None:
                browser.quit()
            logging.error(
                f"Unrecoverable exception occurred on attempting to screenshot {post.http_url_to_post}",
                e
            )
            raise e
        return await take_screenshot(post, retry=retry + 1, retry_limit=retry_limit)
    finally:
        if browser is not None:
            browser.quit()
    return screenshot_path


async def repost_with_screenshot(posts: [ObservedPost]):
    logging.info(f"Processing {len(posts)} post(s)")
    publisher_client = await setup_publisher_client()
    for post in posts:
        screenshot_path = await take_screenshot(post)
        url = post.http_url_to_post
        if screenshot_path is None:
            logging.error(f"Unable to take screenshot of {url}")
            continue
        handle = await fetch_handle(post.commit_repo)
        await publish_to_tg_channel(post=post, screenshot_path=screenshot_path, user_handle=handle)
        if publisher_client is None:
            logging.info(f"Publishing disabled")
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
        if publisher_client is None:
            continue
        handle = handle if handle is not None else post.commit_repo
        while retries < retry_limit:
            try:
                logging.info(
                    f"Re-publishing {url} from {handle} with {os.environ.get('PUBLISHER_LOGIN')}"
                    f"\n\tScreenshot size: {len(raw_image_bytes)/1000/1000} MB"
                )
                await publisher_client.send_image(
                    text=url,
                    image=raw_image_bytes,
                    image_alt=url
                )
                break
            except Exception as e:
                retries += 1
                if retries == retry_limit:
                    logging.error(
                        f"Unrecoverable exception occurred on attempting to repost {url}",
                        e
                    )
                    raise e
                await asyncio.sleep(10)


async def main():
    logging.info(
        f"Configuring."
        f"\n\tObserver: {os.environ.get('OBSERVER_LOGIN')} "
        f"\n\tPublisher: {os.environ.get('PUBLISHER_LOGIN')}"
    )
    global observation_subscription

    asyncio.set_event_loop(loop=event_loop)

    observer = BskyPostObserver()
    observation_subscription = observer.posts(
        schedule_s=30.0,
        capacity=25  # This is the maximum supported by ATProto/BlueSky
    ).subscribe(
        on_next=lambda posts: event_loop.create_task(repost_with_screenshot(posts)),
        scheduler=async_io_scheduler
    )
    while True:
        try:
            logging.info("Starting observation")
            await observer.start()
        except FirehoseError as e:
            logging.info("Observation failed/cancelled; retrying")
            await observer.stop()
            logging.warning("FirehoseError occurred; Restarting observation", e)


if __name__ == '__main__':
    dotenv.load_dotenv(".test.env")
    log_format = '%(asctime)s %(levelname)-8s %(message)s' \
        if os.environ.get("IS_DOCKERIZED") != "1" \
        else '%(levelname)-8s %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stdout
    )
    event_loop.run_until_complete(main())
