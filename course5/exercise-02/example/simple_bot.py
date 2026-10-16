"""The warm-up example: two nodes, one rule-based, one LLM-backed. GIVEN.

This is the whole of Iteration 2 in one readable file, with everything that
makes the real bot big taken out: no Pizza API, no order form, no router, no
fallback, no configurations. Two nodes, one state, one prompt file.

    pizza_recognition     rule-based:  the name has to be on the menu, spelled
                                       as the menu spells it (case ignored)
    address_recognition   LLM-backed:  the model reads the message, we check
                                       the answer, and today the address is
                                       only a postcode and a city

Run it (the key from the lecture hall has to be in ../.env)::

    python example/simple_bot.py --interactive     # you type the sentences
    python example/simple_bot.py                   # four sentences chosen here
    python example/simple_bot.py "one Diavola to 42000 Saint-Étienne"

Test it::

    python -m pytest -q example/example_tests.py -v

The two unit tests next to it are the point of the example as much as the code
is: the rule is deterministic, so its test asserts equality on every case; the
model is not, so its test asserts a *rate* against a threshold. Same cases,
different bar.

What you change in this file, and where:

    Task 2b   ADDRESS_FIELDS and the prompt: the address gains a street and a
              house number. The schema check and the domain check are written
              over ADDRESS_FIELDS, so they follow on their own -- the prompt
              and the test cases are the work.
    Task 2c   recognize_pizza_name: the literal menu lookup becomes a
              similarity function, and "Margaritha" starts being understood.
    Task 2d   recognize_pizza_name again, this time all three options in one
              method: exact, then similarity, then the model -- cheapest
              first. Which option answered goes into LAST_TIER, which is a
              diagnostic and not process data, exactly like `trace.TIERS` in
              the real bot.

All three are changes of the *implementation*: `pizza_name` is still a menu
name or nothing, `address` is still complete or nothing. The contracts hold --
which is the only reason three implementations may hide behind one method.
"""

from __future__ import annotations

import os
import sys
import unicodedata
from typing import TypedDict

# so that `python example/simple_bot.py` finds the repository root, like
# `python -m example.simple_bot` does
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import END, START, StateGraph  # noqa: E402

from pizzabot import llm_service, log# noqa: E402

# The menu, hard-coded here so that the example needs no Pizza API.
MENU = ["Margherita", "Quattro Formaggi", "Diavola", "Regina", "Calzone"]

# The fields the address consists of -- Task 2b adds "street" and "house_number".
ADDRESS_FIELDS = ("postcode", "city")

# The prompt is a file, not a string in the code -- Task 2b writes a v2 of it.
ADDRESS_PROMPT = "example_address_v1"

# Given for Task 2d: the prompt of the third stage of the pizza cascade. The
# component puts the menu into it in place of <MENU>.
PIZZA_PROMPT = "example_pizza_v1"


class OrderState(TypedDict):
    """Three keys: what the customer said, and the two things we recognise."""

    input: str
    pizza_name: str
    address: dict


def fold(text: str) -> str:
    """Lower-case and without accents, so that Saint-Etienne == saint-étienne."""
    stripped = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in stripped if not unicodedata.combining(c))


# ------------------------------------------------------- the rule-based node --
LAST_TIER = ""          # Task 2d: which option answered, for the trace only


def recognize_pizza_name(text: str) -> str:
    """The pizza the customer named, spelled as the menu spells it, or "".

    Contract
        reads       the customer's message
        writes      pizza_name
        guarantee   the answer is a name from MENU, or "" -- never anything else
        failure     "": nothing on the menu was named; the process would ask

    The rule: the menu name occurs in the message, upper and lower case
    ignored. Nothing more. "Margaritha" is therefore not recognised -- that is
    a limitation on purpose, and Task 2c is where you lift it.
    """
    lowered = fold(text)
    for name in MENU:
        if fold(name) in lowered:
            return name
    return ""


