"""Task 4 -- address recognition. YOUR CODE GOES HERE.

Contract -- do not change it, implement it

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
    failure     no match, or the API rejects the address -> empty patch `{}`;
                the order form (Task 5) asks again.

Run just this component:

    python -m pizzabot.task4_address "deliver it to 5 Rue Michelet, Saint-Étienne"

Task 4a  draw the component and its two rules before you code.
Task 4b  implement the two TODOs below.
Task 4c  validate by hand: python validate_task4.py -- and add the case that
         you are sure will break it. Keep that case; you will need it in
         Iteration 2, when an LLM takes this component over.
"""

from __future__ import annotations

import re

from pizzabot import pizza_api, trace
from pizzabot.state import ChatbotState

# Words that may stand around an address but are never part of one.
FILLER = {
    "a", "an", "and", "address", "at", "bring", "deliver", "delivered", "delivery",
    "for", "house", "i", "in", "is", "it", "like", "live", "my", "of", "order",
    "please", "send", "thanks", "thank", "you", "the", "to", "would",
}

# Building blocks for the two patterns -- given, so that you spend the time on
# the rule and not on regex syntax.
WORD = r"[^\W\d_][\w'’\-\.]*"            # a word starting with a letter (accents ok)
STREET = rf"{WORD}(?: {WORD}){{0,4}}"    # up to five words
NUMBER = r"\d+\s?[a-zA-Z]?"              # 5, 12b, "12 b"
CITY = rf"{WORD}(?:[ \-]{WORD}){{0,3}}"  # Lyon, Saint-Priest-en-Jarez

# TODO 1: assemble the two patterns from the blocks above. Both must capture the
#         groups "house_number", "street" and "city" -- the rest of the code
#         relies on exactly these names.
#
#         NUMBER_FIRST: <number> <street> , <city>
#         NUMBER_LAST : <street> <number> , <city>
#
NUMBER_FIRST = re.compile(rf"(?P<house_number>{NUMBER})\s+(?P<street>{STREET})\s*,\s*(?P<city>{CITY})", re.UNICODE)
NUMBER_LAST = re.compile(r"^$")     # <- replace this


def _strip_filler(text: str) -> str:
    """Drop filler words at the beginning and at the end of a captured group."""
    words = text.split()
    while words and words[0].lower().strip(".,") in FILLER:
        words.pop(0)
    while words and words[-1].lower().strip(".,") in FILLER:
        words.pop()
    return " ".join(words)


def find_address(text: str) -> dict | None:
    """The pure rule, without any state -- which is why it is easy to test.

    Returns {"street": ..., "house_number": ..., "city": ...} or None.

    TODO 2: try both patterns with .search(); for the first one that matches,
            clean street and city with _strip_filler (and skip the match if one
            of them becomes empty), remove spaces inside the house number, and
            return the dict. Return None when no pattern matched.
    """
    return None


def recognize_address(state: ChatbotState) -> dict:
    """Write slots.address if the utterance contains a complete address."""
    trace.received("address_recognition", state, "input", "slots", "expected")

    found = find_address(state["input"])
    if found is None:
        trace.doing("address_recognition", "no rule matched -> nothing to write; order_form will ask")
        return trace.returns("address_recognition", {}, next_step="order_form")

    trace.doing("address_recognition", f"a complete address matched: {found}")

    # Rule 3: an address the delivery service does not know is not an address.
    if not pizza_api.validate_address(**found):
        trace.doing("address_recognition", "POST /address/validate rejected it -> slot stays empty")
        return trace.returns("address_recognition", {}, next_step="order_form")

    trace.doing("address_recognition", "address validated by the API -> writing the slot")
    slots = {**state["slots"], "address": found}
    return trace.returns(
        "address_recognition",
        {"slots": slots, "expected": None},
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
    print("\nslots :", result["slots"])
    print("bot   :", last_message(result) or "(said nothing)")
