"""Read stored traces only. Replay never launches inference or collection operations."""
import asyncio

from .event_stream import sse
from .run_store import TERMINAL


def recording(store, run_id):
    run = store.get(run_id)
    if run['status'] not in TERMINAL:
        raise ValueError('Wait for the live run to finish before replaying it')
    if not run['last_sequence']:
        raise ValueError('This run has no recorded events')
    return run


async def events(store, run_id, request, after=0, speed=1):
    sequence = after
    while not await request.is_disconnected():
        try:
            await asyncio.to_thread(store.get, run_id)
        except KeyError:
            yield "event: history_expired\ndata: {}\n\n"
            return
        batch = await asyncio.to_thread(store.events, run_id, sequence)
        if not batch:
            return
        for event in batch:
            if await request.is_disconnected():
                return
            # Presentation pacing is explicit, independent of recorded timestamps.
            await asyncio.sleep(.25 / speed)
            sequence = event['sequence']
            yield sse(event)
