from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from framestar.calendar import expand, group_by_day
from framestar.config import CalendarFeed

DENVER = ZoneInfo("America/Denver")
FEED = CalendarFeed(name="Family", url="https://example.invalid/basic.ics", color="#ffd700")

ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//EN
BEGIN:VEVENT
UID:weekly
DTSTART:20261006T223000Z
DTEND:20261007T000000Z
RRULE:FREQ=WEEKLY;BYDAY=TU
SUMMARY:Soccer practice
LOCATION:Sloan's Lake
END:VEVENT
BEGIN:VEVENT
UID:trip
DTSTART;VALUE=DATE:20261012
DTEND;VALUE=DATE:20261015
SUMMARY:Fraser trip
END:VEVENT
BEGIN:VEVENT
UID:cancelled
DTSTART:20261012T150000Z
DTEND:20261012T160000Z
STATUS:CANCELLED
SUMMARY:Dentist
END:VEVENT
BEGIN:VEVENT
UID:late
DTSTART;TZID=America/Chicago:20261011T230000
DTEND;TZID=America/Chicago:20261012T013000
SUMMARY:Norman watch party
END:VEVENT
BEGIN:VEVENT
UID:outside
DTSTART:20261101T150000Z
DTEND:20261101T160000Z
SUMMARY:Too far out
END:VEVENT
END:VCALENDAR
"""

FIRST_DAY = date(2026, 10, 11)
WINDOW_START = datetime.combine(FIRST_DAY, time.min, DENVER)
WINDOW_END = WINDOW_START + timedelta(days=7)


def events():
    return expand(ICS, FEED, DENVER, WINDOW_START, WINDOW_END)


def test_expand_recurring_all_day_and_cancelled():
    titles = sorted(e.title for e in events())
    assert titles == ["Fraser trip", "Norman watch party", "Soccer practice"]


def test_recurring_event_in_local_time():
    soccer = next(e for e in events() if e.title == "Soccer practice")
    assert soccer.start == datetime(2026, 10, 13, 16, 30, tzinfo=DENVER)
    assert soccer.location == "Sloan's Lake"
    assert not soccer.all_day


def test_group_by_day_spans_and_order():
    days = group_by_day(events(), FIRST_DAY, 7, DENVER)
    by_date = {d["date"]: [e["title"] for e in d["events"]] for d in days}
    assert len(days) == 7
    assert by_date["2026-10-11"] == ["Norman watch party"]
    assert by_date["2026-10-12"] == ["Fraser trip", "Norman watch party"]
    assert by_date["2026-10-13"] == ["Fraser trip", "Soccer practice"]
    assert by_date["2026-10-14"] == ["Fraser trip"]
    assert by_date["2026-10-15"] == []


def test_continued_flag_for_event_crossing_midnight():
    days = group_by_day(events(), FIRST_DAY, 2, DENVER)
    party_day2 = next(e for e in days[1]["events"] if e["title"] == "Norman watch party")
    assert party_day2["continued"]
    assert party_day2["end"] == "2026-10-12T00:30:00-06:00"
    trip = days[1]["events"][0]
    assert trip["all_day"] and not trip["continued"]


def test_plain_text_strips_emoji_keeps_degrees_and_accents():
    from framestar.calendar import plain_text

    assert plain_text("\U0001F3C0 Oklahoma City Thunder @ Atlanta Hawks") == "Oklahoma City Thunder @ Atlanta Hawks"
    assert plain_text("Café run \u2744\ufe0f 20°") == "Café run 20°"
    assert plain_text("\U0001F468\u200D\U0001F469\u200D\U0001F467 Family dinner") == "Family dinner"
