"""Fixtures for the Pizza API tests.

    pip install -r requirements-service.txt -r requirements-test.txt
    pytest tests/                  # from common/

The tests run the service in-process (FastAPI's TestClient), so they need no
network and no running container. They cover three things:

    test_versions.py            every version keeps the contract it was published with
    test_exercise_material.py   every exercise names its version, and its data agree with it
    test_stubs.py               every exercise's offline stub answers like its version
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

COMMON = Path(__file__).resolve().parent.parent
REPO = COMMON.parent
sys.path.insert(0, str(COMMON))

import main  # noqa: E402  (after the path is set)

# The course folders whose exercises use the service -- course5 and course6
# (the Athens edition), the same six exercises with the same examples.
COURSES = [name for name in ("course5", "course6") if (REPO / name).is_dir()]

VERSION_KEYS = [version.key for version in main.VERSIONS]


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    return TestClient(main.app)


def base(key: str, prefixed: bool = True) -> str:
    """The path prefix of a version, as the proxy passes it (or as a direct call sends it)."""
    root = "/pizza-api" if prefixed else ""
    return root if key == "latest" else f"{root}/{key}"


@pytest.fixture
def minute(monkeypatch):
    """Pin the clock of the availability draw: minute(1234) makes it that minute."""
    def set_minute(value: int) -> int:
        monkeypatch.setattr(main, "current_minute", lambda: value)
        return value
    return set_minute


def validate(client, key: str, city: str, street: str = "Ermou", house_number: str = "5"):
    return client.post(f"{base(key)}/address/validate",
                       json={"city": city, "street": street, "house_number": house_number})


def order(client, key: str, pizza_id: int, city: str = "Athens", accept_everything: bool = False):
    headers = {"X-Accept-Everything": "true"} if accept_everything else {}
    return client.post(f"{base(key)}/order", headers=headers,
                       json={"pizza_id": pizza_id, "city": city, "street": "Ermou", "house_number": "5"})
