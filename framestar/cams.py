from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

import httpx

YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
EMBEDDED_YOUTUBE = re.compile(r"youtube(?:-nocookie)?\.com/embed/([A-Za-z0-9_-]{11})")
LIVE_THUMBNAIL = "https://i.ytimg.com/vi/{video_id}/maxresdefault_live.jpg"


def youtube_id(url: str) -> str | None:
    parts = urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.").removeprefix("m.")
    candidate = None
    if host == "youtu.be":
        candidate = parts.path.strip("/")
    elif host in ("youtube.com", "youtube-nocookie.com"):
        if parts.path == "/watch":
            candidate = parse_qs(parts.query).get("v", [None])[0]
        elif parts.path.startswith(("/embed/", "/live/")):
            candidate = parts.path.split("/")[2]
    return candidate if candidate and YOUTUBE_ID.match(candidate) else None


def is_camstreamer(url: str) -> bool:
    parts = urlsplit(url)
    return parts.netloc.lower().removeprefix("www.") == "camstreamer.com" and parts.path.startswith("/embed/")


async def snapshot_url(client: httpx.AsyncClient, url: str) -> str:
    """Still-image URL for a cam given as a direct image, a YouTube link, or a camstreamer embed."""
    if video_id := youtube_id(url):
        return LIVE_THUMBNAIL.format(video_id=video_id)
    if is_camstreamer(url):
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        match = EMBEDDED_YOUTUBE.search(response.text)
        if match is None:
            raise ValueError(f"no YouTube stream found in {url}")
        return LIVE_THUMBNAIL.format(video_id=match.group(1))
    return url


async def fetch_snapshot(client: httpx.AsyncClient, image_url: str) -> bytes:
    response = await client.get(image_url, follow_redirects=True)
    response.raise_for_status()
    if not response.headers.get("content-type", "").startswith("image/"):
        raise ValueError(f"{image_url} is not an image")
    return response.content
