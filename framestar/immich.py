from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

from framestar.imaging import fill_frame

from framestar.config import Immich


@dataclass(frozen=True)
class Photo:
    id: str
    taken_at: str | None
    city: str | None


@dataclass(frozen=True)
class Image:
    content: bytes
    media_type: str


def _from_asset_dto(asset: dict) -> Photo | None:
    if asset.get("type") != "IMAGE" or asset.get("isTrashed"):
        return None
    exif = asset.get("exifInfo") or {}
    return Photo(id=asset["id"], taken_at=asset.get("fileCreatedAt"), city=exif.get("city"))


def photos_from_bucket(bucket: dict | list) -> list[Photo]:
    if isinstance(bucket, list):
        return [p for p in map(_from_asset_dto, bucket) if p is not None]
    ids = bucket.get("id", [])
    is_image = bucket.get("isImage", [True] * len(ids))
    trashed = bucket.get("isTrashed", [False] * len(ids))
    taken = bucket.get("fileCreatedAt", [None] * len(ids))
    city = bucket.get("city", [None] * len(ids))
    return [
        Photo(id=ids[i], taken_at=taken[i], city=city[i])
        for i in range(len(ids))
        if is_image[i] and not trashed[i]
    ]


SESSION_COOKIE = "immich_shared_link_token"


class ImmichShare:
    def __init__(self, client: httpx.AsyncClient, immich: Immich):
        self._client = client
        self._base = immich.base_url
        self._auth = immich.auth_params
        self._password = immich.password
        self._session: str | None = None
        self._login_lock = asyncio.Lock()

    async def _login(self, stale: str | None) -> None:
        async with self._login_lock:
            if self._session != stale:
                return
            response = await self._client.post(
                f"{self._base}/api/shared-links/login", params=self._auth, json={"password": self._password}
            )
            response.raise_for_status()
            token = response.cookies.get(SESSION_COOKIE)
            if not token:
                raise RuntimeError(f"Immich login set no {SESSION_COOKIE} cookie")
            self._session = token

    async def _send(self, path: str, params: dict) -> tuple[httpx.Response, str | None]:
        session = self._session
        headers = {"Cookie": f"{SESSION_COOKIE}={session}"} if session else None
        response = await self._client.get(f"{self._base}/api{path}", params={**params, **self._auth}, headers=headers)
        return response, session

    async def _get(self, path: str, **params) -> httpx.Response:
        if self._password is not None and self._session is None:
            await self._login(None)
        response, session = await self._send(path, params)
        if response.status_code == 401 and self._password is not None:
            await self._login(session)
            response, _ = await self._send(path, params)
        response.raise_for_status()
        return response

    async def photos(self) -> list[Photo]:
        link = (await self._get("/shared-links/me")).json()
        direct = [p for p in map(_from_asset_dto, link.get("assets") or []) if p is not None]
        album = link.get("album")
        if album is None:
            return direct
        buckets = (await self._get("/timeline/buckets", albumId=album["id"])).json()
        pages = await asyncio.gather(
            *(self._get("/timeline/bucket", albumId=album["id"], timeBucket=b["timeBucket"]) for b in buckets)
        )
        seen = {p.id for p in direct}
        photos = list(direct)
        for page in pages:
            for photo in photos_from_bucket(page.json()):
                if photo.id not in seen:
                    seen.add(photo.id)
                    photos.append(photo)
        return photos

    async def preview(self, asset_id: str) -> Image:
        response = await self._get(f"/assets/{asset_id}/thumbnail", size="preview")
        framed = await asyncio.to_thread(fill_frame, response.content)
        return Image(framed, "image/jpeg")
