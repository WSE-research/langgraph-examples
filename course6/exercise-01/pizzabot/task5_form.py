"""Task 5 -- order form, routing, placement, confirmation. YOUR CODE GOES HERE.

Six components live here: three are yours to write, three are given.

    route            (yours)  the entry decision: which component sees this turn
    order_form       (yours)  which slot is still missing, and how we ask for it
    slots_complete   (yours)  the condition on the edge to order_placement
    place_order      (given)  POST /order -- the only side effect of the process
    confirm          (given)  the closing message
    help_message     (given)  what we say when we did not understand at all

Contracts -- do not change them, implement them

    name        router (decision component)
    reads       state["input"], state["expected"], state["slots"]
    calls       GET /pizza (to recognise a menu name as ordering intent), state["slots"]
    calls       GET /pizza (to recognise a menu name as ordering intent)
    returns     the name of the node that runs next -- it never changes state
    rules       1. if `expected` names a slot, the turn goes to the component that
                   fills it: "pizza_name" -> pizza_recognition,
                   "address" -> address_recognition
                2. an utterance with ordering intent, or naming an item of the
                   menu, or arriving while an order is in progress, starts the
                   ordering branch
                3. anything else gets help
    guarantee   returns exactly one of: "pizza_recognition",
                "address_recognition", "help". Every routing rule of the process
                lives in this function -- if it is not here, it is not in the
                diagram either.

    name        order_form (the only component that asks questions)
    reads       state["slots"], state["expected"]
    writes      expected, messages
    rules       1. ask for the first missing slot, in the order of REQUIRED
                2. asking twice for the same slot is prefixed with REPEAT, so
                   the user hears that we did not understand
                3. nothing missing -> say nothing, set expected = None
    guarantee   at most one question per turn; expected always names the slot
                that question was about (or None)
    failure     none -- this component cannot fail

    name        slots_complete (decision component, the edge to order_placement)
    reads       state["slots"]
    returns     True when every slot of REQUIRED is present, False otherwise --
                it never changes the state
    guarantee   True is only ever returned for a frame that order_placement can
                use; this is what discharges that component's precondition
    failure     none -- the question "is the frame full?" always has an answer

    name        order_placement (given) and confirmation (given)
    precondition  slots.pizza_id and slots.address exist (order_placement),
                and order_id exists (confirmation). Neither component checks:
                the condition on the edge -- slots_complete -- is what
                guarantees it. That is the one precondition in this process, and
                the graph, not an `if`, is what establishes it.

Task 5a  draw the whole process: every node, every edge, both conditional
         edges, and what the state looks like after each node.
Task 5b  implement the three TODOs.
Task 5c  validate by hand: python validate_task5.py, then run the full dialog
         with python run_dialog.py
"""

from __future__ import annotations

from pizzabot import pizza_api, trace
from pizzabot.state import ChatbotState, say

REQUIRED = ["pizza_name", "address"]

QUESTIONS = {
    "pizza_name": "Which pizza would you like? Our menu: {menu}.",
    "address": "Where should we deliver? Street, house number and city, for example: 5 Rue Michelet, Saint-Étienne.",
}
REPEAT = "Sorry, I did not get that. "

# Ordering intent, as a list of literal phrases -- one simple, decidable rule.
ORDER_INTENT = (
    "order", "pizza", "menu", "hungry", "delivery", "deliver",
    "would like", "i'd like", "i want", "give me", "i'll have",
)


# ---------------------------------------------------------------- routing --
def route(state: ChatbotState) -> str:
    """Return the name of the node that handles this turn.

    TODO 1: implement the three rules of the contract. Use

                trace.decision("router", "<node name>", "<why>")

            for every branch -- it returns the node name unchanged and makes the
            decision visible in the log. A routing rule that is not logged is a
            rule nobody can review.
    """
    text = state["input"].lower()

    return trace.decision("router", "help", "nothing implemented yet")


# -------------------------------------------------------------- the form --
def order_form(state: ChatbotState) -> dict:
    """Ask for the first missing slot -- or stay silent when the frame is full.

    TODO 2: - compute `missing` from REQUIRED and state["slots"]
            - nothing missing -> return {"expected": None} (and log it)
            - otherwise take the first missing slot, build the question from
              QUESTIONS (the pizza question needs the menu:
              .format(menu=", ".join(pizza_api.menu_names()))), prefix it with
              REPEAT if state["expected"] is already that slot, and return

                  {"expected": slot, **say(state, question)}
    """
    trace.received("order_form", state, "slots", "expected")

    trace.doing("order_form", "nothing implemented yet -> asking nothing")
    return trace.returns("order_form", {"expected": None}, next_step="slots_complete")


def slots_complete(state: ChatbotState) -> bool:
    """The condition on the edge: may we place the order?

    TODO 3: return True exactly when every slot of REQUIRED is present in
            state["slots"], and log the decision with trace.decision().
    """
    return False


# ------------------------------------------------- given: the last two nodes --
def place_order(state: ChatbotState) -> dict:
    """GIVEN. POST /order -- the only side effect this process has on the world."""
    trace.received("order_placement", state, "slots")
    slots = state["slots"]
    trace.doing("order_placement", f"POST /order pizza_id={slots['pizza_id']} address={slots['address']}")
    order = pizza_api.place_order(slots["pizza_id"], slots["address"])
    return trace.returns(
        "order_placement", {"order_id": order["order_id"]}, next_step="confirmation (fixed edge)"
    )


def confirm(state: ChatbotState) -> dict:
    """GIVEN. The closing message -- and the end of the dialog."""
    trace.received("confirmation", state, "slots", "order_id")
    address = state["slots"]["address"]
    text = (
        f"Your {state['slots']['pizza_name']} is on its way to "
        f"{address['house_number']} {address['street']}, {address['city']}. "
        f"Order id: {state['order_id']}."
    )
    trace.doing("confirmation", "order confirmed -> ending the dialog")
    patch = {**say(state, text), "ended": True}
    return trace.returns("confirmation", patch, next_step="END")


def help_message(state: ChatbotState) -> dict:
    """GIVEN. What we say when no rule understood the utterance."""
    trace.received("help", state, "input")
    trace.doing("help", "no ordering intent -> explaining what this bot can do")
    patch = say(
        state,
        "I can take a pizza order. Tell me which pizza you would like and where to deliver it.",
    )
    return trace.returns("help", patch, next_step="END")
