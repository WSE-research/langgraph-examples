"""Task 4 -- REFERENCE SOLUTION: pizza recognition, LLM-backed.

Contract -- the SAME contract as in Iteration 1 (pizzabot/task3_pizza.py).

    name        pizza_recognition          (this implementation: recognize_pizza_llm)
    reads       state["input"], state["slots"], state["expected"]
    writes      slots.pizza_name, slots.pizza_id
    calls       GET /pizza (the menu), through pizzabot/pizza_api.py
                the LLM service with prompts/pizza_v1.txt, through pizzabot/llm_service.py
                recognize_pizza from Iteration 1 -- as the fallback
    rules       1. the live menu goes INTO the prompt (<MENU>): the model chooses,
                   it does not invent
                2. the answer is {"pizza_name": <string>} or {}
                3. domain check: the name is on the menu -- compared without case,
                   but the slot gets the menu's spelling
                4. the service answered None or {}, or a check failed -> the
                   Iteration 1 rule decides
    guarantee   slots.pizza_name is always a name that exists on the menu, spelled
                as the menu spells it, and slots.pizza_id belongs to it -- unchanged
    failure     nothing recognised -> empty patch, silent -- unchanged
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pizzabot import llm_service, log, pizza_api, trace
from pizzabot.state import ChatbotState
from pizzabot.task3_pizza import recognize_pizza              # the fallback

PROMPT_VERSION = "pizza_v1"                                    # prompts/pizza_v1.txt
PROMPT_TEMPLATE = llm_service.load_prompt(PROMPT_VERSION)

DOMAIN_CHECKS = ("menu membership",)


class PizzaModel(BaseModel):
    """The schema of the answer: one key, one non-empty string."""

    model_config = ConfigDict(extra="forbid")

    pizza_name: str = Field(min_length=1)


def on_menu(name: str, names: list[str]) -> str | None:
    """Rule 3, the domain check: the menu name this answer refers to, or None."""
    wanted = name.strip().lower()
    for menu_name in names:
        if menu_name.lower() == wanted:
            return menu_name
    return None


def recognize_pizza_llm(state: ChatbotState) -> dict:
    """Same signature, same contract, same patch as recognize_pizza."""
    trace.received("pizza_recognition", state, "input", "slots", "expected")
    names = pizza_api.menu_names()                                 # rule 1: data, not code
    system = PROMPT_TEMPLATE.replace("<MENU>", ", ".join(names))

    raw = llm_service.extract(system, state["input"])
    if raw is None:
        trace.tier("pizza_recognition", "static", "the service failed -> the rule decides")
        return recognize_pizza(state)
    if raw == {}:
        trace.tier("pizza_recognition", "static", "the service saw no menu item -> the rule decides")
        return recognize_pizza(state)
    try:
        answer = PizzaModel(**raw)                                  # schema check
    except (ValidationError, TypeError) as error:
        trace.tier("pizza_recognition", "static",
                   f"schema check failed on {raw!r}: {type(error).__name__} -> the rule decides")
        return recognize_pizza(state)
    name = on_menu(answer.pizza_name, names)                        # domain check
    if name is None:
        trace.tier("pizza_recognition", "static", f"rejected: {answer.pizza_name!r} is not on the menu -> the rule decides")
        return recognize_pizza(state)

    trace.doing("pizza_recognition", f"schema ok, on the menu as {name!r} -> writing the slot")
    trace.tier("pizza_recognition", "llm")
    slots = {**state["slots"], "pizza_name": name, "pizza_id": pizza_api.pizza_id_for(name)}
    return trace.returns("pizza_recognition", {"slots": slots}, next_step="address_recognition (fixed edge)")


def build_graph():
    """A one-node graph, so this component can be run on its own."""
    from langgraph.graph import END, START, StateGraph

    workflow = StateGraph(ChatbotState)
    workflow.add_node("pizza_recognition", recognize_pizza_llm)
    workflow.add_edge(START, "pizza_recognition")
    workflow.add_edge("pizza_recognition", END)
    return workflow.compile()


if __name__ == "__main__":
    import sys

    from pizzabot.state import last_message, new_state

    utterance = sys.argv[1] if len(sys.argv) > 1 else "the four-cheese one please"
    result = build_graph().invoke(new_state(utterance))
    log.plain()
    log.result(f"slots : {result['slots']}")
    log.plain(f"tier  : [{trace.last_tier('pizza_recognition')}]")
    log.plain(f"bot   : {last_message(result) or '(said nothing)'}")
    log.detail(f"usage : {llm_service.service().usage.summary()}", indent="")
