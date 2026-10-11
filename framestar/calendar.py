from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx
import icalendar
import recurring_ical_events

from framestar.config import CalendarFeed

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    calendar: str
    color: str
    title: str
    start: datetime
    end: datetime
    all_day: bool
    location: str | None


def _as_local(value: date | datetime, tz: ZoneInfo) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=tz) if value.tzinfo is None else value.astimezone(tz)
    return datetime.combine(value, time.min, tz)


def expand(ics: bytes, feed: CalendarFeed, tz: ZoneInfo, window_start: datetime, window_end: datetime) -> list[Event]:
    cal = icalendar.Calendar.from_ical(ics)
    events = []
    for component in recurring_ical_events.of(cal).between(window_start, window_end):
        if str(component.get("STATUS", "")).upper() == "CANCELLED":
            continue
        dtstart = component.decoded("DTSTART")
        all_day = not isinstance(dtstart, datetime)
        start = _as_local(dtstart, tz)
        if "DTEND" in component:
            end = _as_local(component.decoded("DTEND"), tz)
        elif "DURATION" in component:
            end = start + component.decoded("DURATION")
        else:
            end = start + (timedelta(days=1) if all_day else timedelta())
        location = str(component.get("LOCATION", "")).strip() or None
        events.append(
            Event(
                calendar=feed.name,
                color=feed.color,
                title=str(component.get("SUMMARY", "(busy)")).strip(),
                start=start,
                end=end,
                all_day=all_day,
                location=location,
            )
        )
    return events


def group_by_day(events: list[Event], first_day: date, days: int, tz: ZoneInfo) -> list[dict]:
    out = []
    for offset in range(days):
        day = first_day + timedelta(days=offset)
        day_start = datetime.combine(day, time.min, tz)
        day_end = day_start + timedelta(days=1)
        todays = [e for e in events if e.start < day_end and (e.end > day_start or e.start >= day_start)]
        todays.sort(key=lambda e: (not e.all_day, e.start, e.title.lower()))
        out.append(
            {
                "date": day.isoformat(),
                "events": [
                    {
                        "calendar": e.calendar,
                        "color": e.color,
                        "title": e.title,
                        "start": e.start.isoformat(),
                        "end": e.end.isoformat(),
                        "all_day": e.all_day,
                        "continued": e.start < day_start,
                        "location": e.location,
                    }
                    for e in todays
                ],
            }
        )
    return out


async def fetch_feed(client: httpx.AsyncClient, feed: CalendarFeed) -> bytes:
    response = await client.get(feed.url, follow_redirects=True)
    response.raise_for_status()
    return response.content


async def agenda(
    client: httpx.AsyncClient, feeds: list[CalendarFeed], tz: ZoneInfo, days: int, now: datetime
) -> dict:
    first_day = now.astimezone(tz).date()
    window_start = datetime.combine(first_day, time.min, tz)
    window_end = window_start + timedelta(days=days)
    results = await asyncio.gather(*(fetch_feed(client, f) for f in feeds), return_exceptions=True)
    events: list[Event] = []
    errors = []
    for feed, result in zip(feeds, results, strict=True):
        if isinstance(result, BaseException):
            log.warning("calendar %s failed: %r", feed.name, result)
            errors.append(feed.name)
            continue
        events.extend(expand(result, feed, tz, window_start, window_end))
    if errors and len(errors) == len(feeds):
        raise RuntimeError(f"every calendar failed: {errors}")
    return {
        "calendars": [{"name": f.name, "color": f.color} for f in feeds],
        "days": group_by_day(events, first_day, days, tz),
        "errors": errors,
    }
