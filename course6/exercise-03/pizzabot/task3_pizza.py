"""Iteration 1, Task 3 -- pizza recognition (static, rule-based). Complete since Iteration 1.

Contract (the same one the students get in the skeleton)

    name        pizza_recognition
    reads       state["input"], state["slots"], state["expected"]
    writes      slots.pizza_name, slots.pizza_id
    calls       GET /pizza (the menu), through pizzabot/pizza_api.py
    rules       1. the menu is data: names come from GET /pizza, never from code
                2. a menu name mentioned literally in the utterance wins
                   (compared case-insensitively)
                3. otherwise: one token of the utterance is close to a menu name
                   (difflib ratio >= 0.80 on lower-cased strings, token >= 4
                   characters), against the name and against each word of it
                4. several candidates -> the first one in menu order wins
    guarantee   slots.pizza_name is always a name that exists on the menu, spelled
                as the menu spells it, and slots.pizza_id always belongs to that
                name; no other slot is written and no question is asked
    failure     nothing recognised -> empty patch. The component stays silent
                on purpose: asking is the order form's job (Task 5), so the
                dialog has exactly one place where questions are phrased.
"""

from __future__ import annotations

import difflib
import re

from pizzabot import log, pizza_api, trace
from pizzabot.state import ChatbotState

FUZZY_THRESHOLD = 0.80
MIN_TOKEN_LENGTH = 4          # "to", "a", "it" must never fuzzy-match a pizza
TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)   # letters only, accents included


def _literal_mention(text: str, names: list[str]) -> str | None:
    """Rule 2: the menu name appears literally in the utterance.

    Literal, not "exact": this is substring containment, so the first *menu*
    entry that occurs anywhere in the utterance wins -- which is rule 4, and
    which is why "a salami and a funghi please" answers Funghi.
    """
    for name in names:
        if name.lower() in text:
            return name
    return None


def _fuzzy_match(text: str, names: list[str]) -> tuple[str, float, str] | None:
    """Rule 3: one token of the utterance is one typo away from a menu name."""
    best: tuple[float, str, str] | None = None
    for token in TOKEN.findall(text):
        if len(token) < MIN_TOKEN_LENGTH:
            continue
        for name in names:
            variants = [name.lower()] + name.lower().split()
            for variant in variants:
                ratio = difflib.SequenceMatcher(None, token.lower(), variant).ratio()
                if ratio >= FUZZY_THRESHOLD and (best is None or ratio > best[0]):
                    best = (ratio, name, token)
    if best is None:
        return None
    ratio, name, token = best
    return name, ratio, token


def recognize_pizza(state: ChatbotState) -> dict:
    """Write slots.pizza_name/pizza_id if the utterance names a pizza."""
    trace.received("pizza_recognition", state, "input", "slots", "expected")

    text = state["input"].lower()
    names = pizza_api.menu_names()
    trace.doing("pizza_recognition", f"menu has {len(names)} items: {', '.join(names[:4])}, ...")

    name = _literal_mention(text, names)
    if name:
        trace.doing("pizza_recognition", f"rule 2 (literal mention, menu order) matched {name!r}")
    else:
        fuzzy = _fuzzy_match(text, names)
        if fuzzy:
            name, ratio, token = fuzzy
            trace.doing(
                "pizza_recognition",
                f"rule 3 (fuzzy) token {token!r} ~ {name!r} at ratio {ratio:.2f} "
                f">= {FUZZY_THRESHOLD}",
            )

    if name:
        slots = {**state["slots"], "pizza_name": name, "pizza_id": pizza_api.pizza_id_for(name)}
        return trace.returns(
            "pizza_recognition",
            {"slots": slots},          # `expected` belongs to the order form
            next_step="address_recognition (fixed edge)",
        )

    if state["expected"] == "pizza_name":
        trace.doing("pizza_recognition", "we asked for a pizza and understood nothing -> order_form will ask again")
    else:
        trace.doing("pizza_recognition", "no pizza mentioned -> nothing to write, stay silent")
    return trace.returns("pizza_recognition", {}, next_step="address_recognition")


def build_graph():
    """A one-node graph, so this component can be run and reviewed on its own."""
    from langgraph.graph import END, START, StateGraph

    workflow = StateGraph(ChatbotState)
    workflow.add_node("pizza_recognition", recognize_pizza)
    workflow.add_edge(START, "pizza_recognition")
    workflow.add_edge("pizza_recognition", END)
    return workflow.compile()


if __name__ == "__main__":
    import sys

    from pizzabot.state import last_message, new_state

    utterance = sys.argv[1] if len(sys.argv) > 1 else "I would like a Margaritha please"
    result = build_graph().invoke(new_state(utterance))
    log.plain()
    log.result(f"slots : {result['slots']}")
    log.plain(f"bot   : {last_message(result) or '(said nothing)'}")
