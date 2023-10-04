import os
from typing import Optional

import telegram

from bsky_account_observer import ObservedPost


async def publish_to_tg_channel(post: ObservedPost, screenshot_path: str, user_handle: Optional[str]):
    api_key = os.environ.get("TELEGRAM_API_KEY")
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID")
    if api_key is None or channel_id is None:
        return
    bot = telegram.Bot(token=api_key)
    print(f"Reposting {post.http_url_to_post} to TG channel {channel_id}")
    await bot.send_photo(
        chat_id=channel_id,
        photo=open(screenshot_path, 'rb'),
        caption=f"{user_handle if user_handle is not None else post.profile_url}:"
                f"\n\n{post.text}"
                f"\n\n{post.http_url_to_post}"
    )
