"""Task 3 -- the gate on YOUR extension of the domain data. Red until you have done it.

    pytest -q -m gate tests/test_extension.py

These tests do not check that the software works; `pytest -q` does that. They
check that the **knowledge graph has grown**, by the amount the exercise asks
for, and that it grew the way a knowledge graph is supposed to grow: the things
the service owns are taken from the service, the things nobody else knows are
written by you, and a city that is already in the graph is linked to, not
written down a second time.

What is required, counted against the data as it was handed to you:

| what | was | must be | where it comes from |
| --- | --- | --- | --- |
| cities | 8 | at least 18 -- **ten more, picked from `GET /city`** | `python -m benchmark.fetch cities "Grenoble" ...` |
| pizzas | 10 | at least 13 -- **three more, picked from `GET /pizza`** | `python -m benchmark.fetch pizzas "Capricciosa" ...` |
| streets | 8 | at least 18 -- ten more, **written by you** | Turtle, by hand: the service has no streets |
| house numbers | 8 | at least 18 -- one per street, **written by you** | the same |
| descriptive pizza wordings | 8 | at least 11 -- three more, **written by you** | one `rdfs:label` each |

The split is the lesson. The service owns what can be ordered and where we
deliver: a pizza id and a delivery city are *facts about the system under test*,
and typing them by hand is how a benchmark ends up measuring a world that does
not exist. Streets, house numbers and the wordings a customer types are not in
any endpoint -- they are yours, and they are what makes the benchmark yours.

The rest of the point is in `test_a_city_is_defined_exactly_once`
(`tests/test_dataset.py`) and `test_cities_are_reused_by_several_addresses`
below: your second address in Lyon writes `:hasCity :lyon`. That is the
difference between a knowledge graph and a list of strings, and it is why four
teams can extend one benchmark without turning it into a mess.
"""

import unicodedata

import pytest

from benchmark.catalog import TG
from benchmark.generate import capacity

pytestmark = pytest.mark.gate

#: The data as it was handed out, on 2026-09-18. Every number below is "this
#: many were there before you started" -- the tests ask for growth, not for a
#: particular content, because what you add is your team's decision.
BASELINE = {"PIZZA": 10, "CITY": 8, "STREET": 8, "ADDRESS": 8, "descriptive": 8}
BASELINE_CAPACITY = {"address_v2": 2448, "pizza_v2": 960, "order_v2": 195840}

REQUIRED = {"PIZZA": 3, "CITY": 10, "STREET": 10, "descriptive": 3}

#: How many of the new ones must carry `tg:source` -- the line `benchmark.fetch`
#: writes to say "the service told me this". All of them, for cities and pizzas.
FETCHED = {"CITY": 10, "PIZZA": 3}


def picked_from_the_service(catalog, cls: str) -> list:
    """The individuals of `cls` that came from an endpoint, not from a keyboard."""
    return [individual for individual in catalog.instances(cls)
            if catalog.g.value(individual, TG.source) is not None]


def fold(text: str) -> str:
    """No accents, no case, no spaces -- "Quattro Formaggi" ~ "quattroformaggi"."""
    stripped = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in stripped if not unicodedata.combining(c)).casefold().replace(" ", "")


