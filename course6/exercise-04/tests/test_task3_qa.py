"""Task 3 -- the QA sub-graph: does each of the four nodes do its own job?

Run it::

    pytest -q tests/test_task3_qa.py
    pytest -q -m gate tests/test_task3_qa.py       # did YOU do the task
    BOT_CONFIG=llm pytest -q tests/test_task3_qa.py

Every expected value is **computed from the knowledge base**, never typed in:
`kb.pizzas_with_flag("vegan", True)` is the same call your `query_construction`
makes, so a menu that grows does not make these tests wrong -- it makes them
test more. That is the Iteration 3 move (a benchmark drawn from the domain
graph) applied to a second process.

The groups follow your four nodes, on purpose. A failure in `linking` means
`entity_linking`; a failure in `template` means `query_construction`; a failure
in `rows` means the query asked the wrong thing; a failure in `sentence` means
the facts were right and the wording was not. "The bot was wrong" is not a
sentence anybody can act on -- these four are.

What is NOT checked: your wording. The names that belong in an answer have to
appear in it; the sentence around them is yours.
"""

import pytest

from pizzabot import kb
from bot_helpers import names_in, say, skip_without, spoken

ALL = {pizza["name"] for pizza in kb.all_pizzas()}
ALL_LOCAL = {pizza["local"] for pizza in kb.all_pizzas()}


def flagged(prop: str, value: bool = True) -> set:
    return {pizza["name"] for pizza in kb.pizzas_with_flag(prop, value)}


def flagged_local(prop: str, value: bool = True) -> set:
    return {pizza["local"] for pizza in kb.pizzas_with_flag(prop, value)}


def linked_iris(state: dict) -> set:
    return {item.get("iri") for item in (state.get("linked") or []) if item.get("iri")}


# =========================================================================
# entity_linking -- from a word to a thing
# =========================================================================

LINKING_CASES = [
    ("What toppings does the Hawaiian have?", {"Hawaiian"}),
    ("What toppings does the hawaii have?",   {"Hawaiian"}),      # an alias
    ("Tell me about the Frutti di Mare.",     {"FruttiDiMare"}),  # two words
    ("Tell me about the Salami.",             {"SalamiPizza"}),   # local != name
    ("Who invented the Margherita?",          {"Margherita"}),
]


@pytest.mark.parametrize("utterance, expected", LINKING_CASES,
                         ids=[case[0] for case in LINKING_CASES])
def test_a_mention_becomes_a_thing(bot, fresh, utterance, expected):
    state = say(bot, fresh, utterance)
    skip_without(state, "linked")
    assert expected <= linked_iris(state), (
        f"{utterance!r}: linked {sorted(linked_iris(state))}, expected to contain "
        f"{sorted(expected)}. Two of these are the ones that catch a shortcut: "
        f"'Salami' is pz:SalamiPizza and 'Frutti di Mare' is pz:FruttiDiMare, so "
        f"a local name rebuilt with .replace(' ', '') is wrong for both.")


def test_an_ambiguous_word_keeps_both_readings(bot, fresh):
    """"pepperoni" is a pizza AND a topping, and the graph says so.

    This node does not get to pick one to keep things simple: which one the
    guest meant depends on the question, and that is the next node's problem.
    Throwing one away here throws away the only evidence it could have used.
    """
    assert kb.pizza_iri("pepperoni") and kb.topping_iri("pepperoni"), \
        "the data changed: 'pepperoni' is no longer both"
    state = say(bot, fresh, "Tell me about the pepperoni.")
    skip_without(state, "linked")
    kinds = {item.get("kind") for item in state["linked"]}
    assert {"pizza", "topping"} <= kinds, (
        f"linked kinds are {sorted(k for k in kinds if k)}; 'pepperoni' resolves "
        f"to a pizza and to a topping and both records belong in `linked`")


@pytest.mark.parametrize("word, utterance", [
    ("napoli", "What toppings does the Napoli have?"),
    ("kale",   "Which pizzas have kale?"),
])
def test_a_word_that_is_no_thing_keeps_its_word(bot, fresh, word, utterance):
    """Dropped silently, it becomes an answer to a question nobody asked."""
    state = say(bot, fresh, utterance)
    skip_without(state, "linked")
    said = spoken(state, 0)
    words = {str(item.get("word", "")).lower() for item in state["linked"]}
    assert word in words or word in said, (
        f"{word!r} resolves to nothing, and neither `linked` nor the answer "
        f"mentions it. Keep the mention with iri=None and report it.")


