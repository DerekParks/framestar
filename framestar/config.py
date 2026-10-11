from __future__ import annotations

import re
from datetime import time
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class Location(BaseModel):
    name: str
    lat: float
    lon: float


class CalendarFeed(BaseModel):
    name: str
    url: str
    color: str = "#ffff00"

    @field_validator("color")
    @classmethod
    def six_digit_hex(cls, v: str) -> str:
        if not HEX_COLOR.match(v):
            raise ValueError("color must be #rrggbb; WebView 106 mangles other hex forms")
        return v


class Tempest(BaseModel):
    station_id: int
    token: str
    name: str = "Tempest"


class Immich(BaseModel):
    share_url: str = Field(description="Public share link, e.g. https://photos.example.com/share/<key> or /s/<slug>")
    password: str | None = None
    shuffle: bool = True

    @property
    def base_url(self) -> str:
        parts = urlsplit(self.share_url)
        return f"{parts.scheme}://{parts.netloc}"

    @property
    def auth_params(self) -> dict[str, str]:
        path = urlsplit(self.share_url).path.strip("/").split("/")
        if len(path) == 2 and path[0] == "share":
            return {"key": path[1]}
        if len(path) == 2 and path[0] == "s":
            return {"slug": path[1]}
        raise ValueError(f"unrecognised Immich share URL: {self.share_url}")


class Cam(BaseModel):
    name: str
    url: str = Field(description="Direct image URL, YouTube live URL, or camstreamer.com embed URL")


class QuietHours(BaseModel):
    start: time
    end: time

    @field_validator("start", "end", mode="before")
    @classmethod
    def quoted_clock_time(cls, v: object) -> object:
        if isinstance(v, (str, time)):
            return v
        raise ValueError('write clock times as quoted strings, e.g. "22:00"; YAML reads a bare 22:00 as the number 1320')


class RadarMap(BaseModel):
    name: str
    lat: float
    lon: float
    zoom: int = Field(7, ge=3, le=10)
    markers: list[str] = Field(default_factory=list, description="Location keys to pin on the map")


class CalendarSlide(BaseModel):
    type: Literal["calendar"]
    seconds: int = 30
    title: list[str] = Field(default_factory=lambda: ["Upcoming", "Events"], min_length=1, max_length=2)
    calendars: list[str] | None = Field(None, description="Calendar names to show; all when omitted")


class Ws4kpSlide(BaseModel):
    type: Literal["ws4kp"]
    location: str
    seconds: int = 120
    params: dict[str, str] = Field(default_factory=dict, description="Extra ws4kp permalink params, e.g. radar: 'false'")


class TempestSlide(BaseModel):
    type: Literal["tempest"]
    seconds: int = 20


class PhotosSlide(BaseModel):
    type: Literal["photos"]
    count: int = Field(5, ge=1)
    seconds_each: int = Field(8, ge=1)


class RadarSlide(BaseModel):
    type: Literal["radar"]
    map: str
    seconds: int = 20


class CamsSlide(BaseModel):
    type: Literal["cams"]
    count: int = Field(2, ge=1)
    seconds_each: int = Field(10, ge=1)


Slide = Annotated[
    CalendarSlide | Ws4kpSlide | TempestSlide | PhotosSlide | RadarSlide | CamsSlide,
    Field(discriminator="type"),
]


class Config(BaseModel):
    title: str = "Framestar"
    timezone: str = "America/Denver"
    ws4kp_url: str = Field(
        "http://{host}:8080/",
        description="ws4kp base URL as the frame sees it; {host} becomes the hostname the frame used to reach framestar",
    )
    ws4kp_defaults: dict[str, str] = Field(
        default_factory=lambda: {"kiosk": "true", "wide": "true", "scanLines": "false", "units-select": "us"}
    )
    calendar_days: int = 7
    calendars: list[CalendarFeed] = Field(default_factory=list)
    locations: dict[str, Location] = Field(default_factory=dict)
    tempest: Tempest | None = None
    immich: Immich | None = None
    radar_maps: dict[str, RadarMap] = Field(default_factory=dict)
    cams: list[Cam] = Field(default_factory=list)
    quiet_hours: QuietHours | None = Field(None, description="Local times the display goes dark, e.g. 22:00 to 07:00")
    slides: list[Slide]

    @field_validator("timezone")
    @classmethod
    def known_zone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError as e:
            raise ValueError(f"unknown time zone {v!r}") from e
        return v

    @model_validator(mode="after")
    def references_resolve(self) -> Config:
        for slide in self.slides:
            match slide:
                case Ws4kpSlide(location=key) if key not in self.locations:
                    raise ValueError(f"ws4kp slide references unknown location {key!r}")
                case RadarSlide(map=key) if key not in self.radar_maps:
                    raise ValueError(f"radar slide references unknown radar map {key!r}")
                case TempestSlide() if self.tempest is None:
                    raise ValueError("tempest slide needs a tempest: section")
                case PhotosSlide() if self.immich is None:
                    raise ValueError("photos slide needs an immich: section")
                case CalendarSlide() if not self.calendars:
                    raise ValueError("calendar slide needs at least one calendar")
                case CalendarSlide(calendars=names) if names and set(names) - {c.name for c in self.calendars}:
                    unknown = sorted(set(names) - {c.name for c in self.calendars})
                    raise ValueError(f"calendar slide references unknown calendars {unknown}")
                case CamsSlide() if not self.cams:
                    raise ValueError("cams slide needs at least one cam")
        for radar in self.radar_maps.values():
            unknown = set(radar.markers) - set(self.locations)
            if unknown:
                raise ValueError(f"radar map {radar.name!r} has unknown markers {sorted(unknown)}")
        if self.immich is not None:
            self.immich.auth_params
        return self

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def load_config(path: Path) -> Config:
    return Config.model_validate(yaml.safe_load(path.read_text()))
