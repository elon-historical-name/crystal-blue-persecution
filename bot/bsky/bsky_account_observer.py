import logging
from typing import List, Optional

import reactivex as rx
from atproto import models, CAR
from atproto_client.models import get_or_create
from atproto_firehose import AsyncFirehoseSubscribeReposClient, parse_subscribe_repos_message
from atproto_firehose.models import MessageFrame
from reactivex import operators as ops

from bsky.observed_bsky_post import ObservedBlueSkyPost
from event_loop import event_loop, async_io_scheduler


class BskyPostObserver:
    _firehose: Optional[AsyncFirehoseSubscribeReposClient] = None
    _subject: rx.subject.Subject = rx.subject.Subject()

    def __init__(self):
        pass

    async def start(self):
        await self.stop()
        self._firehose = AsyncFirehoseSubscribeReposClient(base_uri="wss://bsky.network/xrpc")
        await self._firehose.start(self.process_firehose_message)

    async def stop(self):
        if self._firehose is None:
            return
        await self._firehose.stop()
        self._firehose = None

    def posts(self, schedule_s: float = 60.0, capacity: int = 25) -> rx.Observable[List[ObservedBlueSkyPost]]:
        """ Emits ATProto URIs for collected posts every schedule_s
        OR if the given capacity is exhausted before that """
        return self._subject.pipe(
            ops.filter(lambda it: it is not None),
            ops.buffer_with_time_or_count(
                timespan=schedule_s,
                count=capacity
            ),
            ops.filter(lambda posts: True if posts else False),
            ops.subscribe_on(async_io_scheduler)
        )

    async def process_firehose_message(self, message: MessageFrame):
        # we'll process this in another thread since exceptions might occur if the processing takes too much time
        # (aka fire & forget)
        self.enqueue(message)
        return None

    def enqueue(self, message: MessageFrame):
        commit = parse_subscribe_repos_message(message)
        if not isinstance(commit, models.ComAtprotoSyncSubscribeRepos.Commit):
            return
        if not commit.blocks:
            logging.info("Commit does not contain any blocks")
            return
        operations = commit.ops
        car = CAR.from_bytes(commit.blocks)
        for op in operations:
            # ATProto uses so-called ATUris to uniquely identify posts.
            # Let's push them into an observable to collect post URIs into a buffer which then
            # might be able to process multiple posts at once, thus avoiding
            # network throttling by bsky.app
            if op.action != 'create':
                continue
            record_raw_data = car.blocks.get(op.cid)
            if not record_raw_data:
                continue
            record = get_or_create(record_raw_data, strict=False)
            if not record:
                logging.warning("get_or_create returned None")
                continue
            if record.py_type != "app.bsky.feed.post":
                continue
            url = f"https://bsky.app/profile/{commit.repo}/post/{op.path}".replace("app.bsky.feed.post/", "")
            observed_post = ObservedBlueSkyPost(
                commit_repo=commit.repo,
                text=record.text,
                atproto_uri=f'at://{commit.repo}/{op.path}',
                http_url_to_post=url,
                profile_url=f"https://bsky.app/profile/{commit.repo}",
                content_identifier=op.path.replace("app.bsky.feed.post/", "")
            )
            self._subject.on_next(observed_post)
