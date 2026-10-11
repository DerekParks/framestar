import asyncio

import pytest

from framestar.cache import TtlCache


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_caches_until_ttl_then_refreshes():
    clock = Clock()
    cache = TtlCache(10, clock=clock)
    calls = []

    async def load():
        calls.append(clock.now)
        return len(calls)

    async def run():
        assert await cache.get("k", load) == 1
        clock.now = 9
        assert await cache.get("k", load) == 1
        clock.now = 11
        assert await cache.get("k", load) == 2

    asyncio.run(run())


def test_serves_stale_on_failure_and_raises_without_value():
    clock = Clock()
    cache = TtlCache(10, clock=clock)

    async def ok():
        return "good"

    async def boom():
        raise RuntimeError("down")

    async def run():
        with pytest.raises(RuntimeError):
            await cache.get("other", boom)
        await cache.get("k", ok)
        clock.now = 100
        assert await cache.get("k", boom) == "good"

    asyncio.run(run())


def test_evicts_oldest_beyond_capacity():
    cache = TtlCache(100, max_entries=2)

    async def run():
        for key in "abc":
            await cache.get(key, lambda key=key: asyncio.sleep(0, result=key))
        return list(cache._entries)

    assert asyncio.run(run()) == ["b", "c"]


def test_concurrent_misses_load_once():
    cache = TtlCache(100)
    calls = 0

    async def load():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return calls

    async def run():
        return await asyncio.gather(*(cache.get("k", load) for _ in range(5)))

    assert asyncio.run(run()) == [1] * 5
    assert calls == 1


def test_stale_value_expires_after_max_stale():
    clock = Clock()
    cache = TtlCache(10, max_stale=20, clock=clock)

    async def ok():
        return "good"

    async def boom():
        raise RuntimeError("down")

    async def run():
        await cache.get("k", ok)
        clock.now = 25
        assert await cache.get("k", boom) == "good"
        clock.now = 31
        with pytest.raises(RuntimeError):
            await cache.get("k", boom)

    asyncio.run(run())


def test_drop_forces_reload():
    cache = TtlCache(100)
    calls = 0

    async def load():
        nonlocal calls
        calls += 1
        return calls

    async def run():
        await cache.get("k", load)
        cache.drop("k")
        return await cache.get("k", load)

    assert asyncio.run(run()) == 2
