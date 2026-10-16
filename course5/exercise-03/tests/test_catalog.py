"""The app: does the API answer the way the generator will need it to?"""

import pytest
from rdflib import URIRef

from benchmark import Catalog
from benchmark.catalog import DATA_DIR, PZ


def test_the_catalog_loads_every_turtle_file_of_the_data_directory(catalog):
    assert len(catalog.sources) == len(list(DATA_DIR.glob("*.ttl")))
    assert len(catalog) > 200


def test_patterns_are_returned_per_benchmark(catalog):
    address = catalog.patterns("address_v2")
    order = catalog.patterns("order_v2")
    assert all("{ADDRESS:" in template for template in address)
    assert any("{PIZZA}" in template for template in order)
    assert not set(address) & set(order), "a pattern is in two benchmarks at once"
    assert catalog.patterns("no_such_benchmark") == []


def test_instances_are_the_individuals_of_a_slot_class(catalog):
    # ">= 10", not "== 10": extending the catalog is the task, and a test that
    # counts individuals would punish a team for doing it. What the menu of the
    # API contains is checked where it belongs -- tests/test_dataset.py.
    assert len(catalog.instances("PIZZA")) >= 10
    assert PZ.Margherita in catalog.instances("PIZZA")
    assert catalog.instances("NOTHING") == []


def test_part_resolves_a_qualified_slot_without_knowing_the_property(catalog):
    address = PZ.a1
    assert catalog.part(address, "STREET") == PZ.st1
    assert catalog.part(address, "CITY") == PZ.saintEtienne
    assert catalog.part(address, "PIZZA") is None


def test_the_parts_of_one_address_belong_together(catalog):
    """The reason an address is a resource and not three strings."""
    for address in catalog.instances("ADDRESS"):
        record = catalog.expected(address)
        street = catalog.part(address, "STREET")
        city = catalog.part(address, "CITY")
        assert record["street"] == catalog.name(street)
        assert record["city"] == catalog.name(city)


def test_labels_are_the_wordings_and_name_is_the_canonical_form(catalog):
    labels = catalog.labels(PZ.QuattroFormaggi)
    assert "4 formaggi" in labels and "Quattro Formaggi" in labels
    assert catalog.name(PZ.QuattroFormaggi) == "Quattro Formaggi"


def test_expected_is_the_api_id_for_a_pizza_and_a_record_for_an_address(catalog):
    assert catalog.expected(PZ.Margherita) == 1
    assert catalog.expected(PZ.a1) == {
        "street": "Rue Michelet", "house_number": "5", "city": "Saint-Étienne",
    }


def test_fills_says_which_class_fills_which_state_field(catalog):
    assert catalog.fills() == {"PIZZA": "pizza_id", "ADDRESS": "address"}


def test_a_single_file_can_be_loaded_on_its_own(tmp_path):
    single = Catalog(DATA_DIR / "catalog.ttl")
    assert len(single.instances("PIZZA")) >= 10
    assert single.patterns("address_v2") == [], "patterns live in the model file"


def test_a_missing_source_fails_loudly(tmp_path):
    with pytest.raises(FileNotFoundError):
        Catalog(tmp_path)


def test_own_sparql_is_possible_but_not_necessary(catalog):
    rows = list(catalog.query(
        "PREFIX pz: <http://example.org/pizza/> SELECT ?p WHERE { ?p a pz:PIZZA }"))
    assert len(rows) == len(catalog.instances("PIZZA"))
    assert isinstance(rows[0].p, URIRef)
