"""Task 4 -- pizza recognition, LLM-backed. YOUR CODE GOES HERE.

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

Run just this component:

    python -m pizzabot.pizza_llm "the four-cheese one please"

Task 4a  draw it: where does the menu enter, and where is the membership checked?
Task 4b  implement the two TODOs.
Task 4c  compare both implementations: python compare_configs.py --pizza
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pizzabot import llm_service, log, pizza_api, trace
from pizzabot.state import ChatbotState
from pizzabot.task3_pizza import recognize_pizza              # the fallback

PROMPT_VERSION = "pizza_v1"                                    # prompts/pizza_v1.txt
PROMPT_TEMPLATE = llm_service.load_prompt(PROMPT_VERSION)

# The domain check, named -- compare_configs.py prints this on the service card.
DOMAIN_CHECKS = ("menu membership",)


class PizzaModel(BaseModel):
    """The schema of the answer: one key, one non-empty string."""

    model_config = ConfigDict(extra="forbid")

    pizza_name: str = Field(min_length=1)


def on_menu(name: str, names: list[str]) -> str | None:
    """Rule 3, the domain check: the menu name this answer refers to, or None.

    TODO 1: return the entry of `names` that equals `name` case-insensitively,
            spelled as the menu spells it -- or None. "Quattro formaggi" is on
            the menu, "Pizza Napoli" is not, whatever the model says.
    """
    return None


def recognize_pizza_llm(state: ChatbotState) -> dict:
    """Same signature, same contract, same patch as recognize_pizza."""
    trace.received("pizza_recognition", state, "input", "slots", "expected")
    names = pizza_api.menu_names()                                 # rule 1: data, not code
    system = PROMPT_TEMPLATE.replace("<MENU>", ", ".join(names))

    # TODO 2: the tiered flow, the same shape as in address_llm.py:
    #
    #   raw = llm_service.extract(system, state["input"])
    #   None            -> trace.tier("pizza_recognition", "static", "service failed"); fall back
    #   {} (empty dict) -> the model saw no menu item; fall back too -- the rule is the floor
    #   PizzaModel(**raw) raises ValidationError / TypeError -> "schema check failed"; fall back
    #   on_menu(...) is None -> "not on the menu: <name>"; fall back
    #   otherwise:
    #       trace.doing("pizza_recognition", f"schema ok, on the menu as {name!r} -> writing the slot")
    #       trace.tier("pizza_recognition", "llm")
    #       slots = {**state["slots"], "pizza_name": name, "pizza_id": pizza_api.pizza_id_for(name)}
    #       return trace.returns("pizza_recognition", {"slots": slots},
    #                            next_step="address_recognition (fixed edge)")
    #
    # Falling back means: `return recognize_pizza(state)` -- the Iteration 1
    # function, unchanged, with its own trace block (so the component appears
    # twice in the trace: that is the fallback, not a bug). The menu in the
    # prompt is the smallest possible retrieval step; Lecture 5 generalises it.

    trace.doing("pizza_recognition", "nothing implemented yet -> falling back to the rule")
    trace.tier("pizza_recognition", "static", "not implemented")
    return recognize_pizza(state)


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
