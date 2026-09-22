"""Iteration 4 fixtures. GIVEN -- drop this file into your `tests/` directory.

Nothing to merge: pytest reads the `conftest.py` at your repository root (the
Iteration 3 one, with `configuration` and `implementations`) **and** this one,
and the fixtures of both are available to every test under `tests/`.

Two fixtures, and both exist for the same reason: **the tests drive the
compiled graph, not the individual functions.** A test that calls
`answer_question(state)` measures a function. A test that sends a sentence
through `build_graph()` measures the *process* -- the router rule, the skip
rules, the order of the nodes and the state they leave behind. Since everything
you build today is about which node runs when, the second is the only kind that
can fail for the right reason.

    bot          the compiled graph of the configuration under test
    fresh        a new dialog, so a test starts from nothing

Both configurations, same files, same cases::

    pytest -q                        # static -- no key needed
    BOT_CONFIG=llm pytest -q         # the LLM-backed implementations
"""

import os

# The tests order fixed pizzas, and since Pizza API 1.3.0 two pizzas are sold out
# every minute (POST /order answers 409). A test driver opts out of that draw with
# the header X-Accept-Everything: true, which pizzabot/pizza_api.py sends when this
# is set -- so a result does not depend on the minute the suite runs in.
os.environ.setdefault("PIZZA_API_ACCEPT_EVERYTHING", "true")

import pytest


@pytest.fixture(scope="session")
def bot(configuration):
    """The compiled graph of the configuration under test."""
    from pizzabot import config
    from pizzabot.graph import build_graph

    return build_graph(config.implementations(configuration))


@pytest.fixture
def fresh():
    """A new dialog. Function-scoped: no test may inherit another's state."""
    from pizzabot.state import new_state

    return new_state("")
