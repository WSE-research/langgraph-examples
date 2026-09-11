"""The process -- GIVEN. You write the components, this file wires them.

This is the same graph as on slide 20-27 of Lecture 1. Read it once: it is the
picture of your process in code form, and `demo_visualize.py --pizza` turns it
back into a picture you can put next to your hand-drawn model.

    START -> router ?-> pizza_recognition -> address_recognition -> order_form
                    ?-> address_recognition -> order_form
                    ?-> help -> END
    order_form ?-> order_placement -> confirmation -> END     (slots complete)
               ?-> END                                        (something missing)

One run of this graph = one user turn. The dialog loop lives in run_dialog.py,
not in the graph: the graph is a process, not an event loop.

You do not have to change anything here for Tasks 3-5. If you want to change
it, change the drawing first -- that is the whole point of Iteration 1.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from pizzabot.state import ChatbotState
from pizzabot.task3_pizza import recognize_pizza
from pizzabot.task4_address import recognize_address
from pizzabot.task5_form import confirm, help_message, order_form, place_order, route, slots_complete


def build_graph():
    """Wire the components and compile the process."""
    workflow = StateGraph(ChatbotState)

    # The router decides only -- it changes nothing, so its node body is empty.
    # `add_conditional_edges(START, route, ...)` would work without this node at
    # all. It exists so that the decision has a box in the exported diagram: one
    # empty node is a cheap price for a picture that does not hide a rule.
    workflow.add_node("router", lambda state: {})
    workflow.add_node("pizza_recognition", recognize_pizza)
    workflow.add_node("address_recognition", recognize_address)
    workflow.add_node("order_form", order_form)
    workflow.add_node("order_placement", place_order)
    workflow.add_node("confirmation", confirm)
    workflow.add_node("help", help_message)

    workflow.add_edge(START, "router")
    workflow.add_conditional_edges(
        "router", route, ["pizza_recognition", "address_recognition", "help"]
    )
    workflow.add_edge("pizza_recognition", "address_recognition")
    workflow.add_edge("address_recognition", "order_form")
    workflow.add_conditional_edges(
        "order_form", slots_complete, {True: "order_placement", False: END}
    )
    workflow.add_edge("order_placement", "confirmation")
    workflow.add_edge("confirmation", END)
    workflow.add_edge("help", END)

    return workflow.compile()
