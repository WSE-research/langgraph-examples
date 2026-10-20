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

Write the expected value from the **contract**: the address as the catalog names
it ("Athens", "12b"). The comparison rule is the same as in `evaluate.py` --
an answer is right when it names the same individual: "Athina", "ATHENS" or
"12 b" for the same city and house number all count.

Run it::

    pytest -q -m gate tests/test_manual_cases.py         # did you write five per method?
    pytest -q tests/test_manual_cases.py                 # the static configuration
    BOT_CONFIG=llm pytest -q tests/test_manual_cases.py  # the LLM configuration
    # PowerShell: $env:BOT_CONFIG="llm"; pytest -q tests/test_manual_cases.py

Two kinds of statement over the same cases, and the difference between them is
the lesson: **refusing is exact** -- a guarantee, asserted case by case -- and
**recognising is a rate**, which over five cases cannot decide anything (even 5
of 5 has a lower bound of 0.57). So the rate is *reported*, not asserted: the
summary at the end of the pytest output prints every case, what the component
wrote, and the interval.

You are done with this task when: `pytest -q -m gate tests/test_manual_cases.py`
is green, `pytest -q tests/test_manual_cases.py` is green in both configurations,
and you can name one case the static configuration fails and one the LLM
configuration fails -- the summary prints both.

Note the division of labour with `evaluate.py`: these cases are *yours*, few, and
chosen; the generated ones are many and drawn from the graph. Both are scored by
exactly the same `score()` function and the same wordings of the catalog, so the
two numbers can be put in one table.
"""

import pytest

from evaluate import METHODS, accepted_for, fold, score, wilson

#: At least this many cases per method, at least one of them a refusal.
MINIMUM = 5


# ---------------------------------------------------------------------------
# address_recognition -- expected: a complete record, or None
# ---------------------------------------------------------------------------

MANUAL_ADDRESS = [
    ("deliver it to 5 Ermou, Athens",
     {"street": "Ermou", "house_number": "5", "city": "Athens"}),
    # TODO: four more. Ideas that are worth a case, one each:
    #   * the other word order -- the Greek one ("Ermou 5, Athens")
    #   * a spelling a real customer uses ("Athina", "Ermou St.")
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
    #   * something we do not sell ("a Pizza Napoli") -> None
    #   * a sentence with no pizza in it at all -> None
]

# ---------------------------------------------------------------------------
# the two of them in one utterance -- expected: (pizza id, address record)
# ---------------------------------------------------------------------------

MANUAL_ORDER = [
    ("I would like one Diavola to 12b Vasilissis Sofias, Athens",
     (8, {"street": "Vasilissis Sofias", "house_number": "12b", "city": "Athens"})),
    # TODO: four more in MANUAL_ORDER. At least one where ONE of the two is
    # recognisable and the other is not -- e.g. ("a Funghi to Barcelona", (5, None))
    # -- and one where NEITHER is: ("is the kitchen open tonight?", (None, None)).
    # Only the second kind counts as the refusal of this method.
]


CASES = {
    "address_recognition": [(text, {"address": expected}) for text, expected in MANUAL_ADDRESS],
    "pizza_recognition": [(text, {"pizza_id": expected}) for text, expected in MANUAL_PIZZA],
    "pizza_and_address": [(text, {"pizza_id": pizza, "address": address})
                          for text, (pizza, address) in MANUAL_ORDER],
}
LIST_NAME = {"address_recognition": "MANUAL_ADDRESS", "pizza_recognition": "MANUAL_PIZZA",
             "pizza_and_address": "MANUAL_ORDER"}


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
        f"fill {LIST_NAME[method_name]} in this file")
    refusals = [case for case in cases if all(value is None for value in case[1].values())]
    assert refusals, (
        f"{method_name}: no case in {LIST_NAME[method_name]} expects 'nothing recognised' "
        f"in every field{' -- e.g. (None, None)' if method_name == 'pizza_and_address' else ''}. "
        f"A contract has a failure clause; a test set without one does not test it.")


@pytest.mark.parametrize("method_name", list(CASES))
def test_a_refusal_is_never_answered_with_a_value(implementations, method_name):
    """The exact half of the contract: what the component promises NOT to do.

    Recognising a value is approximate -- it is a rate, reported below. Refusing
    is not: "nothing recognised -> write nothing" is a guarantee, and a guarantee
    that holds 80 % of the time is not a guarantee. Every case of yours with a
    `None` is checked here, one assertion each, both configurations.
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
def test_the_rate_over_the_hand_written_cases_is_reported(implementations, catalog, configuration,
                                                          manual_report, method_name):
    """The same cases as a rate -- reported, not asserted.

    Five cases cannot decide anything: 5 of 5 has a lower bound of 0.57, far below
    any useful threshold. Asserting the rate would push you to edit honest cases
    until they pass -- the one thing a gold standard must never be. So this test
    records every case and the interval; pytest prints them in its summary.
    """
    cases = CASES[method_name]
    if not cases:
        pytest.skip(f"{method_name}: no case written yet")
    hits, lines = 0, []
    for utterance, expected in cases:
        slots = run(implementations, method_name, utterance)
        ok = all(score(slots.get(field), want, accepted_for(catalog, want))
                 for field, want in expected.items())
        hits += ok
        got = {field: slots.get(field) for field in expected}
        lines.append(f"  {'ok  ' if ok else 'MISS'} {utterance!r}\n         got {got}"
                     + ("" if ok else f"\n         expected {dict(expected)}"))
    low, high = wilson(hits, len(cases))
    manual_report.append(f"{method_name} [{configuration}]: {hits}/{len(cases)} = {hits / len(cases):.2f}, "
                         f"95% CI [{low:.2f}, {high:.2f}] -- reported, not asserted")
    manual_report.extend(lines)


def test_the_scorer_treats_a_copied_wording_as_the_same_answer(catalog):
    """Read this one: it is the whole leniency of this harness, and its limit."""
    accepted = {"city": ["Athens", "Athina", "athens"]}
    assert score({"city": "Athina"}, {"city": "Athens"}, accepted)
    assert not score({"city": "Piraeus"}, {"city": "Athens"}, accepted)
    assert fold("Agía Paraskeví") == fold("agia paraskevi")
    assert score(None, None, None)                       # a refusal, answered correctly
    assert not score({"city": "Piraeus"}, None, None)    # answered something where nothing was right
    # A hand-written record is looked up in the catalog: the same individual, any wording
    expected = {"street": "Vasilissis Sofias", "house_number": "12b", "city": "Athens"}
    copied = {"street": "Vas. Sofias", "house_number": "12 b", "city": "Αθήνα"}
    assert score(copied, expected, accepted_for(catalog, expected))
