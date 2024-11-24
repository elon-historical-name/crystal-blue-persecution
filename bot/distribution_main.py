import asyncio
import logging
import os
from typing import Optional

import telegram
from atproto.exceptions import FirehoseError
from reactivex.abc import DisposableBase
from selenium.common import WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from telegram.constants import ParseMode
from telegram.error import BadRequest

from bsky.bsky_account_observer import BskyPostObserver
from bsky.bsky_api_extensions import fetch_handle
from bsky.observed_bsky_post import ObservedBlueSkyPost
from event_loop import event_loop, async_io_scheduler
from model.subscription import Subscription
from run_migrations import run_migrations_async
from selenium_webdriver_setup import setup_selenium
from telegram_extensions import link

engine: Optional[AsyncEngine] = None
async_session: Optional[sessionmaker] = None
observation_subscription: Optional[DisposableBase] = None


async def distribute(posts: [ObservedBlueSkyPost]):
    global async_session
    async with async_session() as sql_session:
        subscriptions = (await sql_session.scalars(
            select(Subscription).where(Subscription.did.in_([post.commit_repo for post in posts]))
        )).all()
        logging.info(f"Processing {len(posts)} posts")
        if not subscriptions:
            logging.info("There are no subscriptions; done processing")
            return
        logging.info(f"Setting up selenium for screenshotting ...")
        browser = await setup_selenium()
        bot = telegram.Bot(token=os.environ.get("TELEGRAM_API_KEY"))
        logging.info(f"Distributing to {len(posts)} to {len(subscriptions)}")
        for subscription in subscriptions:
            for post in filter(lambda post: post.commit_repo == subscription.did, posts):
                logging.info(f"Processing {post.http_url_to_post} ...")
                user_handle = await fetch_handle(post.commit_repo)
                if browser is not None:
                    screenshot = await take_screenshot(post, browser)
                    try:
                        await bot.send_photo(
                            chat_id=subscription.chat_id,
                            photo=open(screenshot, 'rb'),
                            caption=f"{link(url=post.profile_url, caption=user_handle)}:"
                                    f"\n\n{post.text}"
                                    f"\n\n{link(url=post.http_url_to_post, caption='Open in Browser')}",
                            parse_mode=ParseMode.HTML
                        )
                    except BadRequest as e:
                        await bot.send_photo(
                            chat_id=subscription.chat_id,
                            photo=open(screenshot, 'rb'),
                            caption=f"{post.profile_url}:"
                                    f"\n\n{post.text}"
                                    f"\n\n{post.http_url_to_post}",
                        )
                else:
                    try:
                        await bot.send_message(
                            chat_id=subscription.chat_id,
                            text=f"{link(url=post.profile_url, caption=user_handle)}:"
                                 f"\n\n{post.text}"
                                 f"\n\n{link(url=post.http_url_to_post, caption='Open in Browser')}",
                            parse_mode=ParseMode.HTML
                        )
                    except BadRequest as e:
                        await bot.send_message(
                            chat_id=subscription.chat_id,
                            text=f"{user_handle}:"
                                 f"\n\n{post.text}"
                                 f"\n\n{post.http_url_to_post}"
                        )


async def take_screenshot(
        post: ObservedBlueSkyPost,
        browser: WebDriver,
        retry: int = 0,
        retry_limit: int = 5
) -> Optional[str]:
    screenshots_dir = os.environ.get("SCREENSHOT_DIRECTORY")
    screenshot_path = f"{screenshots_dir}/{post.commit_repo.replace(':', '-')}_{post.content_identifier}.png"
    if os.path.exists(screenshot_path):
        return screenshot_path
    try:
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
            return await take_screenshot(post, browser, retry=retry + 1, retry_limit=retry_limit)
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


async def __distribute_posts_async__():
    global observation_subscription
    observer = BskyPostObserver()
    observation_subscription = observer.posts(
        schedule_s=30.0,
        capacity=250
    ).subscribe(
        on_next=lambda posts: event_loop.create_task(distribute(posts)),
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

def distribute_posts():
    asyncio.set_event_loop(loop=event_loop)
    current_dir_path = os.path.dirname(os.path.realpath(__file__))
    event_loop.run_until_complete(
        run_migrations_async(f"{current_dir_path}/alembic", os.environ.get("SQLALCHEMY_URL"))
    )
    global engine, async_session
    engine = create_async_engine(
        os.environ.get("SQLALCHEMY_URL")
    )
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    event_loop.run_until_complete(__distribute_posts_async__())
