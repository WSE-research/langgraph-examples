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

This module is the *trace* channel of the log layer (pizzabot/log.py): it is
diagnostics, so ``LOG_LEVEL=WARNING`` silences it while the scripts keep
printing their results. Colour, the stream and the format come from there;
this file only decides what a node says and in which order.

Set ``LOG_LEVEL=WARNING`` in the environment to silence the trace, or
``TRACE_WIDTH=100`` to widen the value cut-off.
"""

from __future__ import annotations

import os
import textwrap
from typing import Any, Mapping

from pizzabot import log

# The trace channel. Its level comes from LOG_LEVEL, its handler and its
# colours from pizzabot/log.py -- one place for the whole repository.
LOGGER = log.TRACE
LOG_LEVEL = log.LOG_LEVEL

# Values are shortened so a long menu or message history cannot flood the log.
# The node rules end at column 79; keep the values inside the same frame:
# 4 (indent) + 8 (label) + 2 + 10 (key) + 3 (" = ") = 27, so 50 fits in 79.
# Widen it with TRACE_WIDTH=88 on a wide terminal.
VALUE_WIDTH = int(os.environ.get("TRACE_WIDTH", "50"))
RULE_WIDTH = 74


def _line(message: str, *args: Any, role: str = "detail") -> None:
    """One line on the trace channel, painted by the role it plays.

    The roles are the ones of pizzabot/log.py: the node header is a step, the
    mechanical `received`/`returns` lines are details, what the node *decided*
    is plain text, and the tier -- who answered -- is the result.
    """
    LOGGER.info(message, *args, extra={"role": role})


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
    _line("")
    _line("--- %s %s", node, "-" * max(0, RULE_WIDTH - len(node)), role="step")
    fields = keys if keys else tuple(state.keys())
    for key in fields:
        _line("    received: %-10s = %s", key, _short(state.get(key)))


def _wrapped(label: str, message: str, role: str = "plain") -> None:
    """Log one labelled line, wrapped into the 79-column frame of the rules."""
    lines = textwrap.wrap(str(message), width=79 - 14) or [""]
    _line("    %-8s: %s", label, lines[0], role=role)
    for continuation in lines[1:]:
        _line("    %-8s  %s", "", continuation, role=role)


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
                _line("    returns : %-10s += %s", key, _short(text))
            else:
                _line("    returns : %-10s = %s", key, _short(value))
    else:
        _line("    returns : {} (nothing changed -- this is allowed)")
    if next_step:
        _line("    next    : %s", next_step)
    return patch


# Which tier answered, per node, for the whole process run. Iteration 2 adds this
# so that a comparison can say "the LLM answered in 9 of 12 cases, the rule in
# 3" -- the data Iteration 3 computes a metric from. The state schema is
# not touched: this is diagnostics, not process data.
TIERS: dict[str, list[str]] = {}


def tier(node: str, which: str, reason: str = "") -> None:
    """Record and log which tier produced the component's answer.

    ``which`` is "llm" (the service answered and passed every check) or
    "static" (the Iteration 1 rule decided); the reason says why the rule was
    needed. Printed in brackets -- the same tokens pytest uses in its test ids
    -- and always as the last line before ``returns``.
    """
    TIERS.setdefault(node, []).append(which)
    _wrapped("tier", f"[{which}]" + (f" -- {reason}" if reason else ""), role="result")


def service(message: str) -> None:
    """Log one line of the LLM service adapter, under the label ``llm``.

    The adapter is not a node: it has no ``received`` and no ``returns``. Its
    lines appear inside the block of the component that called it.
    """
    _wrapped("llm", message, role="detail")


def last_tier(node: str) -> str:
    """The tier recorded by the last run of ``node``, or "-" if it never recorded one."""
    return TIERS.get(node, ["-"])[-1]


def decision(node: str, chosen: str, reason: str) -> str:
    """Log a routing decision, then return the chosen branch unchanged.

    Routing is a component too: it has one place, one log line, one reason.
    """
    _line("")
    _line("--- %s (routing) %s", node, "-" * max(0, RULE_WIDTH - len(node) - 10), role="step")
    _wrapped("chose", chosen)
    _wrapped("because", reason)
    return chosen
