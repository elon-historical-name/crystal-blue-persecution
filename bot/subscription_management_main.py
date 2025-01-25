import asyncio
import logging
import os
from typing import Optional, List

import telegram.ext.filters
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler, Application, MessageHandler

from bsky.bluesky_credentials import BlueSkyCredentials
from bsky.bsky_api_extensions import fetch_handle, fetch_did, find_users, \
    get_post_info
from event_loop import event_loop
from model.subscription import Subscription
from run_migrations import run_migrations_async
from telegram_extensions import link

engine: Optional[AsyncEngine] = None
async_session: Optional[sessionmaker] = None

async def get_post_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message if update.message else update.channel_post
    post_url = None
    if update.channel_post:
        args = message.text.split(" ")
        args.pop(0)
        post_url = args[0]
    elif update.message:
        post_url = context.args[0] if context.args and update else None
    if post_url is None:
        await message.reply_text(
            f"You didn't provide a post URL, such as https://bsky.app/profile/did:plc:5n3pxz7xpnrzuxprkjewbki/post/gkklcv73c26."
            f"\n\nUsage: /post someone.bsky.social https://bsky.app/profile/did:plc:5n3pxz7xpnrzuxprkjewbki/post/gkklcv73c26"
        )
        return
    post_info = get_post_info(post_url, credentials=BlueSkyCredentials(
        user_name=os.environ.get("OBSERVER_LOGIN_ALTERNATIVE"),
        password=os.environ.get("OBSERVER_PASSWORD_ALTERNATIVE")
    ))
    if post_info is None:
        await message.reply_text(
            f"{post_url} is not a valid post URL, such as https://bsky.app/profile/did:plc:5n3pxz7xpnrzuxprkjewbki/post/gkklcv73c26."
            f"\n\nUsage: /post someone.bsky.social https://bsky.app/profile/did:plc:5n3pxz7xpnrzuxprkjewbki/post/gkklcv73c26"
        )
        return
    await message.reply_text(post_info)

async def list_subscriptions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global engine
    global async_session
    sql_session: AsyncSession
    message = update.message if update.message else update.channel_post
    async with async_session() as sql_session:
        subscriptions = await sql_session.execute(
            select(Subscription).where(Subscription.chat_id == message.chat_id)
        )
        subscriptions = list(subscriptions.all())
        if subscriptions:
            await message.reply_text(
                f"You have {len(subscriptions)} active subscription(s). Calculating .."
            )
            accounts = [s._data[0].did for s in subscriptions]
            accounts = [f"- {await fetch_handle(did)}" for did in accounts]
            await update.get_bot().send_message(
                chat_id=message.chat_id,
                text="\t\n".join([handle for handle in accounts if handle is not None])
            )
        else:
            await message.reply_text(
                f"You have no active subscription."
            )


async def unsubscribe_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global engine
    global async_session
    message = update.message if update.message else update.channel_post
    chat_id = message.chat_id
    sql_session: AsyncSession
    async with async_session() as sql_session:
        await sql_session.execute(
            delete(Subscription).where(Subscription.chat_id == chat_id)
        )
        await sql_session.commit()
        await message.reply_text(
            f"Unsubscribed from all"
        )


