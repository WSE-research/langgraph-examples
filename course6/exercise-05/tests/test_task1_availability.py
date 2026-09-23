"""Task 1 -- does a dead end become a repair?

Run it::

    pytest -q tests/test_task1_availability.py
    pytest -q -m gate tests/test_task1_availability.py

**These tests do not depend on the minute they run in.** Since version 1.3.0
the Pizza API marks two pizzas `"available": false` every minute, at random. So
every test here first pins that draw (`the_kitchen_has_everything`: the live
menu, every pizza available) and then makes exactly the pizza it needs sold out
-- with `SOLD_OUT`, or with the service's own flag. One test does the opposite
and checks the live draw itself. The pizzas that are in the graph and not on the
menu at all are tested too, when there are any -- and skipped with a reason when
there are none. A test that only passes in some minutes is not a test.
"""

import pytest

from pizzabot import kb, pizza_api
from bot_helpers import names_in, say, skip_without, spoken

ALL = {pizza["name"] for pizza in kb.all_pizzas()}

# The real GET /pizza, kept before any fixture replaces it -- for the one test
# that has to see the live draw.
LIVE_MENU = pizza_api.menu


def menu_with(sold_out=()):
    """A `pizza_api.menu` replacement: the live menu, and only `sold_out` is off."""
    def menu(refresh: bool = False) -> list:
        return [{**pizza, "available": pizza["name"] not in sold_out}
                for pizza in LIVE_MENU(refresh)]
    return menu


@pytest.fixture(autouse=True)
def the_kitchen_has_everything(monkeypatch):
    """Pin the service's draw: every pizza available, unless a test says otherwise.

    Without this, "I would like a Margherita" would fail in every minute in
    which the service happens to draw the Margherita -- about one in eleven.
    """
    monkeypatch.setattr(pizza_api, "menu", menu_with())
    monkeypatch.delenv("SOLD_OUT", raising=False)


def on_menu() -> set:
    return set(pizza_api.menu_names())


def only_in_the_graph() -> set:
    """What the knowledge base knows and the service does not sell right now.

    Called while pytest is *collecting*, so a service that does not answer must
    not take the whole file down with it: no answer -> no cases, and the one
    test that needs them skips with a reason.
    """
    try:
        return ALL - on_menu()
    except Exception:                       # the API is down, or there is no network
        return set()


# ---------------------------------------------------------------------------
# the module itself
# ---------------------------------------------------------------------------


def test_available_is_a_question_asked_of_the_service_every_time(monkeypatch):
    """Not a list in your code, and not a copy made at import time."""
    from pizzabot import availability

    sellable = {pizza["name"] for pizza in availability.available_pizzas()}
    assert sellable <= ALL, (
        f"available_pizzas() offered {sorted(sellable - ALL)}, which the graph "
        f"does not know -- it must filter the graph, not replace it")

    victim = sorted(sellable)[0]
    monkeypatch.setenv("SOLD_OUT", victim)
    assert not availability.is_available(victim), (
        f"{victim} was marked sold out and is_available() still says yes -- "
        f"the answer was computed once and cached, or SOLD_OUT is not read")
    after = {pizza["name"] for pizza in availability.available_pizzas()}
    assert victim not in after
    assert after == sellable - {victim}, "exactly one pizza should have gone"


def test_the_service_flag_is_read(monkeypatch):
    """`"available": false` from GET /pizza is enough -- no SOLD_OUT needed."""
    from pizzabot import availability

    monkeypatch.setattr(pizza_api, "menu", menu_with({"Funghi"}))
    assert not availability.is_available("Funghi"), (
        "GET /pizza marks the Funghi \"available\": false and is_available() "
        "still says yes -- the `available` field of the menu is not read")
    assert "Funghi" not in {pizza["name"] for pizza in availability.available_pizzas()}
    assert availability.is_available("Margherita"), "only the Funghi is sold out"


def test_the_flag_is_asked_now_and_not_remembered(monkeypatch):
    """The menu cache of Iteration 1 is right for names and wrong for availability."""
    from pizzabot import availability

    assert availability.is_available("Funghi")
    monkeypatch.setattr(pizza_api, "menu", menu_with({"Funghi"}))
    assert not availability.is_available("Funghi"), (
        "the Funghi was sold out a moment later and is_available() did not "
        "notice -- the answer came from a copy, not from GET /pizza")


