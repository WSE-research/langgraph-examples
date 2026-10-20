"""Fixtures: the catalog, and the configuration under test.

`catalog` is the in-process graph -- the default path, no server, no network.
`endpoint` starts `benchmark.server` on a free port for the tests that check the
HTTP path. Both are session-scoped: the graph is parsed once per run.

`implementations` is the seam of Iteration 2, as a fixture: which implementation
sits behind each component name. It follows `BOT_CONFIG`, so the same test file
measures both configurations without being edited::

    pytest -q                      # static -- the Iteration 1 rules, no LLM endpoint needed
    BOT_CONFIG=llm pytest -q       # the LLM-backed implementations

`implementation` (singular) is Iteration 2's fixture, parametrized over both
configurations; it is here so that the Iteration 2 tests of a team that copies
this file into its repository keep running.
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
    """Component name -> the function that implements it, for this configuration.

    `BOT_CONFIG=llm` without an endpoint skips instead of running: the LLM-backed
    components would fall back to the rules on every case, and the tests would
    measure the rule under the LLM's name.
    """
    from pizzabot import config, llm_service

    if configuration == config.LLM and not llm_service.configured():
        pytest.skip(f"BOT_CONFIG=llm needs {', '.join(llm_service.missing())} in .env (provided on-site) "
                    f"-- without them every answer would come from the rule")
    return config.implementations(configuration)


#: What tests/test_manual_cases.py reports: the rate over the hand-written cases.
MANUAL_REPORT: list[str] = []


@pytest.fixture(scope="session")
def manual_report() -> list[str]:
    return MANUAL_REPORT


def pytest_terminal_summary(terminalreporter, exitstatus, config):  # noqa: ARG001
    """Print the hand-written cases, case by case, after the dots -- no `-s` needed."""
    if MANUAL_REPORT:
        terminalreporter.section("your hand-written cases (Task 2): the rate, reported")
        for line in MANUAL_REPORT:
            terminalreporter.write_line(line)


@pytest.fixture(scope="session", params=["static", "llm"])
def implementation(request) -> dict:
    """Iteration 2's fixture, kept on purpose: the same tests, once per configuration.

    Your Iteration 2 repository has `tests/test_both_configurations.py`, which asks
    for it. Copying this file over the Iteration 2 `conftest.py` must not turn
    those tests red -- so the fixture moved here, unchanged: the LLM half is
    skipped, not failed, while the endpoint is not configured.
    """
    from pizzabot import config, llm_service

    if request.param == config.LLM and not llm_service.configured():
        pytest.skip(f"the LLM configuration needs {', '.join(llm_service.missing())} in .env (provided on-site)")
    return config.implementations(request.param)
