"""Iteration 2, Task 2 -- one unit test per method. YOUR CODE GOES HERE.

Four methods, four tests, two lists of cases::

    recognize_address       (rule)  ->  ADDRESS_CASES, all of them
    recognize_address_llm   (LLM)   ->  ADDRESS_CASES, THRESHOLD of them
    recognize_pizza         (rule)  ->  PIZZA_CASES,   all of them
    recognize_pizza_llm     (LLM)   ->  PIZZA_CASES,   THRESHOLD of them

Two ideas, and they are the whole task.

**The cases are data, not code.** A case is a pair: a natural-language
utterance and the value the method must return for it. They live in a list at
the top of this file, so that the rule and its LLM-backed substitute are held
to the *same* specification -- one place to read, one place to change. That is
the operational form of substitutability: if the two methods needed different
cases, they would not be implementing the same contract (Liskov & Wing 1994).

**The bar is not the same.** These two rules are *exact*: for every case there
is one right answer and the rule produces it, on every run, so each must pass
*every* case -- a red one means the rule is wrong, or the expected value is.
The LLM-backed methods are *approximate*: the honest question is not "did this
case pass" but "how many did", so their tests assert a **rate** against a
THRESHOLD. Note the criterion: exactness, not who wrote the method. A
similarity-based rule is approximate too and needs a threshold for the same
reason (Task 2c, and slide 2.7). A threshold is a decision, not a constant:
say who chose it, when, and why in a comment next to it -- the constant and its
comment are the record.

pytest is the runner. The same four tests written as `unittest.TestCase`
methods would assert exactly the same things; the structure is the point, not
the framework.

    pytest -q tests/test_recognizers.py            # all four
    pytest -q tests/test_recognizers.py -k rule    # the two exact ones
    pytest -v tests/test_recognizers.py            # one line per case

Write this file BEFORE you implement Tasks 3 and 4. The four tests below are
skipped until you write them; `pytest -q -rs` names them. Once the two rule
tests are written they must be green at once -- the rules have been finished
since Iteration 1, so a red one means your expected value is wrong, not the
rule. The two LLM tests will be green at once as well, and that is worth a
minute of your time: the empty skeletons of Tasks 3 and 4 fall back to the
rule, so they inherit the rule's answers. They only begin to mean something
once the service call is in. Watch the rate move -- in both directions.
"""

from __future__ import annotations

import pytest

from pizzabot import llm_service, pizza_api
from pizzabot.address_llm import recognize_address_llm
from pizzabot.pizza_llm import recognize_pizza_llm
from pizzabot.state import new_state
from pizzabot.task3_pizza import recognize_pizza
from pizzabot.task4_address import recognize_address

needs_key = pytest.mark.skipif(
    not llm_service.configured(),
    reason="the LLM-backed methods need OPENAI_API_KEY in .env (Iteration 1, Task 8)",
)


@pytest.fixture(scope="session", autouse=True)
def pizza_api_available():
    """Both rules call the Pizza API; skip the file with a useful message."""
    ok, detail = pizza_api.ping()
    if not ok:
        pytest.skip(f"Pizza API at {pizza_api.BASE} is not reachable: {detail}", allow_module_level=True)


# --------------------------------------------------------------- the cases --
# TODO 1: five cases per method. The first one of each list is done for you.
#
# A good five: two typical ones, one that is awkward but still inside what the
# rule can do (other word order, filler words, a typo, different case), and two
# that must return NOTHING -- the `failure` row of the contract is a test case,
# not an afterthought. One of those two is worth choosing well: an utterance
# that looks like a perfectly good answer and is rejected for a reason only the
# domain knows (an address outside the delivery area, a pizza that is not on
# the menu).
#
# All five must be cases the RULE gets right -- that is what makes the
# threshold mean something: the LLM-backed method is held to a bar the rule
# clears completely. The cases your rules cannot do (section 6 of Iteration 1)
# do NOT belong here; there is no expected value the rule could be held to.
# They are what Task 6 compares and what Iteration 3 measures.

MICHELET = {"street": "Rue Michelet", "house_number": "5", "city": "Saint-Étienne"}

ADDRESS_CASES: list[tuple[str, dict]] = [
    ("deliver it to 5 Rue Michelet, Saint-Étienne", MICHELET),
    # TODO: four more, at least two of them expecting {}
]

PIZZA_CASES: list[tuple[str, str]] = [
    ("I would like a Margherita", "Margherita"),
    # TODO: four more, at least two of them expecting ""
]

# TODO 2: the bar for the LLM-backed methods. 0.8 means "four of the five".
# It is a decision: put the date and your name in a comment right here.
THRESHOLD = 0.8


# -------------------------------------------------------------- the helpers --
def address_of(method, utterance: str) -> dict:
    """The value under test: the address the method wrote, or {} if none."""
    patch = method(new_state(utterance))
    return patch.get("slots", {}).get("address", {})


def pizza_of(method, utterance: str) -> str:
    """The value under test: the pizza name the method wrote, or "" if none."""
    patch = method(new_state(utterance))
    return patch.get("slots", {}).get("pizza_name", "")


def hit_rate(method, cases, value_of) -> tuple[float, list[str]]:
    """How many of the cases the method got right, and which it did not."""
    misses = []
    for utterance, expected in cases:
        got = value_of(method, utterance)          # exactly one call per case
        if got != expected:
            misses.append(f"{utterance!r}: got {got!r}, expected {expected!r}")
    return (len(cases) - len(misses)) / len(cases), misses


# ------------------------------------------------- the rules: all the cases --
# TODO 3: one parametrized test per rule-based method. `parametrize` turns the
# list into one test per case, so a failure report names the utterance that
# broke -- not "the test". The assertion is an equality: no threshold, no
# tolerance. 5 of 5, on every run.


@pytest.mark.parametrize("utterance, expected", ADDRESS_CASES)
def test_rule_recognize_address(utterance, expected):
    pytest.skip("Task 2 -- TODO 3: assert the rule returns the expected address")


@pytest.mark.parametrize("utterance, expected", PIZZA_CASES)
def test_rule_recognize_pizza(utterance, expected):
    pytest.skip("Task 2 -- TODO 3: assert the rule returns the expected pizza name")


# --------------------------------- the LLM-backed methods: the threshold ----
# TODO 4: one test per LLM-backed method, over the SAME list. One loop instead
# of five tests, because the question is "how many", and one assertion against
# THRESHOLD. Put the misses into the assertion message: the whole value of this
# test is that it tells you which utterance the model got wrong, so that you
# can decide whether it is the prompt, the check, or your expected value.


@needs_key
def test_llm_recognize_address_passes_the_threshold():
    pytest.skip("Task 2 -- TODO 4: assert hit_rate(...) >= THRESHOLD, and report the misses")


@needs_key
def test_llm_recognize_pizza_passes_the_threshold():
    pytest.skip("Task 2 -- TODO 4: assert hit_rate(...) >= THRESHOLD, and report the misses")
