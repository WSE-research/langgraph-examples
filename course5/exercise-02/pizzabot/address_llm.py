"""Task 3 -- address recognition, LLM-backed. YOUR CODE GOES HERE.

Contract -- the SAME contract as in Iteration 1 (pizzabot/task4_address.py).
Do not change it; implement it a second time, with a model behind it.

    name        address_recognition        (this implementation: recognize_address_llm)
    reads       state["input"], state["slots"], state["expected"]
    writes      slots.address
    calls       the LLM service with prompts/address_v1.txt, through pizzabot/llm_service.py
                POST /address/validate, through pizzabot/pizza_api.py
                recognize_address from Iteration 1 -- as the fallback
    rules       1. ask the service for street, house_number, city as JSON
                2. schema check: exactly those three keys, all non-empty strings
                3. domain check: the house number matches HOUSE_NUMBER and its
                   digits occur in the utterance; street and city occur in the
                   utterance (copied, never invented); the Pizza API accepts the
                   address (delivery area)
                4. the service answered None or {}, or a check failed -> the
                   Iteration 1 rule decides. The rule is the guaranteed
                   minimum, not dead code.
    guarantee   *complete or nothing* -- unchanged. In addition: a street, city
                or house number the model invented never reaches the slot.
    failure     empty patch `{}`; the order form asks -- unchanged

What changed against Iteration 1, and what did not: `reads`, `writes`,
`guarantee` and `failure` are the contract -- they do not change (a substitute
may promise more, never less, and may demand nothing more). `calls` and `rules`
describe the implementation -- they do change: the model proposes, the checks
decide, and the Iteration 1 rules become the fallback. For a model the `rules`
row can only list the checks and the fallback; the mapping from input to output
is no longer a rule you can write down -- which is why Iteration 3 needs a
dataset. The structure -- a primary, an acceptance test, an alternate -- is
Randell's recovery block (IEEE TSE 1975).

Run just this component:

    python -m pizzabot.address_llm "number 5 in the Rue Michelet here in Saint-Étienne"

Task 3a  draw the component with its two checks and its fallback before you code.
Task 3b  implement the two TODOs below.
Task 3c  compare both implementations on your own cases: python compare_configs.py --address
"""

from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pizzabot import llm_service, log, pizza_api, trace
from pizzabot.state import ChatbotState
from pizzabot.task4_address import recognize_address        # the fallback: the rule (tier "static")

PROMPT_VERSION = "address_v1"                                # prompts/address_v1.txt
SYSTEM = llm_service.load_prompt(PROMPT_VERSION)
HOUSE_NUMBER = re.compile(r"\d+\s?[a-z]?")                  # 5, 12b, "12 b" -- extend it for "5 bis"

# The three domain checks, named -- compare_configs.py prints this on the service card.
DOMAIN_CHECKS = ("house-number pattern", "values copied from the input", "POST /address/validate")


class AddressModel(BaseModel):
    """The schema = the output contract of the service call, checked on OUR side.

    `extra="forbid"` is `additionalProperties: false` in JSON Schema terms;
    `min_length=1` rejects the empty strings some models answer for a missing
    part instead of `{}`.
    """

    model_config = ConfigDict(extra="forbid")

    street: str = Field(min_length=1)
    house_number: str = Field(min_length=1)
    city: str = Field(min_length=1)


def fold(text: str) -> str:
    """GIVEN. Compare without accents and without case: "saint-etienne" is "Saint-Étienne".

    The model may normalise an accent the user typed (or add one the user did
    not type); the API compares cities the same way, so the copy check must too.
    """
    stripped = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in stripped if not unicodedata.combining(ch)).casefold()


def plausible(address: AddressModel, text: str) -> tuple[bool, str]:
    """Rule 3, the domain check: schema-valid is not domain-valid.

    Returns (ok, reason). Three checks; the folding helper is given above.

    TODO 1: a) the house number matches HOUSE_NUMBER completely (re.fullmatch)
               and its digits occur in the utterance
               -> "five", "42000, Saint-Étienne" and a number the model took
                  from the prompt's example are rejected
            b) street and city occur in the utterance -- compare fold(value)
               in fold(text), so that accents and case do not matter
               -> the model copied them; it did not invent Lyon for Saint-Étienne
            c) pizza_api.validate_address(street, house_number, city) says yes
               -> the delivery area is a domain rule that only the API knows
            Return (False, "<which check, in five words>") on the first failure,
            (True, "") when all three hold. The reason ends up in the trace, and
            the trace is what you read in the adversarial round.
    """
    return True, ""


def recognize_address_llm(state: ChatbotState) -> dict:
    """Same signature, same contract, same patch as recognize_address."""
    trace.received("address_recognition", state, "input", "slots", "expected")

    # TODO 2: the tiered flow -- service call, schema check, domain check, fallback.
    #
    #   raw = llm_service.extract(SYSTEM, state["input"])          # 1. the call
    #   if raw is None:  -> trace.tier("address_recognition", "static", "the service failed -> the rule decides")
    #                       return recognize_address(state)
    #   if raw == {}:    -> trace.tier(..., "static", "the model saw no complete address -> the rule decides")
    #                       return recognize_address(state)        # {} is the model's own "I cannot"
    #   try:
    #       address = AddressModel(**raw)                            # 2. schema check
    #   except (ValidationError, TypeError):
    #       -> trace.tier(..., "static", "schema check failed -> the rule decides"); return recognize_address(state)
    #   ok, why = plausible(address, state["input"])                 # 3. domain check
    #   if not ok:
    #       -> trace.tier(..., "static", why + " -> the rule decides"); return recognize_address(state)
    #   trace.doing("address_recognition", "schema ok, domain ok -> writing the slot")
    #   trace.tier("address_recognition", "llm")
    #   slots = {**state["slots"], "address": address.model_dump()}
    #   return trace.returns("address_recognition", {"slots": slots}, next_step="order_form (fixed edge)")
    #
    # Note what the patch does NOT contain: `expected` belongs to the order form,
    # exactly as in Iteration 1. And note the order of the checks: shape first
    # (cheap, exact), meaning second (cheap, domain), the rule last (it always
    # has an answer). A domain rejection is not a transient fault: fall back, do
    # not ask the model again. When the rule runs, it logs its own block, so the
    # trace shows the component twice -- that is the fallback, not a bug.

    trace.doing("address_recognition", "nothing implemented yet -> falling back to the rule")
    trace.tier("address_recognition", "static", "not implemented")
    return recognize_address(state)


def build_graph():
    """A one-node graph, so this component can be run on its own."""
    from langgraph.graph import END, START, StateGraph

    workflow = StateGraph(ChatbotState)
    workflow.add_node("address_recognition", recognize_address_llm)
    workflow.add_edge(START, "address_recognition")
    workflow.add_edge("address_recognition", END)
    return workflow.compile()


if __name__ == "__main__":
    import sys

    from pizzabot.state import last_message, new_state

    utterance = sys.argv[1] if len(sys.argv) > 1 else "number 5 in the Rue Michelet here in Saint-Étienne"
    result = build_graph().invoke(new_state(utterance))
    log.plain()
    log.result(f"slots : {result['slots']}")
    log.plain(f"tier  : [{trace.last_tier('address_recognition')}]")
    log.plain(f"bot   : {last_message(result) or '(said nothing)'}")
    log.detail(f"usage : {llm_service.service().usage.summary()}", indent="")
