"""Makes `pytest -q` work from the repository root.

pytest inserts the directory of the topmost conftest.py into `sys.path`, which
is how `from pizzabot import ...` resolves in tests/test_contracts.py. Without
this file only `python -m pytest` works (that form adds the current directory
itself), and the two commands would behave differently -- exactly the kind of
difference that costs twenty minutes in a session.
"""