def distance(a: str, b: str) -> int:
    """Levenshtein distance -- how many single-character edits apart two wordings are."""
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def descriptive_wordings(catalog) -> list[tuple[str, str]]:
    """Wordings that are not just another spelling of the canonical name.

    "Margarita" is Margherita misspelled -- two edits away, a *spelling*. "Four
    Cheese" and "mushroom pizza" are something else: what the pizza *is*, in the
    customer's words. Those are the ones that make a recognizer work for real
    orders, and the ones this task asks for three more of.
    """
    found = []
    for pizza in catalog.instances("PIZZA"):
        name = fold(catalog.name(pizza))
        for label in catalog.labels(pizza):
            if distance(fold(label), name) > max(2, len(name) // 4):
                found.append((catalog.name(pizza), label))
    return found


@pytest.mark.parametrize("cls", ["CITY", "STREET", "PIZZA"])
def test_the_catalog_has_grown(catalog, cls):
    wanted = BASELINE[cls] + REQUIRED[cls]
    have = len(catalog.instances(cls))
    how = ({"CITY": 'python -m benchmark.fetch cities "Grenoble" "Roanne" ...',
            "PIZZA": 'python -m benchmark.fetch pizzas "Capricciosa" ...'}
           .get(cls, "write them in Turtle: one :STREET per :ADDRESS, with :name and rdfs:label"))
    assert have >= wanted, (
        f"{cls}: {have} in the graph, {wanted} needed "
        f"({BASELINE[cls]} were handed out, {REQUIRED[cls]} more are the task). {how}")


@pytest.mark.parametrize("cls", ["CITY", "PIZZA"])
def test_what_the_service_owns_was_taken_from_the_service(catalog, cls):
    """Ten cities and three pizzas, each carrying the line `benchmark.fetch` wrote.

    A city typed by hand is a guess about the delivery area, and a pizza typed by
    hand is a guess about the menu. Both are checkable facts, both belong to the
    service, and `tg:source` is the difference between a benchmark and a wish.
    """
    fetched = picked_from_the_service(catalog, cls)
    assert len(fetched) >= FETCHED[cls], (
        f"{len(fetched)} {cls.lower()}(s) in the graph carry tg:source, {FETCHED[cls]} needed. "
        f"Pick them from the endpoint instead of typing them: "
        f"python -m benchmark.fetch {'cities' if cls == 'CITY' else 'pizzas'} --"
        f"{'search saint' if cls == 'CITY' else 'list'}")


def test_the_streets_are_yours(catalog):
    """The other half: no endpoint has your streets, so none of them may claim one.

    If a street carries `tg:source`, something wrote it that should not have --
    the fetch tool never writes streets, because `GET /city` does not know any.
    """
    invented = [catalog.name(street) for street in picked_from_the_service(catalog, "STREET")]
    assert not invented, (
        f"these streets claim to come from the service: {invented}. They cannot -- "
        f"the Pizza API validates an address, it does not list streets.")


def test_three_more_descriptive_pizza_wordings(catalog):
    found = descriptive_wordings(catalog)
    wanted = BASELINE["descriptive"] + REQUIRED["descriptive"]
    assert len(found) >= wanted, (
        f"{len(found)} descriptive wording(s), {wanted} needed. A misspelling does not count -- "
        f"a name that says what the pizza IS does: 'the four cheese one', 'pizza with mushrooms', "
        f"'the spicy one'. Found so far: {sorted(found)}")


def test_every_address_has_its_own_house_number(catalog):
    """Ten streets are ten addresses, and an address without a number is not one."""
    numbers = {catalog.part(address, "STREETNUMBER") for address in catalog.instances("ADDRESS")}
    numbers.discard(None)
    wanted = BASELINE["ADDRESS"] + REQUIRED["STREET"]
    assert len(catalog.instances("ADDRESS")) >= wanted, (
        f"{len(catalog.instances('ADDRESS'))} addresses, {wanted} needed -- "
        f"each of your ten streets belongs to one.")
    assert len(numbers) >= wanted, (
        f"only {len(numbers)} distinct house numbers over {wanted} addresses: "
        f"write one per address (:sn12 a :STREETNUMBER ; :name \"18\" ; rdfs:label \"18\", \"no 18\" .)")


def test_every_street_belongs_to_an_address(catalog):
    """A street nothing links to can never be drawn -- it grows the file, not the benchmark."""
    used = {catalog.part(address, "STREET") for address in catalog.instances("ADDRESS")}
    orphans = [catalog.name(street) for street in catalog.instances("STREET") if street not in used]
    assert not orphans, (
        f"these streets are in the graph but no :ADDRESS uses them: {orphans}. "
        f"A slot is filled by drawing an :ADDRESS, so add one per street: "
        f":a12 a :ADDRESS ; :hasStreet :st12 ; :hasStreetNumber :sn12 ; :hasCity :grenoble .")


def test_cities_are_reused_by_several_addresses(catalog):
    """The whole point: a second address in Lyon LINKS to the Lyon that exists.

    If every address has its own private city, the graph is a list of records
    with extra syntax, and the constraint "a city is defined once" -- which is
    what keeps `:deliverable` from drifting -- buys you nothing.
    """
    from collections import Counter

    counted = Counter(catalog.part(address, "CITY") for address in catalog.instances("ADDRESS"))
    shared = [city for city, count in counted.items() if count >= 2]
    assert len(shared) >= 3, (
        f"only {len(shared)} city/cities serve more than one address. Reuse the individuals "
        f"that are already in the graph (:hasCity :lyon) instead of adding a new one per address.")


@pytest.mark.parametrize("benchmark", ["address_v2", "pizza_v2", "order_v2"])
def test_the_generator_can_now_produce_more_sentences(catalog, benchmark):
    """The number that makes the task visible: cases available before and after.

    Write both numbers into your report. They are the answer to "what did
    extending the meta model buy us" -- together with what the interval did.
    """
    now = capacity(catalog, benchmark)
    was = BASELINE_CAPACITY[benchmark]
    assert now > was, (
        f"{benchmark}: {now} different sentences, unchanged from the {was} handed out. "
        f"Nothing you added is reachable from a pattern of this benchmark.")
