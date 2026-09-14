"""Iteration 2 -- the contracts of the two recognizers, run against BOTH implementations.

    pytest -q                 # every test in this file runs twice: [static] and [llm]
    pytest -q -k static       # only the rules
    pytest -q -k llm          # only the LLM-backed components (needs the key)
    pytest -v -k llm          # shows the [llm-...] test ids

Read the tests carefully: nothing in them says which implementation is under
test. They take the component from the `implementation` fixture (conftest.py),
which pytest fills once per configuration. The assertions are the same
statements as in Iteration 1's tests/test_contracts.py -- only the entry point
moved from the pure helper to the node, because the contract is the node's.
A contract that holds for a regular expression must hold for a language
model, or the substitution is not a substitution: the assertions are the
postconditions, the fixture is the substitution (Liskov & Wing 1994,
doi:10.1145/197320.197383; Meyer 1992, doi:10.1109/2.161279).

Your own Iteration 1 tests stay where they are, in tests/test_contracts.py.
Add new cases here: every row of the comparison that surprised you, and every
hostile utterance of the adversarial round that found a gap.
"""

from __future__ import annotations

import pytest

from pizzabot import pizza_api
from pizzabot.graph import build_graph
from pizzabot.state import new_state


@pytest.fixture(scope="session", autouse=True)
def pizza_api_available():
    """Skip the whole file with a useful message when the API is not reachable."""
    ok, detail = pizza_api.ping()
    if not ok:
        pytest.skip(f"Pizza API at {pizza_api.BASE} is not reachable: {detail}", allow_module_level=True)


# --------------------------------------------- pizza_recognition, both ways --
@pytest.mark.parametrize(
    "utterance, expected_name",
    [
        ("I would like a Margherita", "Margherita"),
        ("one MARGHERITA please", "Margherita"),          # case insensitive
        ("one Margaritha please", "Margherita"),          # one typo away
        ("do you have Quattro Formaggi?", "Quattro Formaggi"),
    ],
)
def test_pizza_on_the_menu_is_recognized(implementation, utterance, expected_name):
    recognize_pizza = implementation["pizza_recognition"]
    patch = recognize_pizza(new_state(utterance))
    assert patch["slots"]["pizza_name"] == expected_name
    assert patch["slots"]["pizza_id"] == pizza_api.pizza_id_for(expected_name)


@pytest.mark.parametrize("utterance", ["I want sushi", "I am hungry", "hello there", "One Pizza Napoli please"])
def test_no_pizza_means_no_slot(implementation, utterance):
    """Expected value: none of these utterances names a pizza, so nothing is written.

    Not a guarantee test: `Margherita` for "I am hungry" would keep the
    guarantee (a name on the menu) and still fail here. This is the one test
    in the suite that is statistical by nature for a model -- with a weaker
    prompt it failed 2 times in 10 on 2026-09-12. Lecture 3 starts there.
    """
    recognize_pizza = implementation["pizza_recognition"]
    patch = recognize_pizza(new_state(utterance))
    assert "slots" not in patch or "pizza_name" not in patch.get("slots", {})


def test_pizza_slot_always_carries_the_menu_spelling(implementation):
    """Guarantee: whatever the implementation answers, the slot is a menu name, spelled as the menu spells it."""
    recognize_pizza = implementation["pizza_recognition"]
    patch = recognize_pizza(new_state("a quattro formaggi, please"))
    if "slots" in patch and "pizza_name" in patch["slots"]:
        assert patch["slots"]["pizza_name"] in pizza_api.menu_names()


# ------------------------------------------- address_recognition, both ways --
@pytest.mark.parametrize(
    "utterance, expected",
    [
        ("deliver it to 5 Rue Michelet, Saint-Étienne",
         {"street": "Rue Michelet", "house_number": "5", "city": "Saint-Étienne"}),
        ("please deliver to 12b Rue de la Paix, Lyon",
         {"street": "Rue de la Paix", "house_number": "12b", "city": "Lyon"}),
        ("Karl-Liebknecht-Strasse 132, Leipzig",
         {"street": "Karl-Liebknecht-Strasse", "house_number": "132", "city": "Leipzig"}),
    ],
)
def test_complete_address_is_recognized(implementation, utterance, expected):
    recognize_address = implementation["address_recognition"]
    patch = recognize_address(new_state(utterance))
    assert patch["slots"]["address"] == expected


@pytest.mark.parametrize("utterance", ["somewhere near the station", "Rue Michelet", "12b", "deliver to Lyon", ""])
def test_incomplete_address_is_rejected(implementation, utterance):
    """Guarantee: complete or nothing -- never a half address in the slot."""
    recognize_address = implementation["address_recognition"]
    patch = recognize_address(new_state(utterance))
    assert "slots" not in patch or "address" not in patch.get("slots", {})


def test_address_outside_the_delivery_area_is_rejected(implementation):
    """Rule 3 of the Iteration 1 contract: the delivery area is a domain rule only the API knows."""
    recognize_address = implementation["address_recognition"]
    patch = recognize_address(new_state("deliver to 1 Rue de Rivoli, Paris"))
    assert "slots" not in patch or "address" not in patch.get("slots", {})


# ---------------------------------------------- the seam (Task 5) --------------
def test_graph_uses_the_injected_implementation():
    """build_graph must wire what it is given -- otherwise `--config llm` runs the rules.

    Two fake implementations that write marker values are the cheapest proof;
    each invocation kills one half of the "forgot Task 5a" mutant. This is the
    mutant test of Iteration 1 (DeMillo, Lipton & Sayward 1978), one level up.
    """
    def marker_pizza(state):
        return {"slots": {**state["slots"], "pizza_name": "MARKER", "pizza_id": -1}}

    def marker_address(state):
        return {"slots": {**state["slots"], "address": {"street": "MARKER", "house_number": "0", "city": "MARKER"}}}

    def silent(state):
        return {}

    graph = build_graph({"pizza_recognition": marker_pizza, "address_recognition": silent})
    state = graph.invoke(new_state("I would like a pizza"))
    assert state["slots"].get("pizza_name") == "MARKER"        # the pizza half is injected

    graph = build_graph({"pizza_recognition": silent, "address_recognition": marker_address})
    state = graph.invoke(new_state("I would like a pizza"))
    assert state["slots"].get("address", {}).get("street") == "MARKER"   # the address half too
    assert state["order_id"] is None                             # the form asked for the pizza; nothing was ordered


def test_both_configurations_complete_the_same_order(implementation):
    """Part C of Lecture 2: the lecture example ends in the same state either way."""
    graph = build_graph(implementation)
    state = graph.invoke(new_state("I would like a Margherita, delivered to 5 Rue Michelet, Saint-Étienne"))
    assert state["slots"]["pizza_name"] == "Margherita"
    assert state["slots"]["address"] == {"street": "Rue Michelet", "house_number": "5", "city": "Saint-Étienne"}
    assert state["order_id"] is not None and state["ended"] is True
