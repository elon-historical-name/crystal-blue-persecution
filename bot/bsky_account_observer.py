from threading import Thread
from typing import List, Optional, Callable

import reactivex as rx
from atproto import models, CAR
from atproto.firehose import parse_subscribe_repos_message, \
    FirehoseSubscribeReposClient
from atproto.firehose.models import MessageFrame
from reactivex import operators as ops, Observable
from custom_logger import logger

from accounts import get_accounts


def urls_of_interest(urls: List[str]) -> List[str]:
    account_ids = get_accounts().values()
    return list(
        filter(
            lambda url: any(account_id in url for account_id in account_ids),
            urls
        )
    )


class BskyPostObserver:
    _firehose: Optional[FirehoseSubscribeReposClient] = None
    _subject: rx.subject.Subject = rx.subject.Subject()

    def __init__(self):
        pass

    def start(self):
        self.stop()
        self._firehose = FirehoseSubscribeReposClient()
        self._firehose.start(self.process_firehose_message)

    def stop(self):
        if self._firehose is None:
            return
        self._firehose.stop()
        self._firehose = None

    def posts(self, schedule_s: float = 60.0, capacity: int = 25) -> rx.Observable[List[str]]:
        """ Emits ATProto URIs for collected posts every schedule_s
        OR if the given capacity is exhausted before that """
        return self._subject.pipe(
            ops.filter(lambda it: it is not None),
            ops.buffer_with_time_or_count(
                timespan=schedule_s,
                count=capacity
            ),
            ops.map(lambda urls: urls_of_interest(urls)),
            ops.filter(lambda urls: True if urls else False)
        )

    def process_firehose_message(self, message: MessageFrame):
        # we'll process this in another thread since exceptions might occur if the processing takes too much time
        # (aka fire & forget)
        t = Thread(target=self.enqueue, args=(message,), daemon=True)
        t.start()
        return None

    def enqueue(self, message: MessageFrame):
        commit = parse_subscribe_repos_message(message)
        if not isinstance(commit, models.ComAtprotoSyncSubscribeRepos.Commit):
            return
        operations = filter(
            lambda it: it.path.startswith('app.bsky.feed.post'),
            commit.ops
        )
        for op in operations:
            # ATProto uses so-called ATUris to uniquely identify posts.
            # Let's push them into an observable to collect post URIs into a buffer which then
            # might be able to process multiple posts at once, thus avoiding
            # network throttling by bsky.app
            uri = f'at://{commit.repo}/{op.path}'
            logger.info(f"Enqueueing {uri}")
            self._subject.on_next(uri)
