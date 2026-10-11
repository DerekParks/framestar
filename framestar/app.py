from __future__ import annotations

import json
import os
import random
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from framestar import calendar, radar, tempest
from framestar.cache import TtlCache
from framestar.config import Config, Ws4kpSlide, load_config
from framestar.immich import Image, ImmichShare, Photo

STATIC_DIR = Path(__file__).parent / "static"
USER_AGENT = "framestar/0.1 (personal photo frame; https://github.com/netbymatt/ws4kp fan)"


def ws4kp_src(config: Config, slide: Ws4kpSlide, host: str) -> str:
    location = config.locations[slide.location]
    params = {
        **config.ws4kp_defaults,
        **slide.params,
        "latLonQuery": location.name,
        "latLon": json.dumps({"lat": location.lat, "lon": location.lon}, separators=(",", ":")),
    }
    return config.ws4kp_url.format(host=host) + "?" + urlencode(params)


def create_app(config: Config, client: httpx.AsyncClient | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owned = client is None
        app.state.client = client or httpx.AsyncClient(timeout=20, headers={"User-Agent": USER_AGENT})
        app.state.radar = radar.RadarRenderer(app.state.client)
        app.state.immich = ImmichShare(app.state.client, config.immich) if config.immich else None
        yield
        if owned:
            await app.state.client.aclose()

    app = FastAPI(title="framestar", lifespan=lifespan)
    agenda_cache: TtlCache[dict] = TtlCache(300)
    tempest_cache: TtlCache[dict] = TtlCache(120)
    photo_list_cache: TtlCache[list[Photo]] = TtlCache(900)
    photo_cache: TtlCache[Image] = TtlCache(3600, max_entries=24)
    radar_time_cache: TtlCache[datetime] = TtlCache(60)
    radar_frame_cache: TtlCache[bytes] = TtlCache(3 * 3600, max_entries=_radar_frame_capacity(config))

    @app.get("/api/config")
    async def get_config(request: Request) -> dict:
        slides = []
        for slide in config.slides:
            entry = slide.model_dump()
            if isinstance(slide, Ws4kpSlide):
                entry["src"] = ws4kp_src(config, slide, request.url.hostname or "localhost")
                entry["name"] = config.locations[slide.location].name
            slides.append(entry)
        return {
            "title": config.title,
            "timezone": config.timezone,
            "features": {"tempest": config.tempest is not None, "calendar": bool(config.calendars)},
            "slides": slides,
        }

    @app.get("/api/calendar")
    async def get_calendar() -> dict:
        return await agenda_cache.get(
            "agenda",
            lambda: calendar.agenda(
                app.state.client, config.calendars, config.tz, config.calendar_days, datetime.now(UTC)
            ),
        )

    @app.get("/api/tempest")
    async def get_tempest() -> dict:
        if config.tempest is None:
            raise HTTPException(404, "no tempest configured")
        return await tempest_cache.get("tempest", lambda: tempest.fetch(app.state.client, config.tempest))

    @app.get("/api/photos")
    async def get_photos(count: int = 5) -> dict:
        if app.state.immich is None:
            raise HTTPException(404, "no immich share configured")
        photos = await photo_list_cache.get("photos", app.state.immich.photos)
        chosen = random.sample(photos, min(count, len(photos))) if config.immich.shuffle else photos[:count]
        return {
            "photos": [
                {"url": f"/api/photos/{p.id}", "taken_at": p.taken_at, "city": p.city} for p in chosen
            ]
        }

    @app.get("/api/photos/{asset_id}")
    async def get_photo(asset_id: uuid.UUID) -> Response:
        if app.state.immich is None:
            raise HTTPException(404, "no immich share configured")
        key = str(asset_id)
        image = await photo_cache.get(key, lambda: app.state.immich.preview(key))
        return Response(image.content, media_type=image.media_type, headers={"Cache-Control": "max-age=86400"})

    @app.get("/api/radar/{map_key}")
    async def get_radar(map_key: str) -> dict:
        if map_key not in config.radar_maps:
            raise HTTPException(404, "unknown radar map")
        latest = await radar_time_cache.get("latest", app.state.radar.latest_time)
        return {
            "name": config.radar_maps[map_key].name,
            "frames": [
                {"time": t.isoformat(), "url": f"/api/radar/{map_key}/{t.strftime(radar.STAMP_FORMAT)}.jpg"}
                for t in radar.frame_times(latest)
            ],
        }

    @app.get("/api/radar/{map_key}/{stamp}.jpg")
    async def get_radar_frame(map_key: str, stamp: str) -> Response:
        radar_map = config.radar_maps.get(map_key)
        if radar_map is None:
            raise HTTPException(404, "unknown radar map")
        try:
            when = radar.parse_stamp(stamp)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        if not datetime.now(UTC) - radar.FRAME_STEP * 36 <= when <= datetime.now(UTC):
            raise HTTPException(400, "radar frame outside the last three hours")
        markers = [config.locations[k] for k in radar_map.markers]
        jpeg = await radar_frame_cache.get(
            (map_key, stamp), lambda: app.state.radar.render(map_key, radar_map, markers, when)
        )
        return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "max-age=10800"})

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


def _radar_frame_capacity(config: Config) -> int:
    return max(1, len(config.radar_maps)) * radar.FRAME_COUNT * 2


def app_from_env() -> FastAPI:
    return create_app(load_config(Path(os.environ.get("FRAMESTAR_CONFIG", "config.yaml"))))
