import dataclasses
import logging
from typing import Optional, List

import aiohttp
from atproto_client import Client
from dataclass_wizard import fromdict

from bsky.bluesky_credentials import BlueSkyCredentials


@dataclasses.dataclass
class PrefetchUsersResponseActor:
    did: str
    handle: str
    displayName: str
    viewer: dict[str, bool]
    avatar: Optional[str] = None


@dataclasses.dataclass
class PrefetchUsersResponse:
    actors: List[PrefetchUsersResponseActor]


async def fetch_handle(did: str) -> Optional[str]:
    url = f"https://bsky.social/xrpc/com.atproto.repo.describeRepo?repo={did}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                json = await response.json()
                return json["handle"]
    except Exception:
        return None


def remove_sld_tld_protocol(url: str) -> Optional[str]:
    import re
    # Regular expression to match the protocol, SLD, and TLD
    pattern = r'^(https?://)?(?:www\.)?[^/]+(?=/(.*))'

    # Find the match for the pattern
    match = re.match(pattern, url)

    if match:
        return match.group(2) if match.group(2) else None
    else:
        return url

def get_profile_identifier_and_post_identifier_from_at_proto_uri(uri: str) -> tuple[Optional[str], Optional[str]]:
    path = remove_sld_tld_protocol(uri)
    if path is None:
        return None, None
    split_post = path.replace("/", "", 1).split("/app.bsky.feed.post/")
    if len(split_post) == 2:
        return split_post[0], split_post[1]
    return None, None

def get_profile_identifier_and_post_identifier_from_url(url: str) -> tuple[Optional[str], Optional[str]]:
    path = remove_sld_tld_protocol(url)
    if path is None:
        return None, None
    split_post = path.replace("profile/", "").split("/post/")
    if len(split_post) == 2:
        return split_post[0], split_post[1]
    return None, None

def get_url_to_parent_if_available(post_url: str, credentials: BlueSkyCredentials) -> Optional[str]:
    profile, post = get_profile_identifier_and_post_identifier_from_url(post_url)
    if profile is None:
        return None
    client = Client()
    client.login(credentials.user_name, credentials.password)
    try:
        record = client.get_post(post_rkey=post, profile_identify=profile)
        if record is None:
            return None
        if record.value.py_type != 'app.bsky.feed.post':
            return None
        if record.value.reply is not None:
            responding_to_profile, responding_to_post = get_profile_identifier_and_post_identifier_from_at_proto_uri(
                record.value.reply.parent.uri
            )
            if responding_to_post is None:
                return None
            return f"https://bsky.app/profile/{responding_to_profile}/post/{responding_to_post}"
    except:
        return None
    return None

def get_post_info(post_url: str, credentials: BlueSkyCredentials) -> Optional[str]:
    profile, post = get_profile_identifier_and_post_identifier_from_url(post_url)
    if profile is None:
        return None
    client = Client()
    client.login(credentials.user_name, credentials.password)
    try:
        record = client.get_post(post_rkey=post, profile_identify=profile)
        if record is None:
            return None
        if record.value.py_type != 'app.bsky.feed.post':
            return None
        message_text = record.value.text
        if record.value.reply is not None:
            responding_to_profile, responding_to_post = get_profile_identifier_and_post_identifier_from_at_proto_uri(
                record.value.reply.parent.uri
            )
            if responding_to_post is None:
                return message_text
            responding_to = get_url_to_parent_if_available(post_url, credentials=credentials)
            if responding_to is None:
                return message_text
            message_text = f"Replying to: {responding_to}\n\n{message_text}"
            return message_text
    except:
        return None
    return message_text

async def fetch_did(handle: str) -> Optional[str]:
    """An alternative method to find a user's handle. Should theoretically bypass network throttling.
    You can pass a commit's repo property to this method"""

    url = f"https://bsky.social/xrpc/com.atproto.identity.resolveHandle?handle={handle}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                json = await response.json()
                return json["did"]
    except Exception:
        return None


async def fetch_bearer_token(credentials: BlueSkyCredentials) -> Optional[str]:
    if not credentials.user_name or not credentials.password:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            data = {"identifier": credentials.user_name, "password": credentials.password}
            async with session.post("https://bsky.social/xrpc/com.atproto.server.createSession", json=data) as response:
                json = await response.json()
                return json['accessJwt']
    except Exception:
        return None


async def find_users(substring: str, credentials: BlueSkyCredentials) -> Optional[PrefetchUsersResponse]:
    if not substring:
        return PrefetchUsersResponse(actors=[])
    authorization = await fetch_bearer_token(credentials=credentials)
    if authorization is None:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': f'Bearer {authorization}'}
            fetch_users = f"https://bsky.social/xrpc/app.bsky.actor.searchActorsTypeahead?term={substring}&limit=10"
            async with session.get(fetch_users, headers=headers) as response:
                json = await response.json()
                return fromdict(PrefetchUsersResponse, json)
    except Exception as e:
        logging.warning("Exception occurred on fetching users")
        logging.warning(e)
        return None
