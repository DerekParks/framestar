from __future__ import annotations

import asyncio
import io
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from PIL import Image, ImageDraw

from framestar.config import Location, RadarMap

TILE = 256
LATEST_N0Q = "https://mesonet.agron.iastate.edu/data/gis/images/4326/USCOMP/n0q_0.json"
RADAR_TILE = "https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/ridge::USCOMP-N0Q-{stamp}/{z}/{x}/{y}.png"
BASE_TILE = "https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
LABEL_TILE = "https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
FRAME_STEP = timedelta(minutes=5)
FRAME_COUNT = 12
STAMP_FORMAT = "%Y%m%d%H%M"


def world_pixel(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    scale = TILE * 2**zoom
    x = (lon + 180.0) / 360.0 * scale
    lat_rad = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * scale
    return x, y


@dataclass(frozen=True)
class Viewport:
    zoom: int
    left: int
    top: int
    width: int
    height: int

    @classmethod
    def centered(cls, lat: float, lon: float, zoom: int, width: int, height: int) -> Viewport:
        cx, cy = world_pixel(lat, lon, zoom)
        return cls(zoom, round(cx - width / 2), round(cy - height / 2), width, height)

    def tiles(self) -> list[tuple[int, int, int, int]]:
        """(tile_x, tile_y, paste_x, paste_y) covering the viewport; tile_x wraps around the antimeridian."""
        n = 2**self.zoom
        out = []
        for ty in range(self.top // TILE, (self.top + self.height - 1) // TILE + 1):
            if not 0 <= ty < n:
                continue
            for tx in range(self.left // TILE, (self.left + self.width - 1) // TILE + 1):
                out.append((tx % n, ty, tx * TILE - self.left, ty * TILE - self.top))
        return out

    def project(self, lat: float, lon: float) -> tuple[float, float]:
        x, y = world_pixel(lat, lon, self.zoom)
        return x - self.left, y - self.top


def frame_times(latest: datetime) -> list[datetime]:
    return [latest - FRAME_STEP * i for i in reversed(range(FRAME_COUNT))]


def parse_stamp(stamp: str) -> datetime:
    when = datetime.strptime(stamp, STAMP_FORMAT).replace(tzinfo=UTC)
    if when.minute % 5:
        raise ValueError("radar frames are on 5 minute boundaries")
    return when


class RadarRenderer:
    def __init__(self, client: httpx.AsyncClient, width: int = 1280, height: int = 610, concurrency: int = 8):
        self._client = client
        self._width = width
        self._height = height
        self._sem = asyncio.Semaphore(concurrency)
        self._layers: dict[tuple[str, str], Image.Image] = {}

    async def latest_time(self) -> datetime:
        response = await self._client.get(LATEST_N0Q)
        response.raise_for_status()
        return datetime.fromisoformat(response.json()["meta"]["valid"].replace("Z", "+00:00"))

    def viewport(self, radar: RadarMap) -> Viewport:
        return Viewport.centered(radar.lat, radar.lon, radar.zoom, self._width, self._height)

    async def _tile(self, template: str, z: int, x: int, y: int, **extra) -> Image.Image | None:
        async with self._sem:
            response = await self._client.get(template.format(z=z, x=x, y=y, **extra))
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert("RGBA")

    async def _layer(self, template: str, view: Viewport, **extra) -> Image.Image:
        canvas = Image.new("RGBA", (view.width, view.height), (0, 0, 0, 0))
        placements = view.tiles()
        tiles = await asyncio.gather(*(self._tile(template, view.zoom, tx, ty, **extra) for tx, ty, _, _ in placements))
        for tile, (_, _, px, py) in zip(tiles, placements, strict=True):
            if tile is not None:
                canvas.paste(tile, (px, py))
        return canvas

    async def _static_layer(self, key: str, template: str, view: Viewport) -> Image.Image:
        cache_key = (key, template)
        if cache_key not in self._layers:
            self._layers[cache_key] = await self._layer(template, view)
        return self._layers[cache_key]

    async def render(self, key: str, radar: RadarMap, markers: list[Location], when: datetime) -> bytes:
        view = self.viewport(radar)
        base, labels, echoes = await asyncio.gather(
            self._static_layer(key, BASE_TILE, view),
            self._static_layer(key, LABEL_TILE, view),
            self._layer(RADAR_TILE, view, stamp=when.strftime(STAMP_FORMAT)),
        )
        frame = Image.new("RGBA", (view.width, view.height), (0, 0, 0, 255))
        frame.alpha_composite(base)
        frame.alpha_composite(echoes)
        draw = ImageDraw.Draw(frame)
        for marker in markers:
            x, y = view.project(marker.lat, marker.lon)
            draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(255, 255, 0, 255), outline=(0, 0, 0, 255), width=2)
        frame.alpha_composite(labels)
        buf = io.BytesIO()
        frame.convert("RGB").save(buf, "JPEG", quality=88, optimize=True)
        return buf.getvalue()