# -------------------------------------------------------- the LLM-backed node --
def recognize_address(text: str) -> dict:
    """The delivery address in the message, or {}.

    Contract
        reads       the customer's message
        calls       the LLM service with prompts/example_address_v1.txt
        writes      address
        guarantee   *complete or nothing*: every field of ADDRESS_FIELDS is
                    present and was copied from the message, or {} is returned
        failure     {}: the service could not answer, or an answer failed a
                    check; the process would ask

    The model proposes, the two checks decide. The schema check asks whether
    the answer has the shape we asked for; the domain check asks whether it is
    true of *this* message -- a model may return a perfectly well-shaped city
    that nobody mentioned.
    """
    answer = llm_service.extract(llm_service.load_prompt(ADDRESS_PROMPT), text)

    # schema check: exactly our fields, all of them non-empty strings
    if not isinstance(answer, dict):
        return {}
    if set(answer) != set(ADDRESS_FIELDS):
        return {}
    if not all(isinstance(answer[f], str) and answer[f].strip() for f in ADDRESS_FIELDS):
        return {}

    # domain check: every value has to occur in the message -- nothing invented
    message = fold(text)
    if not all(fold(answer[f]) in message for f in ADDRESS_FIELDS):
        return {}

    return {f: answer[f].strip() for f in ADDRESS_FIELDS}


# ------------------------------------------------------------------- the graph --
def pizza_node(state: OrderState) -> dict:
    return {"pizza_name": recognize_pizza_name(state["input"])}


def address_node(state: OrderState) -> dict:
    return {"address": recognize_address(state["input"])}


def build_graph():
    """Two nodes in a row: the same shape as the real bot, four sizes smaller."""
    workflow = StateGraph(OrderState)
    workflow.add_node("pizza_recognition", pizza_node)
    workflow.add_node("address_recognition", address_node)
    workflow.add_edge(START, "pizza_recognition")
    workflow.add_edge("pizza_recognition", "address_recognition")
    workflow.add_edge("address_recognition", END)
    return workflow.compile()


def run(graph, sentence: str) -> None:
    """One sentence through both nodes, reported the same way in both modes."""
    state = graph.invoke({"input": sentence, "pizza_name": "", "address": {}})
    log.plain()
    log.step(f"  input   : {sentence}")
    log.plain(f"  pizza   : {state['pizza_name'] or '<nothing recognised>'}")
    log.plain(f"  address : {state['address'] or '<nothing recognised>'}")


def interactive(graph) -> None:
    """Type the sentences yourself, one per line.

    Task 2a starts here, before anything is read or changed: a sentence you
    typed yourself and watched go through both nodes is evidence that your key,
    your environment and the model endpoint work. The four-sentence run below
    proves the same thing, but it is the file that chose the sentences -- and a
    student who has only ever seen the scripted run does not yet know whether
    the bot answers *them*.
    """
    log.step("  type a sentence and press Enter; empty line, 'quit' or Ctrl-D ends it")
    while True:
        try:
            sentence = log.prompt("\nyou: ").strip()
        except (EOFError, KeyboardInterrupt):
            log.plain()
            break
        if not sentence or sentence.lower() in {"quit", "exit"}:
            break
        run(graph, sentence)


def main(argv: list[str]) -> int:
    arguments = argv[1:]
    wants_interactive = bool({"-i", "--interactive"} & set(arguments))
    sentences = [a for a in arguments if a not in {"-i", "--interactive"}] or [
        "I would like a Margherita, delivered to 42000 Saint-Étienne",
        "one Diavola to Lyon, 69001",
        "one Margaritha please",          # Task 2c makes this one work
        "deliver to Saint-Étienne",       # no postcode -> complete or nothing
    ]
    if not llm_service.configured():
        log.fail("no key in .env", "the address node cannot answer")
        log.hint("paste the key from the lecture hall into .env (OPENAI_API_KEY)")
        return 1

    graph = build_graph()
    if wants_interactive:
        interactive(graph)
    else:
        for sentence in sentences:
            run(graph, sentence)
    log.plain()
    log.result(llm_service.service().usage.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
