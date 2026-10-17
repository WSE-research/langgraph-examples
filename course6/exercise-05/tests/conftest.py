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

    pytest -q                        # static -- no LLM endpoint needed
    BOT_CONFIG=llm pytest -q         # the LLM-backed implementations
"""

import os

# The tests order fixed pizzas, and in version v5 two pizzas are sold out every
# minute (POST /order answers 409). A test driver opts out of that draw with the
# header X-Accept-Everything: true, which pizzabot/pizza_api.py sends when this is
# set -- so a result does not depend on the minute the suite runs in.
os.environ.setdefault("PIZZA_API_ACCEPT_EVERYTHING", "true")

import pytest

# The Pizza API version is in the adapter, not in .env: this iteration ships
# pizzabot/pizza_api.py with VERSION = "v5", and copying it is what switches the
# version. A repository that still has the adapter of an earlier iteration would
# quietly test against the wrong service -- so the suite stops before the first
# test and says what to copy. A later adapter is fine: every later version serves
# what this one serves (Iteration 6 keeps these tests green against v6). A
# PIZZA_API_BASE left in .env from an earlier iteration is no danger either: the
# adapter ignores it and says so.
from pizzabot import pizza_api  # noqa: E402

_VERSION = str(getattr(pizza_api, "VERSION", "v0"))


def pytest_configure(config):
    """Stop before the first test -- whichever test file is run -- with the adapter of an earlier iteration."""
    if not _VERSION[1:].isdigit() or int(_VERSION[1:]) < 5:
        older = _VERSION if _VERSION != "v0" else "an earlier iteration"
        pytest.exit(f"pizzabot/pizza_api.py is the adapter of {older}, not of Iteration 5: "
                    f"copy it from exercise-05/pizzabot/pizza_api.py", returncode=4)


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
