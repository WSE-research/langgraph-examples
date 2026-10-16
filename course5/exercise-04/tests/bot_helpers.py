"""Helpers the Iteration 4 test files share. GIVEN -- next to them in `tests/`.

Plain functions, no fixtures: `from bot_helpers import say, spoken`.

The rule they encode is worth naming, because it is what makes these tests
useful rather than annoying: **they assert on facts, never on your wording.**
`spoken()` lower-cases everything the bot said so a test can ask whether a name
is in it; the exact sentence around that name is yours to write and yours to
change.
"""

import os


def say(bot, state: dict, utterance: str) -> dict:
    """One user turn through the graph -- exactly what `run_dialog.py` does."""
    return bot.invoke({**state, "input": utterance})


def spoken(state: dict, since: int = 0) -> str:
    """Everything the bot said from message `since` on, as one lower-cased string."""
    return " ".join(str(getattr(message, "content", message))
                    for message in state["messages"][since:]).lower()


def names_in(text: str, names) -> set:
    """Which of `names` the bot actually mentioned."""
    lowered = text.lower()
    return {name for name in names if name.lower() in lowered}


def skip_without(state: dict, field: str):
    """Skip with a readable reason when a state field of Task 3a is missing."""
    import pytest

    if field not in state:
        pytest.skip(f"state has no {field!r} yet -- Task 3a")


def offline() -> bool:
    """True when no LLM key is configured; the static path is measured anyway."""
    key = os.environ.get("OPENAI_API_KEY", "")
    return not key or key.startswith("<")
