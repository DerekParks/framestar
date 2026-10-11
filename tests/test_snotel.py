import asyncio
from datetime import UTC, datetime

import httpx
import respx

from framestar.config import SnotelSite
from framestar.snotel import AWDB, report, summarize

STATION = {"stationTriplet": "335:CO:SNTL", "name": "Berthoud Summit", "elevation": 11300.0, "dataTimeZone": -8.0}


def hourly(code, unit, values):
    return {
        "stationElement": {"elementCode": code, "storedUnitCode": unit},
        "values": [{"date": d, "value": v} for d, v in values],
    }


DATA = {
    "stationTriplet": "335:CO:SNTL",
    "data": [
        hourly("TOBS", "degF", [("2026-11-01 10:00", 30.0), ("2026-11-01 22:00", 12.5), ("2026-11-02 09:00", 18.0), ("2026-11-02 11:00", 21.4)]),
        hourly("SNWD", "in", [("2026-11-01 10:00", 20), ("2026-11-01 12:00", 21), ("2026-11-02 11:00", 29)]),
        hourly("WTEQ", "in", [("2026-11-02 11:00", 6.1)]),
    ],
}


def test_summarize_latest_range_and_new_snow():
    site = summarize("Berthoud Pass", STATION, DATA)
    assert site["name"] == "Berthoud Pass"
    assert site["elevation_ft"] == 11300.0
    assert site["observed_at"] == "2026-11-02T11:00:00-08:00"
    assert site["temperature"] == 21.4
    assert (site["temp_high"], site["temp_low"]) == (21.4, 12.5)
    assert site["snow_depth"] == 29
    assert site["snow_24h"] == 9
    assert site["swe"] == 6.1


def test_settling_snowpack_reports_zero_new_snow():
    data = {"data": [hourly("SNWD", "in", [("2026-11-01 11:00", 30), ("2026-11-02 11:00", 27)])]}
    assert summarize("x", STATION, data)["snow_24h"] == 0


def test_missing_data_is_none_not_crash():
    site = summarize("x", {}, {})
    assert site["temperature"] is None and site["snow_24h"] is None and site["observed_at"] is None


@respx.mock
def test_report_joins_station_metadata_in_site_order():
    respx.get(f"{AWDB}/stations").respond(json=[STATION])
    respx.get(f"{AWDB}/data").respond(json=[DATA])

    async def run():
        async with httpx.AsyncClient() as client:
            sites = [SnotelSite(name="Berthoud Pass", triplet="335:CO:SNTL")]
            return await report(client, sites, datetime(2026, 11, 2, 19, 30, tzinfo=UTC))

    body = asyncio.run(run())
    assert [s["name"] for s in body["sites"]] == ["Berthoud Pass"]
    assert body["sites"][0]["snow_depth"] == 29
