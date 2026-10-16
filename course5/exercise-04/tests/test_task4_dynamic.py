"""Task 4 -- data that changes: is the menu read, or remembered?

Run it::

    pytest -q tests/test_task4_dynamic.py
    pytest -q -m gate tests/test_task4_dynamic.py

Three things, and only the first is about SPARQL:

* the menu is **read from the graph on every turn** -- the test proves it by
  making the graph answer differently and asking again,
* a follow-up is answered **over the previous answer** and not over the menu,
  which is two pizzas and not three,
* the graph and `GET /pizza` still agree in the direction that matters.
"""

import pytest

from pizzabot import kb
from bot_helpers import names_in, say, skip_without, spoken

ALL = {pizza["name"] for pizza in kb.all_pizzas()}


def flagged(prop: str, value: bool = True) -> set:
    return {pizza["name"] for pizza in kb.pizzas_with_flag(prop, value)}


def flagged_local(prop: str, value: bool = True) -> set:
    return {pizza["local"] for pizza in kb.pizzas_with_flag(prop, value)}


# =========================================================================
# the menu is read, not remembered
# =========================================================================


def test_the_menu_answer_names_every_pizza_the_graph_knows(bot, fresh):
    state = say(bot, fresh, "What pizzas do you have?")
    skip_without(state, "topic")
    said = spoken(state, 0)
    missing = ALL - names_in(said, ALL)
    assert not missing, (
        f"the menu answer did not name {sorted(missing)}. It has "
        f"{len(ALL)} entries today and it had {len(ALL) - 2} on Wednesday.")


def test_the_menu_is_read_again_when_the_graph_changes(bot, fresh, monkeypatch):
    """The test that a hard-coded list cannot pass.

    We make `kb.all_pizzas()` answer differently and ask the same question
    again. A node that read the graph gives a different answer; a node that
    built a list at import time gives the same one.
    """
    before = say(bot, fresh, "What pizzas do you have?")
    skip_without(before, "topic")
    real = kb.all_pizzas()
    assert len(real) > 3

    monkeypatch.setattr(kb, "all_pizzas", lambda: real[:3])
    after = say(bot, fresh, "What pizzas do you have?")
    assert len(set(after["topic"])) == 3, (
        f"the graph now holds three pizzas and the answer was still about "
        f"{len(set(after['topic']))}. Somewhere there is a list that was built "
        f"once -- read the graph on every call (Task 4a, rule 2).")


def test_nothing_in_the_answer_survives_an_empty_graph(bot, fresh, monkeypatch):
    """A kitchen with nothing on the menu is a sentence, not a crash."""
    monkeypatch.setattr(kb, "all_pizzas", list)
    state = say(bot, fresh, "What pizzas do you have?")
    skip_without(state, "topic")
    assert spoken(state, 0).strip(), "say something -- an empty menu is an answer"
    assert not set(state["topic"])


# =========================================================================
# the follow-up -- coreference resolved in the state
# =========================================================================
#
#   (first sentence, second sentence, what the second answer must be about,
#    what it must NOT be about -- i.e. what answering over the whole menu
#    would have dragged in)

FOLLOW_UP_CASES = [
    ("Which pizzas are vegetarian?", "and which of those are without milk?",
     flagged_local("vegetarian") & flagged_local("containsMilk", False),
     flagged_local("containsMilk", False) - flagged_local("vegetarian")),
    ("Which pizzas are vegan?", "and which of those are without milk?",
     flagged_local("vegan") & flagged_local("containsMilk", False),
     flagged_local("containsMilk", False) - flagged_local("vegan")),
    ("Which pizzas are without milk?", "which of them are vegetarian?",
     flagged_local("containsMilk", False) & flagged_local("vegetarian"),
     flagged_local("vegetarian") - flagged_local("containsMilk", False)),
]


@pytest.mark.parametrize("first, second, must, must_not", FOLLOW_UP_CASES,
                         ids=[f"{c[0]} -> {c[1]}" for c in FOLLOW_UP_CASES])
