"""The two unit tests of the warm-up example. GIVEN, and green.

    python -m pytest -q example/example_tests.py          # both tests
    python -m pytest -q example/example_tests.py -v       # one line per case

The file is called `example_tests.py`, not `test_*.py`, so that the suite of
the main exercise (`pytest -q` in the repository root) does not pick it up.
The example is a sandbox; it has its own run.

**One list of cases per method.** A case is a pair: what the customer says, and
the value the method must return for it. The list is data at the top of the
file, not code buried in a test body, so that the specification can be read,
reviewed and extended in one place.

**Two different bars, and the reason is not "rule versus model".** The rule
below is *exact*: for every case there is one right answer and it produces it,
every time, so its test asserts equality on all five. The LLM-backed method is
*approximate*: it will be right most of the time and the honest question is how
often, so its test asserts a rate against a THRESHOLD. In Task 2c the pizza
rule becomes approximate too -- a similarity function is a rule and still has
no guaranteed answer -- and its test then needs a threshold for exactly the
same reason. Exactness is the criterion, not who wrote the method.

What you change, and where:

    Task 2b   ADDRESS_CASES: every expected value gains a street and a house
              number, and two cases have to be rewritten, because "42000
              Saint-Étienne" is no longer a complete address.
    Task 2c   PIZZA_CASES: "one Margaritha please" now expects "Margherita",
              more near-miss cases join it, and the test becomes a rate against
              PIZZA_THRESHOLD.
    Task 2d   a third list, CASCADE_CASES, of (utterance, expected tier) --
              and a test that asserts it case by case. Which option answered
              is *exact* even though what the model answers is not: stages 1
              and 2 are deterministic, so whether a sentence reaches the
              network at all is a fact about the cascade. It is the test that
              goes red if somebody reorders the stages.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from example.simple_bot import recognize_address, recognize_pizza_name  # noqa: E402
from pizzabot import llm_service  # noqa: E402

# --------------------------------------------------------------- the cases --
PIZZA_CASES: list[tuple[str, str]] = [
    ("I would like a Margherita", "Margherita"),
    ("one margherita please", "Margherita"),              # case is ignored
    ("do you have Quattro Formaggi?", "Quattro Formaggi"),
    ("I want sushi", ""),                                 # not a pizza
    ("one Margaritha please", ""),                        # a typo -- Task 2c
]

SAINT_ETIENNE = {"postcode": "42000", "city": "Saint-Étienne"}

ADDRESS_CASES: list[tuple[str, dict]] = [
    ("deliver it to 42000 Saint-Étienne", SAINT_ETIENNE),
    ("Saint-Étienne, 42000, please", SAINT_ETIENNE),
    ("bring it to Lyon, 69001", {"postcode": "69001", "city": "Lyon"}),
    ("deliver to Saint-Étienne", {}),                     # no postcode
    ("somewhere near the station", {}),                   # no address at all
]

# The bar for the LLM-backed method: 0.8 means "four of these five".
# A number that decides whether a build is green is a decision, not a constant:
# it belongs next to the guarantee in the contract, with a date and an owner.
ADDRESS_THRESHOLD = 0.8

needs_key = pytest.mark.skipif(
    not llm_service.configured(),
    reason="the address node needs OPENAI_API_KEY in .env -- the key from the lecture hall",
)


def hit_rate(method, cases) -> tuple[float, list[str]]:
    """How many of the cases the method got right, and which it did not."""
    misses = []
    for utterance, expected in cases:
        got = method(utterance)                  # exactly one call per case
        if got != expected:
            misses.append(f"{utterance!r}: got {got!r}, expected {expected!r}")
    return (len(cases) - len(misses)) / len(cases), misses


# -------------------------------------- the rule: every case, on every run --
@pytest.mark.parametrize("utterance, expected", PIZZA_CASES)
def test_recognize_pizza_name(utterance, expected):
    """`parametrize` makes one test per case, so a failure names the utterance."""
    assert recognize_pizza_name(utterance) == expected


# ------------------------------------------ the model: the same cases, a rate --
@needs_key
def test_recognize_address_passes_the_threshold():
    """One loop instead of five tests: the question is "how many", not "did it".

    The misses are in the assertion message on purpose. That is the value of
    this test: it names the sentence the model got wrong, so that you can
    decide whether the prompt, a check, or your expected value is to blame.
    """
    rate, misses = hit_rate(recognize_address, ADDRESS_CASES)
    assert rate >= ADDRESS_THRESHOLD, (
        f"{rate:.0%} < {ADDRESS_THRESHOLD:.0%}\n" + "\n".join(misses))