async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global engine
    global async_session
    message = update.message if update.message else update.channel_post
    message_arg: Optional[str] = None
    if update.channel_post:
        args = message.text.split(" ")
        args.pop(0)
        message_arg = args[0]
    elif update.message:
        message_arg = context.args[0] if context.args and update else None
    if message_arg is None:
        await message.reply_text(
            f"You didn't provide a DID or handle, such as someone.bsky.social."
            f"\n\nUsage: /unfollow someone.bsky.social"
        )
        return
    fetched_handle = await fetch_handle(message_arg)
    fetched_did = await fetch_did(message_arg)
    did = fetched_did if fetched_did is not None else message_arg if fetched_handle is not None else None
    handle = fetched_handle if fetched_handle is not None else message_arg if fetched_did is not None else None
    if did is None:
        await message.reply_text(
            f"User not found: {message_arg}" if "bsky.social" in message_arg else f"User not found: {message_arg}. Did you mean"
        )
        return
    chat_id = message.chat_id
    sql_session: AsyncSession
    async with async_session() as sql_session:
        await sql_session.execute(
            delete(Subscription).where(Subscription.chat_id == chat_id).where(Subscription.did == did)
        )
        await sql_session.commit()
        url = f"https://bsky.app/profile/{did}"
        await message.reply_text(
            f"Unsubscribed from {link(url=url, caption=handle if handle is not None else message_arg)}",
            parse_mode=ParseMode.HTML
        )


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global engine
    global async_session
    message = update.message if update.message else update.channel_post
    message_arg: Optional[str] = None
    if update.channel_post:
        args = message.text.split(" ")
        args.pop(0)
        message_arg = args[0]
    elif update.message:
        message_arg = context.args[0] if context.args and update else None
    if message_arg is None:
        await message.reply_text(
            f"You didn't provide a DID or handle, such as someone.bsky.social."
            f"\n\nUsage: /follow someone.bsky.social"
        )
        return
    fetched_handle = await fetch_handle(message_arg)
    fetched_did = await fetch_did(message_arg)
    did = fetched_did if fetched_did is not None else message_arg if fetched_handle is not None else None
    handle = fetched_handle if fetched_handle is not None else message_arg if fetched_did is not None else None
    logging.info(f"Received subscription request for {message_arg} for chat with ID {message.chat_id}")
    if did is None:
        await message.reply_text(
            f"User not found: {did}"
        )
        return

    chat_id = message.chat_id
    sql_session: AsyncSession
    async with async_session() as sql_session:
        subscription = await sql_session.execute(
            select(Subscription).where(Subscription.chat_id == chat_id).where(Subscription.did == did)
        )
        if subscription.first() is None:
            logging.info(f"Subscribing to {did} for chat with ID {chat_id}")
            sql_session.add(Subscription(chat_id=chat_id, did=did))
            await sql_session.commit()
        link_to_profile = link(f"https://bsky.app/profile/{did}", caption=handle if handle is not None else message_arg)
        await message.reply_text(
            f"Successfully subscribed to {handle if handle is not None else message_arg}"
        )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message if update.message else update.channel_post
    message_arg: Optional[List[str]] = None

    if update.channel_post:
        args = message.text.split(" ")
        args.pop(0)
        message_arg = args
    elif update.message:
        message_arg = context.args

    if message_arg is None:
        await message.reply_text(
            f"You didn't provide a name to search for."
            f"\n\nUsage: /find John Doe"
        )
        return
    user_name = " ".join(message_arg)
    primary_credentials = BlueSkyCredentials(
        user_name=os.environ.get("OBSERVER_LOGIN"),
        password=os.environ.get("OBSERVER_PASSWORD")
    )
    secondary_credentials = BlueSkyCredentials(
        user_name=os.environ.get("OBSERVER_LOGIN_ALTERNATIVE"),
        password=os.environ.get("OBSERVER_PASSWORD_ALTERNATIVE")
    )
    response = await find_users(user_name, credentials=primary_credentials)
    if response is None:
        response = await find_users(user_name, credentials=secondary_credentials)
    if response is None:
        await message.reply_text("Search is unfortunately unavailable right now. Try again later.")
        return
    if response.actors:
        actors = [
            f'{actor.displayName}: {link(f"https://bsky.app/profile/{actor.did}", caption=actor.handle)}'
            for actor in response.actors
        ]
        output = "\n".join(actors)
        await message.reply_text(
            text=f"Found the following results. Note that search results are limited to 10 users at max."
                 f"\n\n"
                 f"{output}",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    await message.reply_text(f"No users found for term '{user_name}'", disable_web_page_preview=True)


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message if update.message else update.channel_post
    await message.reply_text(
        text=f"This bot allows you to follow bsky.app users without having an account yourself. You'll get their "
             f"BlueSky posts in real time as a chat message, it's therefore recommended to mute this chat."
             "\n\n\n"
             "<b>1. List of commands</b>"
             "\n\n"
             "/follow <code>userhandle</code>: Follow a user with the provided BlueSky handle."
             "\n"
             "/unfollow <code>userhandle</code>: Unfollow a user with the provided BlueSky handle."
             "\n"
             "/unfollowall: Unfollow all"
             "\n"
             "/following: List the users you are currently following."
             "\n"
             "/post: Get the text of the provided post URL. If the provided URL is a response, the URL of the parent's "
             "post will be included."
             "\n"
             "/find: Find a BlueSky user by the provided search term."
             "\n\n\n"
             "<b>2. What kind of data is stored?</b>"
             "\n\n"
             f"Aside from the {link(url='https://atproto.com/specs/did', caption='DID')} of the user you've subscribed "
             f"to, the unique ID of this chat ({message.chat_id}) is used to identify this chat."
             f"\n"
             f"<b>Nothing else</b> about you or your Telegram account is stored anywhere. "
             f"This bot is entirely unable to identify you once you delete this chat for "
             f"both participants.",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )


async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.channel_post:
        return
    if not update.channel_post.text.startswith("/"):
        return
    if update.channel_post.text.startswith("/following"):
        return await list_subscriptions_command(update, context)
    if update.channel_post.text.startswith("/follow"):
        return await subscribe_command(update, context)
    if update.channel_post.text.startswith("/unfollow"):
        return await unsubscribe_command(update, context)
    if update.channel_post.text.startswith("/find"):
        return await search_command(update, context)
    if update.channel_post.text.startswith("/post"):
        return await get_post_info_command(update, context)
    if update.channel_post.text.startswith("/unfollowall"):
        return await unsubscribe_all_command(update, context)
    if update.channel_post.text == "/info":
        return await info_command(update, context)
    if update.channel_post.text == "/start":
        return await info_command(update, context)

def manage_subscriptions():
    global engine, async_session
    engine = create_async_engine(os.environ.get("SQLALCHEMY_URL"))
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    asyncio.set_event_loop(loop=event_loop)

    current_dir_path = os.path.dirname(os.path.realpath(__file__))
    event_loop.run_until_complete(
        run_migrations_async(f"{current_dir_path}/alembic", os.environ.get("SQLALCHEMY_URL"))
    )

    tg_application = Application.builder().token(os.environ.get("TELEGRAM_API_KEY")).build()
    tg_application.add_handler(
        MessageHandler(
            filters=telegram.ext.filters.UpdateType.CHANNEL_POST,
            callback=handle_command
        )
    )
    tg_application.add_handler(CommandHandler("follow", subscribe_command))
    tg_application.add_handler(CommandHandler("find", search_command))
    tg_application.add_handler(CommandHandler("unfollow", unsubscribe_command))
    tg_application.add_handler(CommandHandler("following", list_subscriptions_command))
    tg_application.add_handler(CommandHandler("unfollowall", unsubscribe_all_command))
    tg_application.add_handler(CommandHandler("info", info_command))
    tg_application.add_handler(CommandHandler("post", get_post_info_command))
    tg_application.add_handler(CommandHandler("start", info_command))
    asyncio.create_task(tg_application.run_polling(allowed_updates=Update.ALL_TYPES))

