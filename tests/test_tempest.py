from framestar.tempest import icon_url, normalize

RAW = {
    "timezone": "America/Denver",
    "current_conditions": {
        "time": 1791730000,
        "conditions": "Partly Cloudy",
        "icon": "partly-cloudy-day",
        "air_temperature": 61.2,
        "feels_like": 61.2,
        "dew_point": 30.1,
        "relative_humidity": 31,
        "sea_level_pressure": 30.07,
        "pressure_trend": "falling",
        "wind_avg": 6,
        "wind_gust": 12,
        "wind_direction_cardinal": "NW",
        "uv": 3.4,
        "precip_accum_local_day": 0,
        "lightning_strike_count_last_3hr": 0,
    },
    "forecast": {
        "daily": [
            {"day_start_local": 1791698400 + 86400 * i, "conditions": "Clear", "icon": "clear-day",
             "air_temp_high": 70 + i, "air_temp_low": 40 + i, "precip_probability": 0}
            for i in range(10)
        ]
    },
}


def test_normalize_current_and_five_days():
    data = normalize(RAW, "Backyard")
    assert data["station"] == "Backyard"
    assert data["current"]["temperature"] == 61.2
    assert data["current"]["icon"] == "icons/Partly-Cloudy.gif"
    assert data["current"]["wind_cardinal"] == "NW"
    assert [d["high"] for d in data["daily"]] == [70, 71, 72, 73, 74]


def test_unknown_icon_falls_back():
    assert icon_url("meteor-shower") == "icons/No-Data.gif"
    assert icon_url(None) == "icons/No-Data.gif"


def test_every_mapped_icon_exists():
    from pathlib import Path

    from framestar.tempest import ICONS

    icons = Path(__file__).parent.parent / "framestar" / "static" / "icons"
    missing = [name for name in ICONS.values() if not (icons / f"{name}.gif").exists()]
    assert missing == []
