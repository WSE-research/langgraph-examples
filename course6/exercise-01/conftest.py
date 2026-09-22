"""Makes `pytest -q` work from the repository root.

pytest inserts the directory of the topmost conftest.py into `sys.path`, which
is how `from pizzabot import ...` resolves in tests/test_contracts.py. Without
this file only `python -m pytest` works (that form adds the current directory
itself), and the two commands would behave differently -- exactly the kind of
difference that costs twenty minutes in a session.
"""

import os

# The tests order fixed pizzas, and since Pizza API 1.3.0 two pizzas are sold out
# every minute (POST /order answers 409). A test driver opts out of that draw with
# the header X-Accept-Everything: true, which pizzabot/pizza_api.py sends when this
# is set -- so a result does not depend on the minute the suite runs in.
os.environ.setdefault("PIZZA_API_ACCEPT_EVERYTHING", "true")
