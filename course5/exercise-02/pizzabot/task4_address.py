"""Iteration 1, Task 4 -- address recognition (static, rule-based). Complete since Iteration 1.

Contract

    name        address_recognition
    reads       state["input"], state["slots"], state["expected"]
    writes      slots.address
    calls       POST /address/validate (is this address in the delivery area?),
                through pizzabot/pizza_api.py
    rules       1. two accepted orders, both ending in ", <city>":
                     "5 Rue Michelet, Saint-Étienne"   (number first)
                     "Rue Michelet 5, Saint-Étienne"   (number last)
                2. filler words around the match are removed, not parsed
                3. the address is checked against POST /address/validate
    guarantee   *complete or nothing*: street, house_number and city are all
                present, or slots.address is not written at all. A half address
                is worse than none -- it silently produces a wrong delivery.
    failure     no match -> empty patch, and the component stays silent:
                asking is the order form's job (Task 5);
                API says the address does not exist -> slot stays empty, and
                the order form asks for it again

    known limitation (on purpose, this is the hook for Iteration 2): the comma
    before the city is required. "5 Rue Michelet Saint-Étienne" is not
    recognised. Write the rule that fixes it and you will write three more.
"""

from __future__ import annotations

import re

from pizzabot import log, pizza_api, trace
from pizzabot.state import ChatbotState

# Words that may stand around an address but are never part of one.
FILLER = {
    "a", "an", "and", "address", "at", "bring", "deliver", "delivered", "delivery",
    "for", "house", "i", "in", "is", "it", "like", "live", "my", "of", "order",
    "please", "send", "thanks", "thank", "you", "the", "to", "would",
}

WORD = r"[^\W\d_][\w'’\-\.]*"            # a word starting with a letter (accents ok)
STREET = rf"{WORD}(?: {WORD}){{0,4}}"    # up to five words
NUMBER = r"\d+\s?[a-zA-Z]?"              # 5, 12b, "12 b"
CITY = rf"{WORD}(?:[ \-]{WORD}){{0,3}}"  # Lyon, Saint-Priest-en-Jarez

NUMBER_FIRST = re.compile(
    rf"(?P<house_number>{NUMBER})\s+(?P<street>{STREET})\s*,\s*(?P<city>{CITY})", re.UNICODE
)
NUMBER_LAST = re.compile(
    rf"(?P<street>{STREET})\s+(?P<house_number>{NUMBER})\s*,\s*(?P<city>{CITY})", re.UNICODE
)


def _strip_filler(text: str) -> str:
    """Drop filler words at the beginning and at the end of a captured group."""
    words = text.split()
    while words and words[0].lower().strip(".,") in FILLER:
        words.pop(0)
    while words and words[-1].lower().strip(".,") in FILLER:
        words.pop()
    return " ".join(words)


def find_address(text: str) -> dict | None:
    """The pure rule, without any state -- which is why it is easy to test."""
    for rule, pattern in (("number-first", NUMBER_FIRST), ("number-last", NUMBER_LAST)):
        match = pattern.search(text)
        if not match:
            continue
        street = _strip_filler(match.group("street"))
        city = _strip_filler(match.group("city"))
        if not street or not city:
            continue
        trace.doing("address_recognition", f"rule {rule!r} matched in {text!r}")
        return {
            "street": street,
            "house_number": match.group("house_number").replace(" ", ""),
            "city": city,
        }
    return None


def recognize_address(state: ChatbotState) -> dict:
    """Write slots.address if the utterance contains a complete address."""
    trace.received("address_recognition", state, "input", "slots", "expected")

    found = find_address(state["input"])
    if found is None:
        trace.doing("address_recognition", "no rule matched -> nothing to write; order_form will ask")
        return trace.returns("address_recognition", {}, next_step="order_form")

    trace.doing("address_recognition", f"a complete address matched: {found}")

    if not pizza_api.validate_address(**found):
        trace.doing("address_recognition", "POST /address/validate rejected it -> slot stays empty")
        return trace.returns("address_recognition", {}, next_step="order_form")

    trace.doing("address_recognition", "address validated by the API -> writing the slot")
    slots = {**state["slots"], "address": found}
    return trace.returns(
        "address_recognition",
        {"slots": slots},              # `expected` belongs to the order form
        next_step="order_form (fixed edge)",
    )


def build_graph():
    """A one-node graph, so this component can be run on its own."""
    from langgraph.graph import END, START, StateGraph

    workflow = StateGraph(ChatbotState)
    workflow.add_node("address_recognition", recognize_address)
    workflow.add_edge(START, "address_recognition")
    workflow.add_edge("address_recognition", END)
    return workflow.compile()


if __name__ == "__main__":
    import sys

    from pizzabot.state import last_message, new_state

    utterance = sys.argv[1] if len(sys.argv) > 1 else "deliver it to 5 Rue Michelet, Saint-Étienne"
    result = build_graph().invoke(new_state(utterance))
    log.plain()
    log.result(f"slots : {result['slots']}")
    log.plain(f"bot   : {last_message(result) or '(said nothing)'}")
