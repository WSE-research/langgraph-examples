"""Task 2 -- a guest who describes instead of naming.

Run it::

    pytest -q tests/test_task2_description.py
    pytest -q -m gate tests/test_task2_description.py
    BOT_CONFIG=llm pytest -q tests/test_task2_description.py

Every expected answer is **computed by the same `kb.matching()` call your node
makes**, so the cases below say *“whatever the graph answers for this
description, the bot has to end up with that”* -- not *“the bot has to say
Hawaiian”*. A topping added to a pizza tomorrow changes both sides at once,
which is what a benchmark built on the domain graph buys you.

The four outcomes of Task 2c get one test each, and three of them are really
tests of Task 1: if `show_pizza_options` was built with its skip rule, they
pass without a line of new code.
"""

import pytest

from pizzabot import kb, pizza_api
from bot_helpers import names_in, say, skip_without, spoken

ALL = {pizza["name"] for pizza in kb.all_pizzas()}
LIVE_MENU = pizza_api.menu


@pytest.fixture(autouse=True)
def the_kitchen_has_everything(monkeypatch):
    """Pin the Pizza API's per-minute draw: every pizza available.

    Since version 1.3.0 two pizzas are sold out every minute, at random; without
    this, a case whose pizza happens to be drawn would change outcome from one
    minute to the next. Task 1 tests the draw; here it would only be noise.
    """
    monkeypatch.setattr(pizza_api, "menu", lambda refresh=False: [
        {**pizza, "available": True} for pizza in LIVE_MENU(refresh)])
    monkeypatch.delenv("SOLD_OUT", raising=False)


def matching(with_toppings=(), flags=(), without_toppings=()) -> list:
    return kb.matching(list(with_toppings), list(without_toppings), list(flags))


# ---------------------------------------------------------------------------
# the descriptions, and what the graph answers for each
# ---------------------------------------------------------------------------
#
#   (what the guest types, the constraints it means, how many pizzas match)
#
# The last column is not typed in -- it is asserted against `kb.matching()` at
# collection time, so a case that no longer means what it says fails loudly in
# this file instead of quietly in your node.

DESCRIPTION_CASES = [
    ("a pizza with pineapple",            dict(with_toppings=["Pineapple"])),
    ("something vegan",                   dict(flags=[("vegan", True)])),
    ("a vegetarian pizza with mushrooms", dict(with_toppings=["Mushroom"],
                                               flags=[("vegetarian", True)])),
    ("a pizza with mushrooms and ham",    dict(with_toppings=["Mushroom", "Ham"])),
    ("something with tuna",               dict(with_toppings=["Tuna"])),
    ("a vegetarian pizza with aubergine", dict(with_toppings=["Aubergine"],
                                               flags=[("vegetarian", True)])),
    ("a pizza with olives",               dict(with_toppings=["Olive"])),
]

EXPECTED = {utterance: {row["name"] for row in matching(**constraints)}
            for utterance, constraints in DESCRIPTION_CASES}

ONE = [u for u, e in EXPECTED.items() if len(e) == 1]
MANY = [u for u, e in EXPECTED.items() if len(e) > 1]


def test_the_cases_still_mean_what_they_say():
    """Read this first when something below fails for no reason you can see."""
    assert EXPECTED["a pizza with pineapple"] == {"Hawaiian"}
    assert EXPECTED["something vegan"] == {"Marinara", "Verdure"}
    assert len(EXPECTED["a vegetarian pizza with mushrooms"]) == 3
    assert ONE and MANY, "the data no longer offers both a unique and an ambiguous case"


# ---------------------------------------------------------------------------
# outcome 1 -- exactly one match, and it can be ordered
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("utterance", ONE)
def test_one_match_goes_straight_into_the_frame(bot, fresh, utterance):
    only = next(iter(EXPECTED[utterance]))
    from pizzabot import availability

    if not availability.is_available(only):
        pytest.skip(f"{only} cannot be ordered today -- covered by the third outcome")

    before = len(fresh["messages"])
    state = say(bot, fresh, utterance)
    skip_without(state, "needs")
    said = spoken(state, before)

    assert state["slots"].get("pizza_name") == only, (
        f"{utterance!r} describes exactly one pizza ({only}) and the frame is "
        f"{state['slots'].get('pizza_name')!r}")
    assert only.lower() in said, (
        f"say which pizza you decided on -- a guest who described something and "
        f"is asked for their address has no idea what they just ordered")
    skip_without(state, "needs")
    assert not state["needs"], "the need was served; remove it (Task 2b, rule 5)"


# ---------------------------------------------------------------------------
# outcome 3 -- several matches: a question, not an answer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("utterance", MANY)
def test_several_matches_become_a_choice(bot, fresh, utterance):
    expected = EXPECTED[utterance]
    before = len(fresh["messages"])
    state = say(bot, fresh, utterance)
    skip_without(state, "candidates")
    said = spoken(state, before)

    assert not state["slots"].get("pizza_name"), (
        f"{utterance!r} matches {len(expected)} pizzas and one of them was "
        f"chosen for the guest. Several candidates are a question.")

    named = names_in(said, ALL)
    missing = expected - named
    assert not missing, f"{utterance!r}: did not offer {sorted(missing)}"
    assert not (named - expected), (
        f"{utterance!r}: also offered {sorted(named - expected)}, which do not "
        f"match the description")

    skip_without(state, "candidates")
    assert {candidate["name"] for candidate in state["candidates"]} == expected, (
        f"candidates is {sorted(c.get('name') for c in state['candidates'])}, "
        f"expected {sorted(expected)} -- show_pizza_options reads this field")


