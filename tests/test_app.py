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


def test_config_exposes_quiet_hours(client):
    assert client.get("/api/config").json()["quiet_hours"] == {"start": "22:00", "end": "07:00"}


def test_cams_rotate_round_robin(client, example_config):
    names = [c.name for c in example_config.cams]
    first = [c["name"] for c in client.get("/api/cams?count=4").json()["cams"]]
    second = [c["name"] for c in client.get("/api/cams?count=4").json()["cams"]]
    assert first + second == (names + names)[:8]
    assert client.get("/api/cams/99.jpg").status_code == 404


@respx.mock
def test_cam_image_is_framed(client, example_config):
    import io

    from PIL import Image

    src = io.BytesIO()
    Image.new("RGB", (1920, 1080), (10, 120, 200)).save(src, "JPEG")
    town = len(example_config.cams) - 1
    respx.get(example_config.cams[town].url).respond(content=src.getvalue(), headers={"content-type": "image/jpeg"})
    response = client.get(f"/api/cams/{town}.jpg")
    assert response.status_code == 200
    assert Image.open(io.BytesIO(response.content)).size == (1280, 800)


@respx.mock
def test_cam_re_resolves_source_when_snapshot_fails(client, example_config):
    import io

    from PIL import Image

    src = io.BytesIO()
    Image.new("RGB", (640, 360), (5, 5, 5)).save(src, "JPEG")
    embed = example_config.cams[0].url
    embeds = iter(["deadvideo01", "livevideo01"])
    respx.get(embed).mock(side_effect=lambda req: httpx.Response(200, text=f"youtube.com/embed/{next(embeds)}"))
    respx.get("https://i.ytimg.com/vi/deadvideo01/maxresdefault_live.jpg").respond(404)
    respx.get("https://i.ytimg.com/vi/livevideo01/maxresdefault_live.jpg").respond(
        content=src.getvalue(), headers={"content-type": "image/jpeg"}
    )
    assert client.get("/api/cams/0.jpg").status_code == 200


@respx.mock
def test_calendar_filters_by_name(client, example_config):
    empty = b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//t//EN\nEND:VCALENDAR\n"
    for feed in example_config.calendars:
        respx.get(feed.url).respond(content=empty)
    body = client.get("/api/calendar", params={"names": ["Work"]}).json()
    assert [c["name"] for c in body["calendars"]] == ["Work"]
    assert client.get("/api/calendar", params={"names": ["Nope"]}).status_code == 404
