import dataclasses
import logging
from typing import Optional, List

import aiohttp
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