def test_the_live_draw_is_honoured(monkeypatch):
    """Against the real service: the two pizzas sold out right now are not available.

    Read twice around the check, so that a minute boundary in between does not
    count as a failure.
    """
    from pizzabot import availability

    monkeypatch.setattr(pizza_api, "menu", LIVE_MENU)
    for _ in range(3):
        try:
            before = {p["name"] for p in LIVE_MENU(True) if p.get("available") is False}
        except Exception as error:                  # no network, API down
            pytest.skip(f"the Pizza API does not answer: {error}")
        if not before:
            pytest.skip("GET /pizza has no sold-out pizza -- a service older than 1.3.0")
        answers = {name: availability.is_available(name) for name in before}
        after = {p["name"] for p in LIVE_MENU(True) if p.get("available") is False}
        if before == after:
            break
    assert not any(answers.values()), (
        f"the service marks {sorted(before)} sold out right now and "
        f"is_available() said yes to {sorted(n for n, a in answers.items() if a)}")


def test_the_knowledge_base_does_not_know_about_the_service():
    """`kb.py` asks the graph. Nothing else. If this fails, the seam moved."""
    import inspect

    source = inspect.getsource(kb)
    assert "pizza_api" not in source, (
        "pizzabot/kb.py imports pizza_api. The graph and the order service are "
        "two systems; the module that joins them is availability.py, and it is "
        "the only one allowed to know both.")


# ---------------------------------------------------------------------------
# recognised, and not available -- the repair
# ---------------------------------------------------------------------------
#
# Parameterized over pizzas we force sold out, so the case exists on any day.
# Four of them, chosen to cover a one-word name, a two-word name and a name
# whose local name is not its name with the spaces removed.

SOLD_OUT_CASES = ["Funghi", "Quattro Formaggi", "Salami", "Frutti di Mare"]


@pytest.mark.parametrize("unavailable", SOLD_OUT_CASES)
def test_an_unavailable_pizza_is_recognised_named_and_repaired(bot, fresh, monkeypatch,
                                                               unavailable):
    monkeypatch.setenv("SOLD_OUT", unavailable)
    before = len(fresh["messages"])
    state = say(bot, fresh, f"I would like a {unavailable}")
    skip_without(state, "needs")          # before Task 1a there is nothing to check
    said = spoken(state, before)

    assert unavailable.lower() in said, (
        f"the guest named the {unavailable} and the bot never said the word. "
        f"Naming it back is what tells them they were understood.")

    assert not state["slots"].get("pizza_name"), (
        f"{unavailable} is not available and it went into the frame anyway. "
        f"An unorderable pizza in slots reaches order_placement and fails "
        f"there -- as far from the cause as this process can manage.")

    alternatives = names_in(said, ALL - {unavailable})
    assert alternatives, (
        f"the bot said the {unavailable} is unavailable and stopped. That is "
        f"the dead end Task 1 exists to remove: show_pizza_options has to run "
        f"and name something the guest can actually order.")
    assert unavailable not in alternatives


def test_a_pizza_the_service_marks_sold_out_is_repaired(bot, fresh, monkeypatch):
    """The same repair, triggered by the service's flag instead of SOLD_OUT."""
    monkeypatch.setattr(pizza_api, "menu", menu_with({"Funghi"}))
    before = len(fresh["messages"])
    state = say(bot, fresh, "I would like a Funghi")
    skip_without(state, "needs")
    said = spoken(state, before)
    assert "funghi" in said, "the bot never named the Funghi back"
    assert not state["slots"].get("pizza_name"), (
        "GET /pizza marks the Funghi sold out and it went into the frame anyway")
    assert names_in(said, ALL - {"Funghi"}), "no alternatives offered"


@pytest.mark.parametrize("unavailable", SOLD_OUT_CASES[:2])
def test_the_alternatives_offered_can_actually_be_ordered(bot, fresh, monkeypatch,
                                                          unavailable):
    from pizzabot import availability

    monkeypatch.setenv("SOLD_OUT", unavailable)
    before = len(fresh["messages"])
    state = say(bot, fresh, f"I would like a {unavailable}")
    said = spoken(state, before)

    sellable = {pizza["name"] for pizza in availability.available_pizzas()}
    offered = names_in(said, ALL)
    assert offered - {unavailable} <= sellable, (
        f"offered {sorted(offered - sellable - {unavailable})}, which cannot be "
        f"ordered either. Offering a second dead end is worse than the first.")


