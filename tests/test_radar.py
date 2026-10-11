from datetime import UTC, datetime

import pytest

from framestar.radar import TILE, Viewport, frame_times, parse_stamp, world_pixel


def test_world_pixel_origin_and_known_point():
    assert world_pixel(0, 0, 0) == pytest.approx((128, 128))
    x, y = world_pixel(39.7392, -104.9903, 7)
    assert (int(x // TILE), int(y // TILE)) == (26, 48)


def test_viewport_tiles_cover_viewport():
    view = Viewport.centered(39.85, -105.3, 8, 1280, 610)
    placements = view.tiles()
    covered = set()
    for _, _, px, py in placements:
        for x in range(max(px, 0), min(px + TILE, view.width), 64):
            for y in range(max(py, 0), min(py + TILE, view.height), 61):
                covered.add((x // 64, y // 61))
    assert len(covered) == (1280 // 64) * (610 // 61)
    assert all(0 <= tx < 2**8 and 0 <= ty < 2**8 for tx, ty, _, _ in placements)


def test_project_center_is_middle():
    view = Viewport.centered(35.4, -97.5, 7, 1280, 610)
    x, y = view.project(35.4, -97.5)
    assert x == pytest.approx(640, abs=1)
    assert y == pytest.approx(305, abs=1)


def test_frame_times_oldest_first_hour_long():
    latest = datetime(2026, 10, 11, 15, 10, tzinfo=UTC)
    times = frame_times(latest)
    assert len(times) == 12
    assert times[-1] == latest
    assert times[0] == datetime(2026, 10, 11, 14, 15, tzinfo=UTC)


def test_parse_stamp():
    assert parse_stamp("202610111505") == datetime(2026, 10, 11, 15, 5, tzinfo=UTC)
    with pytest.raises(ValueError):
        parse_stamp("202610111503")
    with pytest.raises(ValueError):
        parse_stamp("../../etc")
