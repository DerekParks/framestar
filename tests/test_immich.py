import asyncio

import httpx
import respx

from framestar.config import Immich
from framestar.immich import ImmichShare, photos_from_bucket

BASE = "https://photos.example.com"


def test_columnar_bucket_filters_videos_and_trash():
    bucket = {
        "id": ["a", "b", "c"],
        "isImage": [True, False, True],
        "isTrashed": [False, False, True],
        "fileCreatedAt": ["2025-07-04T18:00:00Z", None, None],
        "city": ["Fraser", None, None],
    }
    photos = photos_from_bucket(bucket)
    assert [(p.id, p.city) for p in photos] == [("a", "Fraser")]


def test_legacy_array_bucket():
    bucket = [
        {"id": "a", "type": "IMAGE", "fileCreatedAt": "2024-01-01T00:00:00Z", "exifInfo": {"city": "Norman"}},
        {"id": "b", "type": "VIDEO"},
    ]
    assert [p.id for p in photos_from_bucket(bucket)] == ["a"]


@respx.mock
def test_album_share_walks_timeline_buckets():
    respx.get(f"{BASE}/api/shared-links/me", params={"key": "k1"}).respond(
        json={"type": "ALBUM", "assets": [], "album": {"id": "alb"}}
    )
    respx.get(f"{BASE}/api/timeline/buckets", params={"albumId": "alb", "key": "k1"}).respond(
        json=[{"timeBucket": "2026-09-01", "count": 2}, {"timeBucket": "2025-07-01", "count": 1}]
    )
    respx.get(f"{BASE}/api/timeline/bucket", params={"timeBucket": "2026-09-01"}).respond(
        json={"id": ["a", "b"], "isImage": [True, True], "isTrashed": [False, False]}
    )
    respx.get(f"{BASE}/api/timeline/bucket", params={"timeBucket": "2025-07-01"}).respond(
        json={"id": ["c", "a"], "isImage": [True, True], "isTrashed": [False, False]}
    )

    async def run():
        async with httpx.AsyncClient() as client:
            return await ImmichShare(client, Immich(share_url=f"{BASE}/share/k1")).photos()

    assert [p.id for p in asyncio.run(run())] == ["a", "b", "c"]


@respx.mock
def test_individual_share_uses_link_assets_and_slug():
    respx.get(f"{BASE}/api/shared-links/me", params={"slug": "frame"}).respond(
        json={"type": "INDIVIDUAL", "assets": [{"id": "x", "type": "IMAGE"}], "album": None}
    )

    async def run():
        async with httpx.AsyncClient() as client:
            return await ImmichShare(client, Immich(share_url=f"{BASE}/s/frame")).photos()

    assert [p.id for p in asyncio.run(run())] == ["x"]


@respx.mock
def test_password_share_logs_in_and_relogs_on_expiry():
    logins = iter(["tok1", "tok2"])
    login = respx.post(f"{BASE}/api/shared-links/login", params={"key": "k1"}).mock(
        side_effect=lambda request: httpx.Response(
            201, json={}, headers={"set-cookie": f"immich_shared_link_token={next(logins)}; Path=/; HttpOnly"}
        )
    )
    seen_cookies = []

    def me(request):
        cookie = request.headers.get("cookie", "")
        seen_cookies.append(cookie)
        if cookie == "immich_shared_link_token=tok2":
            return httpx.Response(200, json={"assets": [{"id": "x", "type": "IMAGE"}], "album": None})
        return httpx.Response(401, json={"message": "Invalid share key"})

    respx.get(f"{BASE}/api/shared-links/me").mock(side_effect=me)

    async def run():
        async with httpx.AsyncClient() as client:
            share = ImmichShare(client, Immich(share_url=f"{BASE}/share/k1", password="pw"))
            return await share.photos()

    assert [p.id for p in asyncio.run(run())] == ["x"]
    assert login.call_count == 2
    assert login.calls[0].request.content == b'{"password":"pw"}'
    assert seen_cookies == ["immich_shared_link_token=tok1", "immich_shared_link_token=tok2"]


def test_fill_frame_letterboxes_portrait_onto_backdrop():
    import io

    from PIL import Image

    from framestar.immich import fill_frame

    src = io.BytesIO()
    Image.new("RGB", (600, 900), (250, 20, 20)).save(src, "JPEG")
    framed = Image.open(io.BytesIO(fill_frame(src.getvalue())))
    assert framed.size == (1280, 800)
    center = framed.getpixel((640, 400))
    edge = framed.getpixel((5, 400))
    assert center[0] > 200
    assert 0 < edge[0] < 150
