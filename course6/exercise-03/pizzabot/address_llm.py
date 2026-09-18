"""Task 3 -- REFERENCE SOLUTION: address recognition, LLM-backed.

Contract -- the SAME contract as in Iteration 1 (pizzabot/task4_address.py).

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
                   Iteration 1 rule decides
    guarantee   *complete or nothing* -- unchanged. In addition: a street, city
                or house number the model invented never reaches the slot.
    failure     empty patch `{}`; the order form asks -- unchanged
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
# 12b, "12 b", and the French forms 5 bis / 12 ter / 3 quater -- our domain, our pattern
HOUSE_NUMBER = re.compile(r"\d+\s?(?:[a-z]|bis|ter|quater)?")

DOMAIN_CHECKS = ("house-number pattern and digits copied", "street and city copied from the input", "POST /address/validate")


class AddressModel(BaseModel):
    """The schema = the output contract of the service call, checked on OUR side."""

    model_config = ConfigDict(extra="forbid")

    street: str = Field(min_length=1)
    house_number: str = Field(min_length=1)
    city: str = Field(min_length=1)


def fold(text: str) -> str:
    """Compare without accents and without case: "Saint-Etienne" is "Saint-Étienne"."""
    stripped = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in stripped if not unicodedata.combining(ch)).casefold()


def plausible(address: AddressModel, text: str) -> tuple[bool, str]:
    """Rule 3, the domain check: schema-valid is not domain-valid."""
    folded = fold(text)
    number = address.house_number.strip().lower()
    if HOUSE_NUMBER.fullmatch(number) is None:
        return False, f"house number {address.house_number!r} is not a number"
    digits = re.match(r"\d+", number).group()
    if digits not in text:
        return False, f"house number {digits!r} does not occur in the utterance"
    if fold(address.street) not in folded:
        return False, f"street {address.street!r} does not occur in the utterance"
    if fold(address.city) not in folded:
        return False, f"city {address.city!r} does not occur in the utterance"
    if not pizza_api.validate_address(address.street, address.house_number, address.city):
        return False, f"the API does not deliver to {address.city!r}"
    return True, ""


def recognize_address_llm(state: ChatbotState) -> dict:
    """Same signature, same contract, same patch as recognize_address."""
    trace.received("address_recognition", state, "input", "slots", "expected")

    raw = llm_service.extract(SYSTEM, state["input"])                     # 1. the call
    if raw is None:
        trace.tier("address_recognition", "static", "the service failed -> the rule decides")
        return recognize_address(state)
    if raw == {}:
        trace.tier("address_recognition", "static", "the model saw no complete address -> the rule decides")
        return recognize_address(state)
    try:
        address = AddressModel(**raw)                                      # 2. schema check
    except (ValidationError, TypeError) as error:
        trace.tier("address_recognition", "static",
                   f"schema check failed ({type(error).__name__}) -> the rule decides")
        return recognize_address(state)
    ok, why = plausible(address, state["input"])                           # 3. domain check
    if not ok:
        trace.tier("address_recognition", "static", f"{why} -> the rule decides")
        return recognize_address(state)

    trace.doing("address_recognition", f"schema ok, domain ok (number, copied, deliverable): {address.model_dump()}")
    trace.tier("address_recognition", "llm")
    slots = {**state["slots"], "address": address.model_dump()}
    return trace.returns("address_recognition", {"slots": slots}, next_step="order_form (fixed edge)")


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
