"""Fixtures: the catalog, and the configuration under test.

`catalog` is the in-process graph -- the default path, no server, no network.
`endpoint` starts `benchmark.server` on a free port for the tests that check the
HTTP path. Both are session-scoped: the graph is parsed once per run.

`implementations` is the seam of Iteration 2, as a fixture: which implementation
sits behind each component name. It follows `BOT_CONFIG`, so the same test file
measures both configurations without being edited::

    pytest -q                      # static -- the Iteration 1 rules, no LLM endpoint needed
    BOT_CONFIG=llm pytest -q       # the LLM-backed implementations
"""

import os

import pytest

from benchmark import Catalog
from benchmark.server import serve

# The tests order fixed pizzas. From Pizza API version v5 on, two pizzas are sold
# out every minute (POST /order answers 409); v3, which this exercise uses,
# never sells out. A test driver opts out of that draw with the header
# X-Accept-Everything: true, which pizzabot/pizza_api.py sends when this is
# set -- so a result never depends on the minute, whichever version it meets.
os.environ.setdefault("PIZZA_API_ACCEPT_EVERYTHING", "true")


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    return Catalog()


@pytest.fixture(scope="session")
def endpoint(catalog):
    running = serve(catalog)
    yield running
    running.stop()


@pytest.fixture(scope="session")
def configuration() -> str:
    """Which configuration this run measures: `BOT_CONFIG`, or static."""
    return (os.environ.get("BOT_CONFIG") or "static").lower()


@pytest.fixture(scope="session")
def implementations(configuration) -> dict:
    """Component name -> the function that implements it, for this configuration."""
    from pizzabot import config

    return config.implementations(configuration)
