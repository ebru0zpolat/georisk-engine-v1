"""Fixture loading; deliberately performs no network access."""

import json
from pathlib import Path

FIXTURES = Path(__file__).with_name("fixtures")


def load_scenario(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())