# =========================================================================
# query_construction -- the type picks the template
# =========================================================================

TEMPLATE_CASES = [
    ("What pizzas do you have?",              "menu"),
    ("Which pizzas are vegan?",               "flag"),
    ("What toppings does the Hawaiian have?", "toppings"),
    ("Who invented the Hawaiian?",            "inventor"),
    ("Tell me about the Hawaiian.",           "about"),
]


@pytest.mark.parametrize("utterance, template", TEMPLATE_CASES,
                         ids=[case[1] for case in TEMPLATE_CASES])
def test_the_question_type_picks_the_template(bot, fresh, utterance, template):
    state = say(bot, fresh, utterance)
    skip_without(state, "question")
    assert state["question"], f"{utterance!r} was not recognised as a question"
    assert state["question"].get("type") == template, (
        f"{utterance!r}: type is {state['question'].get('type')!r}, expected "
        f"{template!r}")


def test_the_query_is_in_the_state_and_can_be_read(bot, fresh):
    """One line in the node, and it buys the whole bounded-generation argument.

    A query in the state is one a student, a reviewer or a grader can copy out
    of the Order pad tab and run against the graph by hand.
    """
    state = say(bot, fresh, "Which pizzas are vegan?")
    skip_without(state, "query")
    assert state["query"], "query_construction wrote no query"
    assert "?" in str(state["query"]) or "SELECT" in str(state["query"]).upper(), (
        f"`query` is {state['query']!r}, which does not look like something "
        f"anybody could paste into a SPARQL endpoint")


def test_no_template_is_a_legitimate_outcome(bot, fresh):
    """"Which pizza is the spiciest?" -- the graph has no such property."""
    state = say(bot, fresh, "Which pizza is the spiciest?")
    skip_without(state, "topic")
    assert spoken(state, 0).strip(), "say something -- silence is not a refusal"
    assert not state["topic"], (
        f"no template covers that question, but the answer was about "
        f"{sorted(state['topic'])}. Guessing is worse than refusing, and "
        f"Task 5 measures exactly this as `honest_refusal`.")


# =========================================================================
# query_execution + answer_generation -- the rows, and the sentence
# =========================================================================

SET_CASES = [
    ("What pizzas do you have?",       ALL,                            ALL_LOCAL),
    ("Which pizzas are vegan?",        flagged("vegan"),               flagged_local("vegan")),
    ("Which pizzas are vegetarian?",   flagged("vegetarian"),          flagged_local("vegetarian")),
    ("Which pizzas are without milk?", flagged("containsMilk", False),
     flagged_local("containsMilk", False)),
    ("Which pizzas are free of meat?", flagged("containsMeat", False),
     flagged_local("containsMeat", False)),
]


@pytest.mark.parametrize("utterance, must_name, must_be_topic", SET_CASES,
                         ids=[case[0] for case in SET_CASES])
def test_a_set_question_is_about_exactly_the_right_pizzas(bot, fresh, utterance,
                                                          must_name, must_be_topic):
    state = say(bot, fresh, utterance)
    skip_without(state, "topic")
    said = spoken(state, 0)
    assert said.strip(), f"{utterance!r}: the bot said nothing at all"

    missing = must_name - names_in(said, must_name)
    assert not missing, f"{utterance!r}: did not name {sorted(missing)}"

    assert set(state["topic"]) == must_be_topic, (
        f"{utterance!r}: topic is {sorted(state['topic'])}, expected "
        f"{sorted(must_be_topic)}. 'vegetarian' and 'free of meat' are two "
        f"different questions and the Siciliana (anchovies) is the difference.")


TOPPING_CASES = [(pizza["name"], set(kb.toppings_of(pizza["local"])))
                 for pizza in kb.all_pizzas()[:6]]


@pytest.mark.parametrize("pizza, toppings", TOPPING_CASES,
                         ids=[case[0] for case in TOPPING_CASES])
def test_the_toppings_question_names_every_topping(bot, fresh, pizza, toppings):
    state = say(bot, fresh, f"What toppings does the {pizza} have?")
    skip_without(state, "topic")
    said = spoken(state, 0)
    missing = {topping for topping in toppings if topping.lower() not in said}
    assert not missing, f"{pizza}: did not name {sorted(missing)}"


