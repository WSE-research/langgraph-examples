"""Task 2 -- YOUR hand-written test cases. The first quality statement of this session.

Before anything is generated, you write cases yourself. Five per method, by hand,
because writing them is how you find out what your bot is actually promising --
and because the generated set later has to be compared against something a human
chose.

Fill the three lists below. One case is a pair::

    ("what the user types", what the component must write into the slot)

and `None` is a legitimate expected value: it means **the component must
recognise nothing**. At least one of your five per method has to be such a case.
A test suite in which nothing is ever refused measures half a contract.

Run it::

    pytest -q tests/test_manual_cases.py                 # against the static configuration
    BOT_CONFIG=llm pytest -q tests/test_manual_cases.py  # against the LLM configuration
    pytest -q tests/test_manual_cases.py -rs             # ... and show what is still skipped

Two kinds of test over the same cases, and the difference between them is the
lesson: **refusing is exact** (a guarantee that holds four times out of five is
not a guarantee), **recognising is a rate** (`THRESHOLD`). That is the same split
Iteration 2 made between a rule test and a threshold test -- now with your cases
behind it.

You are done with this task when: `pytest -q -m gate tests/test_manual_cases.py`
is green for all three methods, `pytest -q tests/test_manual_cases.py` is green,
and you can say which of your cases the static configuration fails and which the
LLM configuration fails. They will not be the same cases -- that difference is
the first finding of the session.

Note the division of labour with `evaluate.py`: these cases are *yours*, few, and
chosen; the generated ones are many and drawn from the graph. Both are scored by
exactly the same `score()` function, so the two numbers can be put in one table.
"""

import pytest

from evaluate import METHODS, fold, score, wilson

#: The rate a method must reach over YOUR cases. Write the number down before
#: you run the tests for the first time -- that is what makes it a threshold and
#: not a description of the result you happened to get.
THRESHOLD = 0.80

#: At least this many cases per method, at least one of them a refusal.
MINIMUM = 5


# ---------------------------------------------------------------------------
# address_recognition -- expected: a complete record, or None
# ---------------------------------------------------------------------------

MANUAL_ADDRESS = [
    ("deliver it to 5 Rue Michelet, Saint-Étienne",
     {"street": "Rue Michelet", "house_number": "5", "city": "Saint-Étienne"}),
    # TODO: four more. Ideas that are worth a case, one each:
    #   * the other word order ("Rue Michelet 5, Saint-Étienne")
    #   * a spelling a real customer uses ("St. Etienne", "R. Michelet")
    #   * a HALF address -- street and city, no number -> None (complete or nothing)
    #   * a city outside the delivery area -> None (the refusal case)
]

# ---------------------------------------------------------------------------
# pizza_recognition -- expected: the id from GET /pizza, or None
# ---------------------------------------------------------------------------

MANUAL_PIZZA = [
    ("I would like a Margherita", 1),
    # TODO: four more. Ideas:
    #   * a misspelling ("Margaritha")
    #   * a descriptive name ("the four cheese one")
    #   * something we do not sell ("a Tartufo") -> None
    #   * a sentence with no pizza in it at all -> None
]

# ---------------------------------------------------------------------------
# the two of them in one utterance -- expected: (pizza id, address record)
# ---------------------------------------------------------------------------

MANUAL_ORDER = [
    ("I would like one Diavola to 12b Avenue de la Libération, Saint-Étienne",
     (8, {"street": "Avenue de la Libération", "house_number": "12b", "city": "Saint-Étienne"})),
    # TODO: four more. At least one where ONE of the two is recognisable and the
    # other is not -- a component that drags its neighbour down with it is a
    # contract violation you want to find here and not in the closing round.
]


CASES = {
    "address_recognition": [(text, {"address": expected}) for text, expected in MANUAL_ADDRESS],
    "pizza_recognition": [(text, {"pizza_id": expected}) for text, expected in MANUAL_PIZZA],
    "pizza_and_address": [(text, {"pizza_id": pizza, "address": address})
                          for text, (pizza, address) in MANUAL_ORDER],
}


def run(implementations, method_name: str, utterance: str) -> dict:
    """The components of one method, in order, over one utterance."""
    from pizzabot.state import new_state

    state = new_state(utterance)
    for component in METHODS[method_name]["components"]:
        state = {**state, **implementations[component](state)}
    return state.get("slots", {})


@pytest.mark.gate
@pytest.mark.parametrize("method_name", list(CASES))
def test_enough_cases(method_name):
    """Five per method, one of them a refusal. This test is the task's checklist."""
    cases = CASES[method_name]
    assert len(cases) >= MINIMUM, (
        f"{method_name}: {len(cases)} case(s) written, {MINIMUM} needed -- "
        f"fill MANUAL_{method_name.split('_')[0].upper()} in this file")
    refusals = [case for case in cases if all(value is None for value in case[1].values())]
    assert refusals, (
        f"{method_name}: no case expects 'nothing recognised'. A contract has a "
        f"failure clause; a test set without one does not test it.")


@pytest.mark.parametrize("method_name", list(CASES))
def test_a_refusal_is_never_answered_with_a_value(implementations, method_name):
    """The exact half of the contract: what the component promises NOT to do.

    Recognising a value is approximate -- it gets a threshold, below. Refusing is
    not: "nothing recognised -> write nothing" is a guarantee, and a guarantee
    that holds 80 % of the time is not a guarantee. Every case of yours whose
    expected value is None is checked here, one assertion each, both
    configurations.
    """
    cases = [case for case in CASES[method_name]
             if any(value is None for value in case[1].values())]
    if not cases:
        pytest.skip(f"{method_name}: no refusal case written yet")
    failures = []
    for utterance, expected in cases:
        slots = run(implementations, method_name, utterance)
        for field, want in expected.items():
            if want is None and slots.get(field) is not None:
                failures.append(f"{utterance!r}: {field} had to stay empty, got {slots.get(field)!r}")
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("method_name", list(CASES))
def test_pass_rate_over_the_hand_written_cases(implementations, method_name):
    """The same cases as a rate, with the interval printed.

    This is the test that survives into the generated world: with five cases the
    interval is embarrassingly wide, and seeing *how* wide is the point. Compare
    it with the interval `evaluate.py` prints for 50 generated ones.
    """
    cases = CASES[method_name]
    if len(cases) < MINIMUM:
        pytest.skip(f"{method_name}: only {len(cases)} case(s) written so far")
    hits = sum(all(score(run(implementations, method_name, utterance).get(field), want, None)
                   for field, want in expected.items())
               for utterance, expected in cases)
    rate = hits / len(cases)
    low, high = wilson(hits, len(cases))
    assert rate >= THRESHOLD, (
        f"{method_name}: {hits}/{len(cases)} = {rate:.2f} < {THRESHOLD}, "
        f"95% CI [{low:.2f}, {high:.2f}]")


def test_the_scorer_treats_a_copied_wording_as_the_same_answer():
    """Read this one: it is the whole leniency of this harness, and its limit."""
    accepted = {"city": ["Saint-Étienne", "St. Etienne", "saint-etienne"]}
    assert score({"city": "St. Etienne"}, {"city": "Saint-Étienne"}, accepted)
    assert not score({"city": "Lyon"}, {"city": "Saint-Étienne"}, accepted)
    assert fold("St. Étienne") == fold("st. etienne")
    assert score(None, None, None)                    # a refusal, answered correctly
    assert not score({"city": "Lyon"}, None, None)    # answered something where nothing was right
