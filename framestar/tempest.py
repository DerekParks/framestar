from __future__ import annotations

import httpx

from framestar.config import Tempest

BETTER_FORECAST = "https://swd.weatherflow.com/swd/rest/better_forecast"
UNITS = {
    "units_temp": "f",
    "units_wind": "mph",
    "units_pressure": "inhg",
    "units_precip": "in",
    "units_distance": "mi",
}

ICONS = {
    "clear-day": "Sunny",
    "clear-night": "Clear",
    "partly-cloudy-day": "Partly-Cloudy",
    "partly-cloudy-night": "Mostly-Clear",
    "cloudy": "Cloudy",
    "foggy": "Fog",
    "windy": "Windy",
    "rainy": "Rain",
    "possibly-rainy-day": "Shower",
    "possibly-rainy-night": "Shower",
    "sleet": "Sleet",
    "possibly-sleet-day": "Rain-Sleet",
    "possibly-sleet-night": "Rain-Sleet",
    "snow": "Heavy-Snow",
    "possibly-snow-day": "Light-Snow",
    "possibly-snow-night": "Light-Snow",
    "thunderstorm": "Thunderstorm",
    "possibly-thunderstorm-day": "Scattered-Thunderstorms-Day",
    "possibly-thunderstorm-night": "Scattered-Thunderstorms-Night",
}


def icon_url(tempest_icon: str | None) -> str:
    return f"icons/{ICONS.get(tempest_icon or '', 'No-Data')}.gif"


def normalize(raw: dict, station_name: str) -> dict:
    cc = raw["current_conditions"]
    daily = raw.get("forecast", {}).get("daily", [])
    return {
        "station": station_name,
        "timezone": raw.get("timezone"),
        "observed_at": cc.get("time"),
        "current": {
            "conditions": cc.get("conditions"),
            "icon": icon_url(cc.get("icon")),
            "temperature": cc.get("air_temperature"),
            "feels_like": cc.get("feels_like"),
            "dew_point": cc.get("dew_point"),
            "humidity": cc.get("relative_humidity"),
            "pressure": cc.get("sea_level_pressure"),
            "pressure_trend": cc.get("pressure_trend"),
            "wind_avg": cc.get("wind_avg"),
            "wind_gust": cc.get("wind_gust"),
            "wind_cardinal": cc.get("wind_direction_cardinal"),
            "uv": cc.get("uv"),
            "rain_today": cc.get("precip_accum_local_day"),
            "lightning_3hr": cc.get("lightning_strike_count_last_3hr"),
        },
        "daily": [
            {
                "day_start": d.get("day_start_local"),
                "conditions": d.get("conditions"),
                "icon": icon_url(d.get("icon")),
                "high": d.get("air_temp_high"),
                "low": d.get("air_temp_low"),
                "precip_probability": d.get("precip_probability"),
            }
            for d in daily[:5]
        ],
    }


async def fetch(client: httpx.AsyncClient, tempest: Tempest) -> dict:
    params = {"station_id": tempest.station_id, "token": tempest.token, **UNITS}
    response = await client.get(BETTER_FORECAST, params=params)
    response.raise_for_status()
    return normalize(response.json(), tempest.name)