@pytest.mark.parametrize("unavailable", SOLD_OUT_CASES[:2])
def test_the_next_turn_closes_the_loop(bot, fresh, monkeypatch, unavailable):
    """The repair is only a repair if the order can carry on afterwards."""
    from pizzabot import availability

    monkeypatch.setenv("SOLD_OUT", unavailable)
    state = say(bot, fresh, f"I would like a {unavailable}")
    skip_without(state, "needs")
    assert not state["needs"], (
        f"needs is still {state['needs']} after show_pizza_options ran. A need "
        f"that is served and left in the state is served again next turn, "
        f"forever -- remove it (Task 1d, rule 5).")
    assert state.get("expected") == "pizza_name", (
        "set expected = 'pizza_name' so that the next turn routes back into "
        "pizza_recognition (Task 1d, rule 4)")

    choice = sorted({pizza["name"] for pizza in availability.available_pizzas()})[0]
    state = say(bot, state, choice)
    assert state["slots"].get("pizza_name"), (
        f"the guest answered with {choice!r}, which is available, and the slot "
        f"is still empty -- the loop did not close")


@pytest.mark.parametrize("unavailable", sorted(only_in_the_graph()) or ["<none>"])
def test_a_pizza_the_graph_knows_and_the_service_does_not_sell(bot, fresh, unavailable):
    """A pizza GET /pizza does not list at all -- when there is one today."""
    if unavailable == "<none>":
        pytest.skip("GET /pizza lists every pizza the graph knows; SOLD_OUT and the "
                    "service's flag cover the path, and this case comes back when "
                    "the two drift apart")
    before = len(fresh["messages"])
    state = say(bot, fresh, f"I would like an {unavailable}")
    said = spoken(state, before)
    assert unavailable.lower() in said, (
        f"the {unavailable} is in the graph, so it must be RECOGNISED even "
        f"though it is not on the menu. If the bot did not say the word, your "
        f"recogniser is still matching against pizza_api.menu_names() -- "
        f"Task 1c, the first change.")
    assert not state["slots"].get("pizza_name")
    assert names_in(said, ALL - {unavailable}), "no alternatives offered"


# ---------------------------------------------------------------------------
# what must NOT have changed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("available", ["Margherita", "Hawaiian", "Marinara"])
def test_an_available_pizza_still_goes_straight_into_the_frame(bot, fresh, available):
    """The path that worked in Iteration 1 has to be untouched by all of this."""
    if available not in on_menu():
        pytest.skip(f"{available} is not on the menu today")
    state = say(bot, fresh, f"I would like a {available}")
    assert state["slots"].get("pizza_name") == available, (
        f"{available} is available and did not reach the frame. The new rules "
        f"are for the unavailable case only.")
    skip_without(state, "needs")
    assert not state["needs"], "an ordinary order raised an information need"


def test_the_two_new_nodes_cost_nothing_on_an_ordinary_turn(bot, fresh):
    """They run, they skip, and the frame is filled exactly as before."""
    state = say(bot, fresh, "I would like a Margherita")
    skip_without(state, "candidates")
    assert not state["candidates"], (
        "an ordinary order left candidates behind; the nodes did not skip")


# ---------------------------------------------------------------------------
# the gate: did YOU do the task
# ---------------------------------------------------------------------------


@pytest.mark.gate
def test_the_graph_has_a_show_pizza_options_node(bot):
    nodes = set(bot.get_graph().nodes)
    assert "show_pizza_options" in nodes, (
        f"no `show_pizza_options` node -- Task 1e. Found: {sorted(nodes)}")


@pytest.mark.gate
def test_availability_is_its_own_module():
    from pizzabot import availability

    for name in ("is_available", "available_pizzas"):
        assert hasattr(availability, name), (
            f"pizzabot/availability.py has no {name}() -- Task 1b")


@pytest.mark.gate
def test_show_pizza_options_skips_when_there_is_nothing_to_show(bot, fresh):
    """The skip rule, asserted directly. Write this one first.

    A turn with no information need must leave the state exactly as the
    Iteration 1 process left it. If this is red, the node is doing work it was
    not asked to do, and the fixed edge of Task 1e is not safe.
    """
    state = say(bot, fresh, "Hello")
    assert "needs" in state and "candidates" in state, (
        "the state has no `needs`/`candidates` yet -- Task 1a")
    assert not state["needs"] and not state["candidates"], (
        "a greeting produced information needs or candidates")
