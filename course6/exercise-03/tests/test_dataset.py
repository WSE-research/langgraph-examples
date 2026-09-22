"""The dataset itself: is it the data we think it is?

These tests are about the Turtle files, not about the code that reads them.
They are what makes extending the catalog safe: add a pizza or an address,
run pytest, and a missing label or a duplicated id is named on the spot.
"""

import pytest
from rdflib import RDF, RDFS, Literal

from benchmark.catalog import PZ

# The menu of the Pizza API (GET /pizza) as of 2026-09-20 -- a snapshot, kept
# here on purpose. It is what makes these tests run offline, and
# `test_the_snapshot_still_matches_the_service` is what keeps it from going
# stale silently: when the service changes, that test fails and this list and
# the graph are updated together.
#
# Note what is NOT required: that every pizza on the menu is in the catalog.
# Picking which ones to benchmark is your job (`python -m benchmark.fetch`);
# agreeing with the service about the ones you picked is not negotiable.
KNOWN_MENU = {
    1: "Margherita", 2: "Pepperoni", 3: "Hawaiian", 4: "Quattro Formaggi", 5: "Funghi",
    6: "Salami", 7: "Prosciutto", 8: "Diavola", 9: "Vegetariana", 10: "Calzone",
    11: "Capricciosa", 12: "Marinara", 13: "Siciliana", 14: "Tonno", 15: "Frutti di Mare",
    16: "Quattro Stagioni", 17: "Bufala", 18: "Tartufo", 19: "Rucola", 20: "Boscaiola",
    21: "Ortolana", 22: "Verdure",
}
ADDRESS_PARTS = ("STREET", "STREETNUMBER", "CITY")


def service_available() -> bool:
    """Is the Pizza API (or the stub) reachable? These tests must run offline too."""
    from pizzabot import pizza_api

    return pizza_api.ping()[0]


def city_key(name: str) -> str:
    """Fold a city name the way the Pizza API does: no accents, no case, no hyphens."""
    import unicodedata

    stripped = unicodedata.normalize("NFKD", name or "")
    stripped = "".join(c for c in stripped if not unicodedata.combining(c))
    return " ".join(stripped.replace("-", " ").split()).casefold()


def test_every_pizza_in_the_catalog_is_on_the_menu_with_the_right_id(catalog):
    """A pizza you can order is one the service sells, under the id it uses.

    A pizza with `:onMenu false` carries no id and is skipped here on purpose:
    it is a thing a customer may ask for and we do not sell, and its expected
    outcome is "nothing recognised". Adding such a pizza must never look like a
    menu change -- that is what the next test guards.
    """
    for pizza in catalog.instances("PIZZA"):
        if not catalog.servable(pizza):
            continue
        pizza_id, name = catalog.expected(pizza), catalog.name(pizza)
        assert pizza_id in KNOWN_MENU, (
            f"{name}: id {pizza_id} is not on the menu. Do not type a pizza into the "
            f"graph -- pick it: python -m benchmark.fetch pizzas \"{name}\"")
        assert KNOWN_MENU[pizza_id] == name, (
            f"id {pizza_id} is {KNOWN_MENU[pizza_id]!r} on the menu, {name!r} in the graph")


def test_every_pizza_says_whether_it_is_on_the_menu(catalog):
    """`:onMenu` and `:pizzaId` must agree: sellable <-> it has an id."""
    for pizza in catalog.instances("PIZZA"):
        flag = catalog.g.value(pizza, PZ.onMenu)
        assert flag is not None, f"{pizza} does not say whether it is :onMenu"
        has_id = catalog.expected(pizza) is not None
        assert bool(flag.toPython()) == has_id, (
            f"{pizza}: :onMenu {flag.toPython()} but "
            f"{'an' if has_id else 'no'} :pizzaId -- an off-menu pizza has no id, "
            f"and a pizza on the menu must carry the id GET /pizza uses")


def test_every_pizza_has_a_canonical_name_and_several_wordings(catalog):
    for pizza in catalog.instances("PIZZA"):
        assert catalog.name(pizza), f"{pizza} has no :name"
        labels = catalog.labels(pizza)
        assert len(labels) >= 2, f"{pizza} has only {labels} -- one wording is not a benchmark"
        assert catalog.name(pizza) in labels, f"{pizza}: the canonical name is not among its labels"


def test_every_address_has_exactly_one_street_number_and_city(catalog):
    addresses = catalog.instances("ADDRESS")
    assert len(addresses) >= 5, "too few addresses to measure anything"
    for address in addresses:
        for part_class in ADDRESS_PARTS:
            part = catalog.part(address, part_class)
            assert part is not None, f"{address} has no {part_class}"
            assert catalog.name(part), f"{part} has no :name"
            assert catalog.labels(part), f"{part} has no wording"


