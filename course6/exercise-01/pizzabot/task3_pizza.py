"""Task 3 -- pizza recognition. YOUR CODE GOES HERE.

Contract -- do not change it, implement it

    name        pizza_recognition
    reads       state["input"], state["slots"], state["expected"]
    writes      slots.pizza_name, slots.pizza_id
    calls       GET /pizza (the menu), through pizzabot/pizza_api.py
    rules       1. the menu is data: names come from GET /pizza, never from code
                2. a menu name mentioned literally in the utterance wins
                   (compared case-insensitively)
                3. otherwise: one token of the utterance is close to a menu name
                   -- difflib ratio >= 0.80, token of >= 4 letters, both sides
                   lower-cased for the comparison
                4. several candidates -> the first one in menu order wins
    guarantee   slots.pizza_name is always a name that exists on the menu, spelled
                exactly as the menu spells it, and slots.pizza_id always belongs
                to that name. The component never writes any other slot and never
                asks a question.
    failure     nothing recognised -> empty patch `{}`. The component stays
                silent on purpose: asking is the order form's job (Task 5), so
                the dialog has exactly one place where questions are phrased.

Run just this component:

    python -m pizzabot.task3_pizza "I would like a Margarita please"

Task 3a  draw this component first: box, arrow in, arrow out, and what each
         arrow carries. docs/process-model.md has a place for it.
Task 3b  implement the three TODOs below.
Task 3c  validate by hand with your own examples: python validate_task3.py
"""

from __future__ import annotations

import difflib
import re

from pizzabot import pizza_api, trace
from pizzabot.state import ChatbotState

FUZZY_THRESHOLD = 0.80
MIN_TOKEN_LENGTH = 4          # "to", "a", "it" must never fuzzy-match a pizza
TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)   # letters only, accents included


def _literal_mention(text: str, names: list[str]) -> str | None:
    """Rule 2: the menu name appears literally in the utterance.

    TODO 1: return the first name of `names` that occurs in `text`, else None.

            Two traps in one line: `text` arrives lower-cased, the menu names do
            not (`pizza_api.menu_names()` returns them as the API spells them),
            so compare `name.lower()` with `text` -- but return `name` unchanged,
            because the guarantee says the slot holds the menu spelling.
    """
    return None


def _fuzzy_match(text: str, names: list[str]) -> tuple[str, float, str] | None:
    """Rule 3: one token of the utterance is one typo away from a menu name.

    TODO 2: for every token of `text` with at least MIN_TOKEN_LENGTH letters
            (use TOKEN.findall) and every menu name -- and every single word of
            a multi-word name such as "Quattro Formaggi" -- compute

                difflib.SequenceMatcher(None, token.lower(), variant.lower()).ratio()

            Both sides lower-cased: "Margarita" against "Margherita" scores 0.84
            lower-cased and 0.70 if you forget, and the difference decides whether
            the example in the sheet works.

            Return the best (name, ratio, token) with ratio >= FUZZY_THRESHOLD,
            or None. Ask yourself why the length limit is in the contract, and
            note that this ratio is not an edit distance: one wrong letter in a
            four-letter word scores 0.75 and is rejected, one in a ten-letter
            word scores ~0.95.
    """
    return None


def recognize_pizza(state: ChatbotState) -> dict:
    """Write slots.pizza_name/pizza_id if the utterance names a pizza."""
    trace.received("pizza_recognition", state, "input", "slots", "expected")

    text = state["input"].lower()
    names = pizza_api.menu_names()          # rule 1: the menu is data
    trace.doing("pizza_recognition", f"menu has {len(names)} items: {', '.join(names[:4])}, ...")

    # TODO 3: try _literal_mention first, then _fuzzy_match. If one of them found a
    #         name, build the patch:
    #
    #             slots = {**state["slots"],
    #                      "pizza_name": name,
    #                      "pizza_id": pizza_api.pizza_id_for(name)}
    #             return trace.returns("pizza_recognition",
    #                                  {"slots": slots},
    #                                  next_step="address_recognition (fixed edge)")
    #
    #         Note what is *not* in that patch: `expected` belongs to the order
    #         form (see the ownership table in state.py), and one slot with one
    #         writer is what lets two people work on this process at once.
    #
    #         Log *which rule* matched with trace.doing() before you return --
    #         a component that cannot explain its decision is not finished.

    trace.doing("pizza_recognition", "nothing implemented yet -> staying silent")
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

    utterance = sys.argv[1] if len(sys.argv) > 1 else "I would like a Margarita please"
    result = build_graph().invoke(new_state(utterance))
    print("\nslots :", result["slots"])
    print("bot   :", last_message(result) or "(said nothing)")
