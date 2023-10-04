from typing import Optional

import aiohttp


async def fetch_handle(did: str) -> Optional[str]:
    """An alternative method to find a user's handle. Should theoretically bypass network throttling.
    You can pass a commit's repo property to this method"""
    url = f"https://bsky.social/xrpc/com.atproto.repo.describeRepo?repo={did}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                json = await response.json()
                return json["handle"]
    except Exception:
        return None
