import pytest
from pydantic import ValidationError

from framestar.config import Config, Immich


def test_example_config_is_valid(example_config):
    assert example_config.tz.key == "America/Denver"
    assert [s.type for s in example_config.slides][:3] == ["calendar", "ws4kp", "tempest"]


def test_unknown_location_rejected(example_dict):
    example_dict["slides"].append({"type": "ws4kp", "location": "dia"})
    with pytest.raises(ValidationError, match="unknown location 'dia'"):
        Config.model_validate(example_dict)


def test_unknown_radar_marker_rejected(example_dict):
    example_dict["radar_maps"]["front_range"]["markers"].append("boulder")
    with pytest.raises(ValidationError, match="boulder"):
        Config.model_validate(example_dict)


def test_tempest_slide_requires_tempest(example_dict):
    del example_dict["tempest"]
    with pytest.raises(ValidationError, match="tempest"):
        Config.model_validate(example_dict)


@pytest.mark.parametrize("color", ["#fff", "#ffffffbf", "gold"])
def test_calendar_color_must_be_six_digit_hex(example_dict, color):
    example_dict["calendars"][0]["color"] = color
    with pytest.raises(ValidationError, match="rrggbb"):
        Config.model_validate(example_dict)


def test_bad_timezone_rejected(example_dict):
    example_dict["timezone"] = "Mountain/Nowhere"
    with pytest.raises(ValidationError):
        Config.model_validate(example_dict)


@pytest.mark.parametrize(
    ("url", "base", "params"),
    [
        ("https://photos.example.com/share/abc123", "https://photos.example.com", {"key": "abc123"}),
        ("http://immich.lan:2283/s/family-frame/", "http://immich.lan:2283", {"slug": "family-frame"}),
    ],
)
def test_immich_share_url_parsing(url, base, params):
    immich = Immich(share_url=url)
    assert immich.base_url == base
    assert immich.auth_params == params


def test_immich_bad_share_url_rejected(example_dict):
    example_dict["immich"]["share_url"] = "https://photos.example.com/albums/123"
    with pytest.raises(ValidationError, match="unrecognised Immich share URL"):
        Config.model_validate(example_dict)


def test_quiet_hours_rejects_unquoted_yaml_time():
    import yaml

    from framestar.config import QuietHours

    with pytest.raises(ValidationError, match="quoted"):
        QuietHours.model_validate(yaml.safe_load("start: 22:00\nend: 07:00"))
    assert QuietHours.model_validate(yaml.safe_load('start: "22:00"\nend: "07:00"')).start.hour == 22


@pytest.mark.parametrize("field", ["count", "seconds_each"])
def test_gallery_slides_need_positive_counts(example_dict, field):
    cams = next(s for s in example_dict["slides"] if s["type"] == "cams")
    cams[field] = 0
    with pytest.raises(ValidationError, match=field):
        Config.model_validate(example_dict)


def test_cams_slide_requires_cams(example_dict):
    del example_dict["cams"]
    with pytest.raises(ValidationError, match="cams slide"):
        Config.model_validate(example_dict)
