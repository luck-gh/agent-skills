"""Small raw source fixture. No execution is needed for architecture analysis."""
import asyncio

cache = {}
store = {"42": {"id": "42"}}
listeners = []


def register(listener):
    listeners.append(listener)


async def notify(record):
    for listener in listeners:
        listener(record)


async def get_record(key):
    if key in cache:
        return cache[key]
    await asyncio.sleep(0)
    record = store[key]
    cache[key] = record
    asyncio.create_task(notify(record))
    return record