def test_a_follow_up_is_answered_over_the_previous_answer(bot, fresh, first, second,
                                                          must, must_not):
    state = say(bot, fresh, first)
    skip_without(state, "topic")
    assert state["topic"], f"{first!r} left `topic` empty -- Task 3f, rule 5"

    before = len(state["messages"])
    state = say(bot, state, second)
    said = spoken(state, before)

    names = {pizza["name"] for pizza in kb.all_pizzas()
             if pizza["local"] in must}
    missing = names - names_in(said, names)
    assert not missing, f"the follow-up did not name {sorted(missing)}"

    leaked = must_not & set(state["topic"])
    assert not leaked, (
        f"the follow-up ended up about {sorted(leaked)}, which the previous "
        f"answer did not contain. The word 'those' means the previous answer -- "
        f"pass state['topic'] as the `only` argument (Task 4c, step 2).")


def test_topic_shrinks_and_never_grows(bot, fresh):
    """`topic` is the antecedent, so a follow-up can only narrow it. 22 -> 10 -> 2."""
    state = say(bot, fresh, "What pizzas do you have?")
    skip_without(state, "topic")
    sizes = [len(set(state["topic"]))]
    for utterance in ("which of those are vegetarian?",
                      "and which of those are without milk?"):
        state = say(bot, state, utterance)
        sizes.append(len(set(state["topic"])))
    assert sizes == sorted(sizes, reverse=True), (
        f"`topic` went {sizes}. Each follow-up narrows the one before it; a "
        f"step that grows means that question was answered over the whole menu.")
    assert sizes[-1] == len(flagged_local("vegetarian")
                            & flagged_local("containsMilk", False))


def test_a_follow_up_with_no_antecedent_is_not_answered_over_the_menu(bot, fresh):
    """"which of those are without milk?" as the FIRST sentence of a dialog."""
    state = say(bot, fresh, "and which of those are without milk?")
    skip_without(state, "topic")
    said = spoken(state, 0)
    assert said.strip(), "say something -- silence is not a refusal"
    assert set(state["topic"]) != flagged_local("containsMilk", False), (
        "there was no previous answer for 'those' to refer to, and the bot "
        "answered over the whole menu anyway. Two conditions, not one: the "
        "wording AND a non-empty topic (Task 4c, step 1).")


# =========================================================================
# the drift check -- a test, not a hope
# =========================================================================


def test_the_service_sells_nothing_the_graph_has_never_heard_of():
    """The direction that is a bug.

    A pizza on `GET /pizza` that the graph does not know is a pizza your bot
    will answer about wrongly, or not at all. The other direction -- the graph
    knows a pizza the kitchen cannot bake today -- is not a bug; it is a fact
    about today, and Iteration 5 turns it into a dialog.
    """
    from pizzabot import pizza_api

    try:
        service = set(pizza_api.menu_names())
    except Exception as error:                  # no network, no verdict
        pytest.skip(f"GET /pizza did not answer ({error!r})")
    graph = {pizza["name"] for pizza in kb.all_pizzas()}

    unknown = service - graph
    assert not unknown, (
        f"the service sells {sorted(unknown)}, which the graph has never heard "
        f"of. Every question about those is answered wrongly or not at all -- "
        f"the graph is behind and somebody has to extend it.")

    only_graph = graph - service
    if only_graph:
        pytest.skip(f"the graph knows {sorted(only_graph)}, which are not on "
                    f"sale today -- that is Iteration 5's repair, not a bug")


# =========================================================================
# the gate: did YOU do the task
# =========================================================================


@pytest.mark.gate
def test_the_bot_can_show_the_menu(bot, fresh):
    """A gate never skips: it is the answer to "did we finish the task?"."""
    state = say(bot, fresh, "What pizzas do you have?")
    assert "topic" in state, "the state has no `topic` yet -- Task 3a"
    assert len(set(state["topic"])) == len(ALL), (
        f"the menu question was about {len(set(state['topic']))} pizzas and "
        f"the graph holds {len(ALL)} -- Task 4a")


@pytest.mark.gate
def test_a_follow_up_is_understood_as_one(bot, fresh):
    state = say(bot, fresh, "Which pizzas are vegetarian?")
    assert "question" in state, "the state has no `question` yet -- Task 3a"
    state = say(bot, state, "and which of those are without milk?")
    assert state["question"] and state["question"].get("follow_up"), (
        "the second sentence was not recognised as a follow-up -- Task 4c, "
        "step 1. It needs the wording AND a non-empty topic.")
