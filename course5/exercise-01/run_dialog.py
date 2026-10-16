"""Run the ordering bot in the terminal -- one graph run per user turn.

    python run_dialog.py                      # type your own turns
    python run_dialog.py --script             # replay the lecture example
    LOG_LEVEL=WARNING python run_dialog.py    # hide the node trace

The loop below is deliberately dumb: read a line, invoke the graph once, print
what the bot said. Everything that deserves a name is a component inside the
graph -- that is what makes the process reviewable and, from Iteration 2 on,
replaceable piece by piece.
"""

from __future__ import annotations

import sys
import textwrap

from pizzabot import pizza_api
from pizzabot.graph import build_graph
from pizzabot.state import new_state

# The walkthrough from Lecture 1, Part C.
SCRIPT = [
    "Hello",
    "I would like a Margherita",
    "deliver it to 5 Rue Michelet, Saint-Étienne",
]


def main() -> None:
    graph = build_graph()
    state = new_state()
    scripted = iter(SCRIPT) if "--script" in sys.argv else None
    spoken = 0

    while not state["ended"]:
        if scripted is not None:
            try:
                state["input"] = next(scripted)
            except StopIteration:
                print("\n(script exhausted -- the dialog did not finish)")
                break
            print(f"\nyou: {state['input']}")
        else:
            try:
                state["input"] = input("\nyou: ")
            except (EOFError, KeyboardInterrupt):
                print("\nbye")
                break
            if state["input"].strip().lower() in {"quit", "exit"}:
                break

        state = graph.invoke(state)

        # The bot may have said nothing this turn (a component stayed silent).
        if len(state["messages"]) > spoken:
            for message in state["messages"][spoken:]:
                print(textwrap.fill(message.content, width=79,
                                    initial_indent="bot: ", subsequent_indent="     "))
            spoken = len(state["messages"])
        else:
            print("bot: (nothing to say -- look at the trace above to see why)")

    if state["ended"]:
        print("\n=== dialog finished ===")
        for slot, value in state["slots"].items():
            print(f"    {slot:11s}: {value}")
        print(f"    {'order_id':11s}: {state['order_id']}")


if __name__ == "__main__":
    try:
        main()
    except pizza_api.PizzaApiError as error:
        pizza_api.explain_and_exit(error)
