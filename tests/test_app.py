import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from framestar.app import create_app


@pytest.fixture
def client(example_config):
    with TestClient(create_app(example_config, httpx.AsyncClient()), base_url="http://frame-server.lan:8000") as c:
        yield c


def test_config_builds_ws4kp_src_for_requesting_host(client):
    body = client.get("/api/config").json()
    ws = [s for s in body["slides"] if s["type"] == "ws4kp"]
    assert [s["name"] for s in ws] == ["Denver", "Fraser", "Norman"]
    src = ws[0]["src"]
    assert src.startswith("http://frame-server.lan:8080/?kiosk=true&wide=true")
    assert "latLon=%7B%22lat%22%3A39.7392%2C%22lon%22%3A-104.9903%7D" in src
    assert "latLonQuery=Denver" in src
    assert body["features"] == {"tempest": True, "calendar": True}


def test_index_and_assets_served(client):
    assert "app.js" in client.get("/").text
    assert client.get("/fonts/Star4000.woff").status_code == 200
    assert client.get("/icons/Sunny.gif").status_code == 200


def test_photo_id_must_be_uuid(client):
    assert client.get("/api/photos/..%2Fadmin").status_code in (404, 422)
    assert client.get("/api/photos/not-a-uuid").status_code == 422


def test_radar_frame_validation(client):
    assert client.get("/api/radar/nowhere").status_code == 404
    assert client.get("/api/radar/front_range/202610111503.jpg").status_code == 400
    assert client.get("/api/radar/front_range/200001010000.jpg").status_code == 400


@respx.mock
def test_calendar_survives_one_failed_feed(client, example_config):
    good, bad = example_config.calendars
    respx.get(good.url).respond(content=b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//t//EN\nEND:VCALENDAR\n")
    respx.get(bad.url).respond(status_code=404)
    body = client.get("/api/calendar").json()
    assert body["errors"] == ["Work"]
    assert len(body["days"]) == 7


@respx.mock
def test_radar_frames_listing(client):
    respx.get("https://mesonet.agron.iastate.edu/data/gis/images/4326/USCOMP/n0q_0.json").respond(
        json={"meta": {"valid": "2026-10-11T15:10:00Z"}}
    )
    body = client.get("/api/radar/front_range").json()
    assert body["name"] == "Front Range"
    assert body["frames"][-1]["url"] == "/api/radar/front_range/202610111510.jpg"
    assert len(body["frames"]) == 12
