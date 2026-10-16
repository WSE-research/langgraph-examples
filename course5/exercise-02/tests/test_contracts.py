"""Component tests -- the contracts of Tasks 3-5, as executable statements.

    pytest -q

These tests are your *definition of done* for the implementation part: with the
skeletons they fail, with a correct implementation they pass. They are also the
first golden reference of the course -- in Iteration 3 you will add numbers to
them, and in Iteration 2 you will run the very same tests against an LLM-backed
component to see whether the contract still holds.

Add your own tests here. A good rule: every case you found in Task 3c/4c/5c that
surprised you becomes a test, so it can never surprise you again.
"""

from __future__ import annotations

import pytest

from pizzabot import pizza_api
from pizzabot.state import new_state
from pizzabot.task3_pizza import recognize_pizza
from pizzabot.task4_address import find_address, recognize_address
from pizzabot.task5_form import REQUIRED, order_form, route, slots_complete


@pytest.fixture(scope="session", autouse=True)
def pizza_api_available():
    """Skip the whole file with a useful message when the API is not reachable."""
    ok, detail = pizza_api.ping()
    if not ok:
        pytest.skip(f"Pizza API at {pizza_api.BASE} is not reachable: {detail}", allow_module_level=True)


# ------------------------------------------------------------------ Task 3 --
@pytest.mark.parametrize(
    "utterance, expected_name",
    [
        ("I would like a Margherita", "Margherita"),
        ("one MARGHERITA please", "Margherita"),          # case insensitive
        ("one Margaritha please", "Margherita"),          # one typo away
        ("do you have Quattro Formaggi?", "Quattro Formaggi"),
    ],
)
def test_pizza_on_the_menu_is_recognized(utterance, expected_name):
    patch = recognize_pizza(new_state(utterance))
    assert patch["slots"]["pizza_name"] == expected_name
    assert patch["slots"]["pizza_id"] == pizza_api.pizza_id_for(expected_name)


@pytest.mark.parametrize("utterance", ["I want sushi", "I am hungry", "hello there"])
def test_unknown_food_is_not_invented(utterance):
    """Guarantee: the slot is only ever written with a name from the menu."""
    patch = recognize_pizza(new_state(utterance))
    assert "slots" not in patch or "pizza_name" not in patch.get("slots", {})


# ------------------------------------------------------------------ Task 4 --
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
def test_complete_address_is_recognized(utterance, expected):
    assert find_address(utterance) == expected


@pytest.mark.parametrize("utterance", ["somewhere near the station", "Rue Michelet", "12b"])
def test_incomplete_address_is_rejected(utterance):
    """Guarantee: complete or nothing -- never a half address in the slot."""
    assert find_address(utterance) is None
    patch = recognize_address(new_state(utterance))
    assert "slots" not in patch or "address" not in patch.get("slots", {})


# ------------------------------------------------------------------ Task 5 --
def test_router_answers_the_question_it_asked():
    state = new_state("5 Rue Michelet, Saint-Étienne")
    state["expected"] = "address"
    assert route(state) == "address_recognition"


def test_router_sends_small_talk_to_help():
    assert route(new_state("good evening")) == "help"


def test_form_asks_for_the_first_missing_slot():
    """The guarantee is 'at most one question per turn, about the slot in expected'.

    Note what is *not* asserted: the wording. A test that pins the sentence is a
    test of your prose, not of your contract -- and it would fail the day you
    improve the question.
    """
    state = new_state("hello")
    patch = order_form(state)
    assert patch["expected"] == REQUIRED[0]
    assert len(patch["messages"]) == len(state["messages"]) + 1      # exactly one
    assert patch["expected"] in ("pizza_name", "address")


def test_form_is_silent_when_the_frame_is_full():
    state = new_state("")
    state["slots"] = {
        "pizza_name": "Margherita",
        "pizza_id": 1,
        "address": {"street": "Rue Michelet", "house_number": "5", "city": "Saint-Étienne"},
    }
    patch = order_form(state)
    assert patch == {"expected": None}          # no question, nothing else
    assert slots_complete(state) is True


def test_slots_complete_is_false_while_a_slot_is_missing():
    state = new_state("")
    state["slots"] = {"pizza_name": "Margherita", "pizza_id": 1}
    assert slots_complete(state) is False
