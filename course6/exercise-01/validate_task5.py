"""Task 5c -- validate the form and the routing by hand, turn by turn.

    python validate_task5.py
    LOG_LEVEL=WARNING python validate_task5.py

Here a single utterance is not enough: the order form is about *sequences*. Each
dialog below is a list of turns, replayed through the full process; what you
check is the state after each turn and the question the bot asks next.
"""

from __future__ import annotations

import os

# This script orders fixed pizzas, and since Pizza API 1.3.0 two pizzas are sold out
# every minute (POST /order answers 409). A test driver opts out of that draw with
# the header X-Accept-Everything: true, which pizzabot/pizza_api.py sends when this
# is set -- so a result does not depend on the minute it runs in.
os.environ.setdefault("PIZZA_API_ACCEPT_EVERYTHING", "true")

from pizzabot import pizza_api
from pizzabot.graph import build_graph
from pizzabot import pizza_api
from pizzabot.state import new_state

DIALOGS: list[tuple[str, list[str], str]] = [
    (
        "happy path, two turns",
        ["I would like a Margherita", "deliver it to 5 Rue Michelet, Saint-Étienne"],
        "asks for the address, then places the order and confirms with an order id",
    ),
    (
        "everything in one turn",
        ["a Margherita to 5 Rue Michelet, Saint-Étienne please"],
        "no question at all -- both slots are filled in the same turn, order placed",
    ),
    (
        "the user starts with nonsense",
        ["good evening", "I would like a Funghi", "3 Place Jean Jaurès, Saint-Étienne"],
        "help, then asks for the address, then confirms",
    ),
    (
        "the user does not answer the question",
        ["I want a pizza", "the red one", "a Diavola to 5 Rue Michelet, Saint-Étienne"],
        "asks for the pizza, repeats the question (prefix 'Sorry, I did not get that'), then confirms",
    ),
    # TODO: one dialog of your own. Ideas: the user changes the pizza half way
    #       through, gives an address that does not exist, orders two pizzas,
    #       or answers the address question with only a street.
]


def main() -> None:
    for title, turns, expectation in DIALOGS:
        print("\n" + "=" * 100)
        print(f"dialog: {title}")
        print(f"you expect: {expectation}")
        print("=" * 100)

        graph = build_graph()
        state = new_state()
        spoken = 0
        for turn in turns:
            state["input"] = turn
            state = graph.invoke(state)
            print(f"  you: {turn}")
            for message in state["messages"][spoken:]:
                print(f"  bot: {message.content}")
            spoken = len(state["messages"])
            print(f"       slots={state['slots']} expected={state['expected']!r} ended={state['ended']}")
            if state["ended"]:
                break
        print(f"  --> order_id: {state['order_id']}")


if __name__ == "__main__":
    try:
        main()
    except pizza_api.PizzaApiError as error:
        pizza_api.explain_and_exit(error)
