"""Node logging: the one thing every component in this exercise does the same way.

A LangGraph node is a function ``state -> patch``. On its own that is invisible:
you see the final state, never the reasoning. Every node in this repository
therefore logs three things, always in the same order:

    received : what the node was handed (the relevant part of the state)
    doing    : which rule of its contract it applied, and why
    returns  : the patch it gives back, plus where control goes next

Read the log top to bottom and you are reading the process. That is the point
of the whole exercise: the process is an artifact, not something you infer.

Usage inside a node::

    from pizzabot import trace

    def my_node(state):
        trace.received("my_node", state, "input", "slots")
        trace.doing("my_node", "no exact match -- trying fuzzy match")
        patch = {"slots": {...}}
        return trace.returns("my_node", patch, next_step="address_recognition")

``trace.returns`` logs the patch and returns it unchanged, so it can wrap the
``return`` statement without changing what the node does.

Set ``LOG_LEVEL=WARNING`` in the environment to silence the trace, or
``TRACE_WIDTH=100`` to widen the value cut-off.
"""

from __future__ import annotations

import logging
import os
import sys
import textwrap
from typing import Any, Mapping

# One logger for the whole exercise. ``basicConfig`` is called once, here, so
# every script gets the same output format without repeating itself.
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
# stdout, not the logging default (stderr): everything else in this repository
# prints to stdout, and the two streams interleave in the wrong order as soon as
# a student pipes the output into a file or into `less`.
logging.basicConfig(level=LOG_LEVEL, format="%(message)s", stream=sys.stdout)
LOGGER = logging.getLogger("pizzabot")

# Values are shortened so a long menu or message history cannot flood the log.
# The node rules end at column 79; keep the values inside the same frame:
# 4 (indent) + 8 (label) + 2 + 10 (key) + 3 (" = ") = 27, so 50 fits in 79.
# Widen it with TRACE_WIDTH=88 on a wide terminal.
VALUE_WIDTH = int(os.environ.get("TRACE_WIDTH", "50"))
RULE_WIDTH = 74


def _short(value: Any) -> str:
    """Render one value on one line, cut to VALUE_WIDTH characters."""
    text = repr(value)
    if len(text) > VALUE_WIDTH:
        text = text[: VALUE_WIDTH - 3] + "..."
    return text


def received(node: str, state: Mapping[str, Any], *keys: str) -> None:
    """Log the node's input.

    ``keys`` selects the state fields worth showing; without it the whole state
    is logged. Naming the keys is the better habit: it documents, in the code,
    which part of the state this component actually reads.
    """
    LOGGER.info("")
    LOGGER.info("--- %s %s", node, "-" * max(0, RULE_WIDTH - len(node)))
    fields = keys if keys else tuple(state.keys())
    for key in fields:
        LOGGER.info("    received: %-10s = %s", key, _short(state.get(key)))


def _wrapped(label: str, message: str) -> None:
    """Print one labelled line, wrapped into the 79-column frame of the rules."""
    lines = textwrap.wrap(str(message), width=79 - 14) or [""]
    LOGGER.info("    %-8s: %s", label, lines[0])
    for continuation in lines[1:]:
        LOGGER.info("    %-8s  %s", "", continuation)


def doing(node: str, message: str) -> None:
    """Log which rule of the contract the node is applying, and why."""
    _wrapped("doing", message)


def returns(node: str, patch: Mapping[str, Any], next_step: str = "") -> Mapping[str, Any]:
    """Log the patch the node hands back, then return it unchanged.

    ``next_step`` is free text: the node that runs next, or the condition that
    decides it. A node never chooses its own successor -- the graph does -- so
    this line is documentation, not behaviour.
    """
    if patch:
        for key, value in patch.items():
            # `say()` hands back the whole history, and the only new entry is the
            # last one -- which is also the only one worth a line in the trace.
            # Printing the list would push the new message past the cut-off, and
            # every node would log the same first message forever.
            if key == "messages" and isinstance(value, list) and value:
                text = getattr(value[-1], "content", value[-1])
                LOGGER.info("    returns : %-10s += %s", key, _short(text))
            else:
                LOGGER.info("    returns : %-10s = %s", key, _short(value))
    else:
        LOGGER.info("    returns : {} (nothing changed -- this is allowed)")
    if next_step:
        LOGGER.info("    next    : %s", next_step)
    return patch


def decision(node: str, chosen: str, reason: str) -> str:
    """Log a routing decision, then return the chosen branch unchanged.

    Routing is a component too: it has one place, one log line, one reason.
    """
    LOGGER.info("")
    LOGGER.info("--- %s (routing) %s", node, "-" * max(0, RULE_WIDTH - len(node) - 10))
    _wrapped("chose", chosen)
    _wrapped("because", reason)
    return chosen
