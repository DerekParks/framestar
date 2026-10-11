import asyncio

import httpx
import pytest
import respx

from framestar.cams import fetch_snapshot, snapshot_url, youtube_id


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=yj-5Q1vBMaA", "yj-5Q1vBMaA"),
        ("https://youtu.be/yj-5Q1vBMaA", "yj-5Q1vBMaA"),
        ("https://www.youtube.com/embed/yj-5Q1vBMaA?autoplay=1", "yj-5Q1vBMaA"),
        ("https://youtube.com/live/yj-5Q1vBMaA", "yj-5Q1vBMaA"),
        ("https://www.youtube.com/watch?v=short", None),
        ("https://cams.winterparkresort.com/best-western-cam.jpg", None),
    ],
)
def test_youtube_id(url, expected):
    assert youtube_id(url) == expected


@respx.mock
def test_camstreamer_resolves_to_live_thumbnail():
    respx.get("https://camstreamer.com/embed/abc").respond(
        text='<script>x = "https://www.youtube.com/embed/HfX4H3MSwXs?autoplay\\u003d1"</script>'
    )

    async def run():
        async with httpx.AsyncClient() as client:
            return await snapshot_url(client, "https://camstreamer.com/embed/abc")

    assert asyncio.run(run()) == "https://i.ytimg.com/vi/HfX4H3MSwXs/maxresdefault_live.jpg"


@respx.mock
def test_camstreamer_without_stream_raises():
    respx.get("https://camstreamer.com/embed/gone").respond(text="<html>offline</html>")

    async def run():
        async with httpx.AsyncClient() as client:
            await snapshot_url(client, "https://camstreamer.com/embed/gone")

    with pytest.raises(ValueError, match="no YouTube stream"):
        asyncio.run(run())


def test_direct_image_passes_through():
    async def run():
        async with httpx.AsyncClient() as client:
            return await snapshot_url(client, "https://cams.example.com/cam.jpg")

    assert asyncio.run(run()) == "https://cams.example.com/cam.jpg"


@respx.mock
def test_fetch_snapshot_rejects_html():
    respx.get("https://cams.example.com/cam.jpg").respond(text="<html>maintenance</html>")

    async def run():
        async with httpx.AsyncClient() as client:
            await fetch_snapshot(client, "https://cams.example.com/cam.jpg")

    with pytest.raises(ValueError, match="not an image"):
        asyncio.run(run())
