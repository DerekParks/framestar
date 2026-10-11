from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class _Entry[T]:
    value: T
    fetched_at: float


class TtlCache[T]:
    """Async memo keyed by arbitrary hashables. A failed refresh serves the stale value for up to max_stale seconds."""

    def __init__(
        self,
        ttl_seconds: float,
        max_entries: int = 512,
        max_stale: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._ttl = ttl_seconds
        self._max = max_entries
        self._max_stale = max_stale
        self._clock = clock
        self._entries: dict[Hashable, _Entry[T]] = {}
        self._locks: dict[Hashable, asyncio.Lock] = {}

    async def get(self, key: Hashable, load: Callable[[], Awaitable[T]]) -> T:
        entry = self._entries.get(key)
        if entry is not None and self._fresh(entry):
            return entry.value
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            entry = self._entries.get(key)
            if entry is not None and self._fresh(entry):
                return entry.value
            try:
                value = await load()
            except Exception:
                if entry is None or not self._servable_stale(entry):
                    self._entries.pop(key, None)
                    raise
                log.exception("refresh of %r failed; serving stale value", key)
                return entry.value
            self._put(key, value)
            return value

    def drop(self, key: Hashable) -> None:
        self._entries.pop(key, None)

    def _fresh(self, entry: _Entry[T]) -> bool:
        return self._clock() - entry.fetched_at < self._ttl

    def _servable_stale(self, entry: _Entry[T]) -> bool:
        return self._max_stale is None or self._clock() - entry.fetched_at < self._ttl + self._max_stale

    def _put(self, key: Hashable, value: T) -> None:
        self._entries.pop(key, None)
        self._entries[key] = _Entry(value, self._clock())
        while len(self._entries) > self._max:
            oldest = next(iter(self._entries))
            del self._entries[oldest]
            self._locks.pop(oldest, None)
