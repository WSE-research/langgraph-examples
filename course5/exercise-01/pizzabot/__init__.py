"""Exercise 1 -- static pizza-ordering bot built from contract-bound components.

Importing this package reads `.env` (if there is one), so that every script in
the repository sees the same configuration -- `PIZZA_API_BASE`, `LOG_LEVEL`.
Real environment variables always win over the file, so a one-off

    PIZZA_API_BASE=http://127.0.0.1:8000 python run_dialog.py

still overrides what `.env` says.
"""

try:
    from dotenv import load_dotenv

    load_dotenv()          # no-op when python-dotenv or the file is missing
except ImportError:        # the package is optional; the exercise works without it
    pass
