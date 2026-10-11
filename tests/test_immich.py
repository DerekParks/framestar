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
