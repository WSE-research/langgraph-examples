"""Exercises 1 and 2 -- a pizza-ordering bot built from contract-bound components, in two configurations.

Importing this package reads `.env` (if there is one), so that every script in
the repository sees the same configuration -- `PIZZA_API_BASE`, `LOG_LEVEL`,
and from Iteration 2 on `OPENAI_API_KEY`, `MODEL_NAME`, `BOT_CONFIG`.
Real environment variables always win over the file, so a one-off

    PIZZA_API_BASE=http://127.0.0.1:8000 python run_dialog.py

still overrides what `.env` says.
"""

try:
    from dotenv import load_dotenv

    load_dotenv()          # no-op when python-dotenv or the file is missing
except ImportError:        # the package is optional; the exercise works without it
    pass
