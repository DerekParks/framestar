from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx

from framestar.config import SnotelSite

AWDB = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1"
ELEMENTS = "TOBS,SNWD,WTEQ"
WINDOW = timedelta(hours=48)
DAY = timedelta(hours=24)


def _station_zone(utc_offset_hours: float) -> timezone:
    return timezone(timedelta(hours=utc_offset_hours))


def _series(element: dict, zone: timezone) -> list[tuple[datetime, float]]:
    return [
        (datetime.strptime(v["date"], "%Y-%m-%d %H:%M").replace(tzinfo=zone), float(v["value"]))
        for v in element.get("values", [])
        if v.get("value") is not None
    ]


def _value_near(series: list[tuple[datetime, float]], target: datetime) -> float | None:
    before = [v for t, v in series if t <= target]
    return before[-1] if before else None


def summarize(name: str, station: dict, data: dict) -> dict:
    """One site's latest reading plus 24 h temperature range and snow-depth change."""
    zone = _station_zone(station.get("dataTimeZone", -7))
    by_code = {e["stationElement"]["elementCode"]: _series(e, zone) for e in data.get("data", [])}
    temps = by_code.get("TOBS", [])
    depth = by_code.get("SNWD", [])
    swe = by_code.get("WTEQ", [])
    latest = max((s[-1][0] for s in (temps, depth, swe) if s), default=None)
    recent = [v for t, v in temps if latest and t > latest - DAY]
    depth_now = depth[-1][1] if depth else None
    depth_then = _value_near(depth, latest - DAY) if latest else None
    return {
        "name": name,
        "elevation_ft": station.get("elevation"),
        "observed_at": latest.isoformat() if latest else None,
        "temperature": temps[-1][1] if temps else None,
        "temp_high": max(recent) if recent else None,
        "temp_low": min(recent) if recent else None,
        "snow_depth": depth_now,
        "snow_24h": max(0.0, depth_now - depth_then) if depth_now is not None and depth_then is not None else None,
        "swe": swe[-1][1] if swe else None,
    }


async def report(client: httpx.AsyncClient, sites: list[SnotelSite], now: datetime) -> dict:
    triplets = ",".join(s.triplet for s in sites)
    fmt = "%Y-%m-%d %H:%M"
    stations_req = client.get(f"{AWDB}/stations", params={"stationTriplets": triplets, "returnStationElements": "false"})
    data_req = client.get(
        f"{AWDB}/data",
        params={
            "stationTriplets": triplets,
            "elements": ELEMENTS,
            "duration": "HOURLY",
            "beginDate": (now - WINDOW).strftime(fmt),
            "endDate": (now + timedelta(hours=2)).strftime(fmt),
            "periodRef": "END",
        },
    )
    stations_resp, data_resp = await asyncio.gather(stations_req, data_req)
    stations_resp.raise_for_status()
    data_resp.raise_for_status()
    stations = {s["stationTriplet"]: s for s in stations_resp.json()}
    data = {d["stationTriplet"]: d for d in data_resp.json()}
    return {
        "sites": [
            summarize(site.name, stations.get(site.triplet, {}), data.get(site.triplet, {})) for site in sites
        ]
    }