def test_the_expected_record_of_an_address_is_the_record_the_bot_must_produce(catalog):
    records = [catalog.expected(a) for a in catalog.instances("ADDRESS")]
    for record in records:
        assert set(record) == {"street", "house_number", "city"}, \
            "the record must have exactly the keys of state.Address -- it IS the expected output"
        assert all(record.values())


def test_a_city_is_defined_exactly_once(catalog):
    """The constraint that makes this a knowledge graph and not a list of strings.

    Two individuals with the same city name would give a generated sentence two
    possible expected values -- and would let one of them drift (deliverable in
    one place, not in the other). When you add an address in a city that is
    already in the graph, you LINK to that city; you do not write it again.
    """
    seen = {}
    for city in catalog.instances("CITY"):
        key = city_key(catalog.name(city))
        owner = seen.setdefault(key, city)
        assert owner == city, (
            f"{catalog.name(city)} is defined twice: {owner} and {city}. "
            f"Reuse the individual that is already there -- :hasCity {owner.split('/')[-1]}")


def test_every_address_links_to_a_city_that_exists_on_its_own(catalog):
    """An address points at a :CITY individual; it never carries a city string."""
    cities = set(catalog.instances("CITY"))
    for address in catalog.instances("ADDRESS"):
        city = catalog.part(address, "CITY")
        assert city in cities, f"{address}: its city is not one of the catalog's :CITY individuals"


def test_every_city_says_whether_we_deliver_there(catalog):
    """`:deliverable` is what turns a drawn city into a recognition or a refusal.

    The delivery area is ~32 700 cities since 2026-09-18, so this file cannot
    list it. What it can do is insist that every city in the graph has made up
    its mind, and that at least one of them is outside -- a benchmark in which
    every case is deliverable measures only the happy path.
    """
    outside = []
    for city in catalog.instances("CITY"):
        flag = catalog.g.value(city, PZ.deliverable)
        assert flag is not None, (
            f"{city} does not say whether it is deliverable. Pick it from the service "
            f"instead of typing it: python -m benchmark.fetch cities \"{catalog.name(city)}\"")
        if not flag.toPython():
            outside.append(catalog.name(city))
    assert outside, ("no city outside the delivery area -- nothing to refuse in a test case. "
                     "Since the area is all of France, an outsider has to be a foreign city.")


@pytest.mark.parametrize("what", ["cities", "menu"])
def test_the_snapshot_still_matches_the_service(catalog, what):
    """The graph and the service, compared -- when the service is reachable.

    Skipped offline, on purpose: the suite has to run on a train. But the moment
    a machine can reach the API, every `:deliverable` flag and every `:pizzaId`
    in the graph is checked against it, so a benchmark can never quietly measure
    a world the service does not live in.
    """
    from pizzabot import pizza_api

    if not service_available():
        pytest.skip(f"Pizza API at {pizza_api.BASE} not reachable -- run pizza_api_stub.py")

    if what == "menu":
        live = {item["id"]: item["name"] for item in pizza_api.menu(refresh=True)}
        assert live == KNOWN_MENU, (
            "GET /pizza has changed. Update KNOWN_MENU in this file and re-fetch the "
            "pizzas in your graph, in the same commit.")
        return

    for city in catalog.instances("CITY"):
        name = catalog.name(city)
        expected = bool(catalog.g.value(city, PZ.deliverable).toPython())
        assert pizza_api.delivers_to(name) == expected, (
            f"{name}: the graph says deliverable={expected}, GET /city says the opposite")


def test_no_wording_is_ambiguous_within_a_class(catalog):
    """Two DIFFERENT individuals of one class must not share a wording: a
    generated case whose input matches two expected values cannot be scored.
    Several spellings of the same individual are the point of the catalog."""
    for cls in ("PIZZA", "CITY", "STREET"):
        seen = {}
        for individual in catalog.instances(cls):
            for label in catalog.labels(individual):
                key = label.strip().casefold()
                owner = seen.setdefault(key, individual)
                assert owner == individual, f"{cls}: {label!r} is used by {owner} and {individual}"


def test_every_labelled_individual_is_typed(catalog):
    for subject in set(catalog.g.subjects(RDFS.label, None)):
        assert list(catalog.g.objects(subject, RDF.type)), f"{subject} has labels but no type"


@pytest.mark.parametrize("benchmark", ["address_v2", "pizza_v2", "order_v2"])
def test_patterns_only_use_slots_the_catalog_can_fill(catalog, benchmark):
    import re

    patterns = catalog.patterns(benchmark)
    assert patterns, f"no pattern for {benchmark}"
    for template in patterns:
        for cls, part, _ in re.findall(r"{(\w+)(?::(\w+))?(\??)}", template):
            individuals = catalog.instances(cls)
            assert individuals, f"{template}: nothing is typed :{cls}"
            if part:
                assert all(catalog.part(i, part) is not None for i in individuals), \
                    f"{template}: an individual of :{cls} has no :{part}"
            else:
                assert all(catalog.labels(i) for i in individuals), \
                    f"{template}: an individual of :{cls} has no wording to render"