@pytest.mark.parametrize("utterance", MANY[:2])
def test_the_guest_can_then_pick_one(bot, fresh, utterance):
    from pizzabot import availability

    state = say(bot, fresh, utterance)
    sellable = [name for name in sorted(EXPECTED[utterance])
                if availability.is_available(name)]
    if not sellable:
        pytest.skip("nothing that matched can be ordered today")
    state = say(bot, state, sellable[0])
    assert state["slots"].get("pizza_name") == sellable[0], (
        "the guest picked one of the names that were offered and it did not "
        "reach the frame -- expected = 'pizza_name' closes this loop")


# ---------------------------------------------------------------------------
# outcome 4 -- nothing matches: drop a constraint and say which
# ---------------------------------------------------------------------------

IMPOSSIBLE = [
    ("something vegan with olives", "olive", {"Marinara", "Verdure"}),
    ("a vegan pizza with ham",      "ham",   {"Marinara", "Verdure"}),
]


@pytest.mark.parametrize("utterance, dropped, fallback", IMPOSSIBLE,
                         ids=[case[0] for case in IMPOSSIBLE])
def test_no_match_names_the_constraint_it_dropped(bot, fresh, utterance, dropped, fallback):
    """Nothing is vegan and has olives -- and the guest deserves to know why.

    `matching()` returning nothing is not a failure; it is the sentence
    *“nothing has all of that”*. The repair is to drop the narrowest constraint
    and say which one you dropped, so that the guest can disagree with the
    choice you made for them.
    """
    assert not matching(with_toppings=["Olive"], flags=[("vegan", True)]), \
        "the data changed: something vegan now has olives"

    before = len(fresh["messages"])
    state = say(bot, fresh, utterance)
    skip_without(state, "candidates")
    said = spoken(state, before)

    assert said.strip(), "an empty result still gets an answer"
    assert dropped in said, (
        f"the bot did not say which constraint it gave up on. Name it: "
        f"'nothing is vegan and has {dropped}s -- without the {dropped}s I have ...'")
    assert names_in(said, fallback), (
        f"after dropping the {dropped}s, {sorted(fallback)} match. Offer them "
        f"rather than ending the conversation.")


# ---------------------------------------------------------------------------
# what must NOT have changed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("utterance", ["I would like a Margherita",
                                       "Margherita please",
                                       "one Marinara"])
def test_a_named_pizza_never_takes_the_description_path(bot, fresh, utterance):
    """`identify_pizza_by_parameters` must skip when the name was recognised."""
    state = say(bot, fresh, utterance)
    assert state["slots"].get("pizza_name"), f"{utterance!r} names a pizza"
    skip_without(state, "candidates")
    assert not state["candidates"], (
        "the name was recognised and the description node ran anyway -- "
        "check the skip rule (Task 2b, rule 1)")


def test_a_word_we_do_not_know_is_reported_and_not_ignored(bot, fresh):
    """"with kale" -- `topping_iri()` returns None, and silence would be a lie."""
    assert kb.topping_iri("kale") is None, "the data changed: kale is a topping now"
    before = len(fresh["messages"])
    state = say(bot, fresh, "a pizza with kale")
    skip_without(state, "needs")
    said = spoken(state, before)
    assert "kale" in said, (
        "the guest asked for kale, the graph does not know the word, and the "
        "bot did not mention it. Dropping an unknown constraint silently hands "
        "back a pizza that does not meet the request (Task 2b, rule 3).")


# ---------------------------------------------------------------------------
# the gate: did YOU do the task
# ---------------------------------------------------------------------------


@pytest.mark.gate
def test_the_graph_has_an_identify_node(bot):
    nodes = set(bot.get_graph().nodes)
    assert "identify_pizza_by_parameters" in nodes, (
        f"no `identify_pizza_by_parameters` node -- Task 2c. Found: {sorted(nodes)}")


@pytest.mark.gate
def test_description_understanding_is_a_substitutable_component(configuration):
    from pizzabot import config

    assert "description_understanding" in config.implementations(configuration), (
        "Task 2b: turning words into constraints is the uncertain step, so it "
        "is the one with two implementations")


@pytest.mark.gate
def test_the_three_new_nodes_sit_on_one_chain(bot):
    """The shape of Task 2c: no new router condition for any of this."""
    drawn = bot.get_graph()
    edges = {(edge.source, edge.target) for edge in drawn.edges}
    chain = [("pizza_recognition", "identify_pizza_by_parameters"),
             ("identify_pizza_by_parameters", "show_pizza_options"),
             ("show_pizza_options", "address_recognition")]
    missing = [edge for edge in chain if edge not in edges]
    assert not missing, (
        f"missing fixed edge(s): {missing}. The nodes decide for themselves "
        f"whether they apply, which is exactly why these are plain edges and "
        f"not conditions.")
