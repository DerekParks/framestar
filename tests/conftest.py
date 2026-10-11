from pathlib import Path

import pytest
import yaml

from framestar.config import Config

ROOT = Path(__file__).parent.parent


@pytest.fixture
def example_dict() -> dict:
    return yaml.safe_load((ROOT / "config.example.yaml").read_text())


@pytest.fixture
def example_config(example_dict) -> Config:
    return Config.model_validate(example_dict)
