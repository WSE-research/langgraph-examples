"""The seam: which implementation sits behind which component name. GIVEN.

The process model (`graph.py`) names components -- `pizza_recognition`,
`address_recognition` -- and never says who implements them. This file does.
Two configurations of one process:

    STATIC   the Iteration 1 rules, unchanged
    LLM      the Iteration 2 service calls, with the rules as their fallback

`build_graph(STATIC)` and `build_graph(LLM)` produce two runnable processes
from one model, and the exported diagram is identical for both -- that picture
is the proof that the process did not change (Task 5). Mixed configurations are
just another dictionary: replace a single entry.

Select one from the command line or `.env`::

    python run_dialog.py --config llm
    BOT_CONFIG=llm python run_dialog.py

This is Lecture 2, slide 2.18 (dependency inversion) in twenty lines: the
process depends on the contract, the implementation is injected.
"""

from __future__ import annotations

import os
from typing import Callable

from pizzabot.task3_pizza import recognize_pizza
from pizzabot.task4_address import recognize_address

# Written as functions so that importing this module never imports the LLM
# modules before they exist (you write them in Tasks 2 and 3).


def static_implementations() -> dict[str, Callable]:
    return {
        "pizza_recognition": recognize_pizza,
        "address_recognition": recognize_address,
    }


def llm_implementations() -> dict[str, Callable]:
    from pizzabot.address_llm import recognize_address_llm      # Task 3
    from pizzabot.pizza_llm import recognize_pizza_llm          # Task 4

    return {
        "pizza_recognition": recognize_pizza_llm,
        "address_recognition": recognize_address_llm,
    }


CONFIGS: dict[str, Callable[[], dict[str, Callable]]] = {
    "static": static_implementations,
    "llm": llm_implementations,
}

STATIC = "static"
LLM = "llm"


def implementations(name: str | None = None) -> dict[str, Callable]:
    """The implementation dictionary for a configuration name.

    `name` may be None: then `BOT_CONFIG` from the environment decides, and the
    default is "static" -- the process must keep working with no key at all.
    """
    chosen = (name or os.environ.get("BOT_CONFIG") or STATIC).lower()
    if chosen not in CONFIGS:
        raise ValueError(f"unknown configuration {chosen!r}; choose one of {', '.join(CONFIGS)}")
    return CONFIGS[chosen]()


def from_argv(argv: list[str]) -> str:
    """`--config llm`, `--llm` or `--static` on the command line; else the environment."""
    if "--llm" in argv:
        return LLM
    if "--static" in argv:
        return STATIC
    if "--config" in argv:
        return argv[argv.index("--config") + 1].lower()
    return (os.environ.get("BOT_CONFIG") or STATIC).lower()
