import asyncio

from reactivex.scheduler.eventloop import AsyncIOScheduler

event_loop = asyncio.new_event_loop()
async_io_scheduler = AsyncIOScheduler(loop=event_loop)