def test_an_inventor_we_know_is_named_with_its_source(bot, fresh):
    state = say(bot, fresh, "Who invented the Hawaiian?")
    skip_without(state, "topic")
    said = spoken(state, 0)
    assert "panopoulos" in said, "the graph knows Sam Panopoulos -- say so"
    assert "1962" in said, "the graph knows the year too"
    assert "q590076" in said or "wikidata" in said, (
        "an answer built from retrieved data can say where it came from; "
        "prov:wasDerivedFrom is in the row your node already has")


def test_an_inventor_we_do_not_know_is_refused_and_not_invented(bot, fresh):
    """The most important test in this file.

    Two of twenty-two pizzas have an inventor. A bot that offers a plausible
    name for the other twenty is confidently wrong about a checkable fact --
    and Task 5 scores that twenty times.
    """
    state = say(bot, fresh, "Who invented the Rucola?")
    skip_without(state, "topic")
    said = spoken(state, 0)
    assert said.strip(), "an empty result is still an answer -- say it"
    for invented in ("panopoulos", "esposito"):
        assert invented not in said, (
            f"the Rucola has no inventor in the graph, and the answer named "
            f"{invented!r} -- that name belongs to another pizza")


@pytest.mark.parametrize("unknown", ["Napoli", "Calabrese", "Pizza Bianca"])
def test_a_pizza_we_do_not_have_is_said_so(bot, fresh, unknown):
    state = say(bot, fresh, f"What toppings does the {unknown} have?")
    skip_without(state, "topic")
    assert spoken(state, 0).strip(), "an unknown name deserves an answer"
    assert not state["topic"], (
        f"we do not have a {unknown}, but the answer was about "
        f"{sorted(state['topic'])} -- the node answered about a different pizza")


def test_a_question_never_fills_an_order_slot(bot, fresh):
    """The router rule of Task 3b, checked where it matters.

    "Which pizzas are vegan?" contains the word *pizza*, so the Iteration 1
    ordering rule would happily claim it -- and the guest would be asked for
    their address instead of getting an answer.
    """
    state = say(bot, fresh, "Which pizzas are vegan?")
    assert not state["slots"].get("pizza_name"), (
        "a question filled a slot: the question rule has to be checked BEFORE "
        "the ordering rules in route()")


# =========================================================================
# the gate: did YOU do the task
# =========================================================================


@pytest.mark.gate
def test_the_state_grew_by_the_six_fields(fresh):
    for field in ("question", "linked", "query", "rows", "topic", "spoke"):
        assert field in fresh, (
            f"`{field}` is not in the state -- Task 3a. Add it to ChatbotState "
            f"AND to new_state(), or a node will read a key that is not there.")


@pytest.mark.gate
def test_question_understanding_is_a_substitutable_component(configuration):
    from pizzabot import config

    assert "question_understanding" in config.implementations(configuration), (
        "Task 3b: the understanding is the uncertain step, so it is the step "
        "that gets two implementations. Add it to both dictionaries in "
        "pizzabot/config.py.")


@pytest.mark.gate
def test_the_qa_process_is_reachable_from_the_dialog_graph(bot):
    nodes = set(bot.get_graph().nodes)
    assert "question_answering" in nodes, (
        f"no `question_answering` step in the compiled dialog graph -- Task 3g. "
        f"Found: {sorted(nodes)}")


@pytest.mark.gate
def test_the_qa_process_has_its_four_nodes(configuration):
    """Compiled on its own, and it is a process with four steps.

    If `build_qa_graph` does not exist, you wrote the four nodes straight into
    the dialog graph. That is a defensible choice -- but then say so in your
    report and explain what you gave up, because the sub-graph is what makes
    the QA process compilable, drawable and testable on its own.
    """
    from pizzabot import config

    try:
        from pizzabot.graph import build_qa_graph
    except ImportError:
        pytest.fail("no `build_qa_graph` -- Task 3g")
    qa = build_qa_graph(config.implementations(configuration))
    nodes = set(qa.get_graph().nodes)
    expected = {"entity_linking", "query_construction",
                "query_execution", "answer_generation"}
    assert expected <= nodes, (
        f"the QA process has {sorted(nodes - {'__start__', '__end__'})}, "
        f"missing {sorted(expected - nodes)}")
