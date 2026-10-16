"""Makes `pytest -q` work from the repository root.

pytest inserts the directory of the topmost conftest.py into `sys.path`, which
is how `from pizzabot import ...` resolves in tests/test_contracts.py. Without
this file only `python -m pytest` works (that form adds the current directory
itself), and the two commands would behave differently -- exactly the kind of
difference that costs twenty minutes in a session.
"""

import os

# The tests order fixed pizzas. From Pizza API version v5 on, two pizzas are sold
# out every minute (POST /order answers 409); v1, which this exercise uses,
# never sells out. A test driver opts out of that draw with the header
# X-Accept-Everything: true, which pizzabot/pizza_api.py sends when this is
# set -- so a result never depends on the minute, whichever version it meets.
os.environ.setdefault("PIZZA_API_ACCEPT_EVERYTHING", "true")
