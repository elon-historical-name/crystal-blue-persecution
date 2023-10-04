import logging
from typing import List, Optional

import reactivex as rx
from atproto import models, CAR
from atproto.firehose import parse_subscribe_repos_message, \
    AsyncFirehoseSubscribeReposClient
from atproto.firehose.models import MessageFrame
from atproto.xrpc_client.models import get_or_create
from reactivex import operators as ops

from accounts import get_accounts
from event_loop import event_loop, async_io_scheduler


class ObservedPost:

    def __init__(self, commit_repo: str, text: str, atproto_uri: str, http_url_to_post: str, profile_url: str,
                 content_identifier: str):
        self.commit_repo = commit_repo
        self.text = text
        self.atproto_uri = atproto_uri
        self.http_url_to_post = http_url_to_post
        self.profile_url = profile_url
        self.content_identifier = content_identifier


def posts_of_interest(urls: List[ObservedPost]) -> List[ObservedPost]:
    account_ids = get_accounts().values()
    return list(
        filter(
            lambda observed_post: any(account_id in observed_post.commit_repo for account_id in account_ids),
            urls
        )
    )


class BskyPostObserver:
    _firehose: Optional[AsyncFirehoseSubscribeReposClient] = None
    _subject: rx.subject.Subject = rx.subject.Subject()

    def __init__(self):
        pass

    async def start(self):
        await self.stop()
        self._firehose = AsyncFirehoseSubscribeReposClient()
        await self._firehose.start(self.process_firehose_message)

    async def stop(self):
        if self._firehose is None:
            return
        await self._firehose.stop()
        self._firehose = None

    def posts(self, schedule_s: float = 60.0, capacity: int = 25) -> rx.Observable[List[ObservedPost]]:
        """ Emits ATProto URIs for collected posts every schedule_s
        OR if the given capacity is exhausted before that """
        return self._subject.pipe(
            ops.filter(lambda it: it is not None),
            ops.buffer_with_time_or_count(
                timespan=schedule_s,
                count=capacity
            ),
            ops.map(lambda posts: posts_of_interest(posts)),
            ops.filter(lambda posts: True if posts else False),
            ops.subscribe_on(async_io_scheduler)
        )

    async def process_firehose_message(self, message: MessageFrame):
        # we'll process this in another thread since exceptions might occur if the processing takes too much time
        # (aka fire & forget)
        event_loop.create_task(self.enqueue(message))
        return None

    async def enqueue(self, message: MessageFrame):
        commit = parse_subscribe_repos_message(message)
        if not isinstance(commit, models.ComAtprotoSyncSubscribeRepos.Commit):
            return
        operations = filter(
            lambda it: it.path.startswith('app.bsky.feed.post'),
            commit.ops
        )
        car = CAR.from_bytes(commit.blocks)
        for op in operations:
            # ATProto uses so-called ATUris to uniquely identify posts.
            # Let's push them into an observable to collect post URIs into a buffer which then
            # might be able to process multiple posts at once, thus avoiding
            # network throttling by bsky.app
            record_raw_data = car.blocks.get(op.cid)
            if not record_raw_data:
                continue
            record = get_or_create(record_raw_data, strict=False)
            url = f"https://bsky.app/profile/{commit.repo}/post/{op.path}".replace("app.bsky.feed.post/", "")
            observed_post = ObservedPost(
                commit_repo=commit.repo,
                text=record.text,
                atproto_uri=f'at://{commit.repo}/{op.path}',
                http_url_to_post=url,
                profile_url=f"https://bsky.app/profile/{commit.repo}",
                content_identifier=op.path.replace("app.bsky.feed.post/", "")
            )
            logging.info(f"Enqueueing {observed_post.atproto_uri}")
            self._subject.on_next(observed_post)
