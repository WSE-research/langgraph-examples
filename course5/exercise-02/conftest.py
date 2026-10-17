"""Makes `pytest -q` work from the repository root, and runs the Iteration 2 suite twice.

The first job is unchanged from Iteration 1: pytest inserts this directory into
`sys.path`, so `from pizzabot import ...` resolves.

The second job is new. The fixture `configuration` is parametrised over the two
configurations of the process, so every test that asks for `implementation`
(tests/test_both_configurations.py) runs once with the Iteration 1 rules and
once with the LLM-backed components. The tests themselves do not change -- that
is the point: if a test had to know which implementation runs, the contract
would have leaked into the test. (pytest docs: "Parametrizing fixtures",
https://docs.pytest.org/en/stable/how-to/fixtures.html#parametrizing-fixtures)

Without the LLM endpoint in `.env` the LLM half is skipped, not failed: the static
configuration must stay green on a machine that has no access to the model.
The summary line printed after the dots says how the two halves did.
"""

from __future__ import annotations

import os

# The tests order fixed pizzas. From Pizza API version v5 on, two pizzas are sold
# out every minute (POST /order answers 409); v2, which this exercise uses,
# never sells out. A test driver opts out of that draw with the header
# X-Accept-Everything: true, which pizzabot/pizza_api.py sends when this is
# set -- so a result never depends on the minute, whichever version it meets.
os.environ.setdefault("PIZZA_API_ACCEPT_EVERYTHING", "true")

import pytest

from pizzabot import config, llm_service


@pytest.fixture(scope="session", params=[config.STATIC, config.LLM])
def configuration(request) -> str:
    """The name of the configuration under test: "static" or "llm"."""
    if request.param == config.LLM and not llm_service.configured():
        pytest.skip(f"the LLM configuration needs {', '.join(llm_service.missing())} in .env (provided on-site)")
    return request.param


@pytest.fixture(scope="session")
def implementation(configuration: str) -> dict:
    """The implementation dictionary of that configuration (see pizzabot/config.py)."""
    return config.implementations(configuration)


def pytest_terminal_summary(terminalreporter, exitstatus, config):  # noqa: ARG001
    """One line that says what the sheet asks for: green in both configurations?"""
    counts = {"static": {}, "llm": {}, "other": {}}
    for outcome in ("passed", "failed", "skipped"):
        for report in terminalreporter.stats.get(outcome, []):
            nodeid = getattr(report, "nodeid", "")
            key = "static" if "[static" in nodeid else "llm" if "[llm" in nodeid else "other"
            counts[key][outcome] = counts[key].get(outcome, 0) + 1

    def fmt(name):
        c = counts[name]
        if not c:
            return f"{name}: no tests"
        parts = [f"{n} {o}" for o, n in c.items()]
        return f"{name}: " + ", ".join(parts)

    line = " | ".join([fmt("static"), fmt("llm"), fmt("other").replace("other", "not parametrized")])
    if counts["llm"].get("skipped") and not counts["llm"].get("passed"):
        line += "   (llm skipped: the LLM endpoint is not configured in .env)"
    terminalreporter.write_sep("-", "configurations")
    terminalreporter.write_line(line)
