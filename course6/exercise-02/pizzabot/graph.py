"""The process -- GIVEN in Iteration 1, and it does NOT change in Iteration 2.

    START -> router ?-> pizza_recognition -> address_recognition -> order_form
                    ?-> address_recognition -> order_form
                    ?-> help -> END
    order_form ?-> order_placement -> confirmation -> END     (slots complete)
               ?-> END                                        (something missing)

What changes today is one thing: `build_graph` no longer imports the two
recognizers itself. It receives a dictionary "component name -> implementation"
(see `pizzabot/config.py`) and wires whatever it is given. That dictionary is
the seam: `build_graph(implementations("static"))` and
`build_graph(implementations("llm"))` are two configurations of ONE process
model, and `demo_visualize.py --both` shows that the exported diagram is
identical for both.

One run of this graph = one user turn. The dialog loop lives in run_dialog.py.
"""

from __future__ import annotations

from typing import Callable

from langgraph.graph import END, START, StateGraph

from pizzabot import config
from pizzabot.state import ChatbotState
from pizzabot.task3_pizza import recognize_pizza
from pizzabot.task4_address import recognize_address
from pizzabot.task5_form import confirm, help_message, order_form, place_order, route, slots_complete


def build_graph(implementations: dict[str, Callable] | None = None):
    """Wire the components and compile the process.

    `implementations` maps the two substitutable component names to functions.
    None means: take the configuration named by BOT_CONFIG (default "static").
    """
    if implementations is None:
        implementations = config.implementations()

    workflow = StateGraph(ChatbotState)

    workflow.add_node("router", lambda state: {})

    # TODO (Task 5a): the two recognizers must come from `implementations`, not
    #                 from the imports above -- otherwise `--config llm` silently
    #                 runs the rules. Replace the two lines below by
    #
    #     for name in ("pizza_recognition", "address_recognition"):
    #         workflow.add_node(name, implementations[name])
    #
    #                 and delete the two now-unused imports. The test
    #                 `test_graph_uses_the_injected_implementation` tells you
    #                 whether you did.
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
