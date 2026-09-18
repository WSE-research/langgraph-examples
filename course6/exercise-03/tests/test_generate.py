"""The generator: does it draw what it promises?

The generator is given to you, so these tests are not here to make you write it
-- they are here to say what "a generated case" is allowed to be, and to catch
the two ways generated data quietly stops being a benchmark: the same sentence
counted twice, and an expected value that nobody drew.
"""

import pytest

from benchmark.generate import capacity, generate, read_jsonl, write_jsonl

BENCHMARKS = ["address_v2", "pizza_v2", "order_v2"]


@pytest.mark.parametrize("benchmark", BENCHMARKS)
def test_the_same_seed_produces_the_same_cases(catalog, benchmark):
    """Reproducible, or the number in your report belongs to no run."""
    assert generate(catalog, benchmark, n=8, seed=5) == generate(catalog, benchmark, n=8, seed=5)


@pytest.mark.parametrize("benchmark", BENCHMARKS)
def test_a_different_seed_produces_different_cases(catalog, benchmark):
    first = [row["input"] for row in generate(catalog, benchmark, n=8, seed=1)]
    second = [row["input"] for row in generate(catalog, benchmark, n=8, seed=2)]
    assert first != second


@pytest.mark.parametrize("benchmark", BENCHMARKS)
def test_no_sentence_is_drawn_twice(catalog, benchmark):
    rows = generate(catalog, benchmark, n=40, seed=3)
    assert len({row["input"] for row in rows}) == len(rows)


def test_asking_for_more_than_the_catalog_has_warns_and_returns_what_exists(catalog):
    """The warning the exercise is about: the data, not the harness, ran out."""
    available = capacity(catalog, "pizza_v2")
    with pytest.warns(UserWarning, match="requested"):
        rows = generate(catalog, "pizza_v2", n=available + 50, seed=4)
    assert len(rows) <= available


def test_an_expected_value_is_always_a_value_that_was_drawn(catalog):
    """The generator produces INPUTS. Nothing invents an expected value."""
    ids = {catalog.expected(p) for p in catalog.instances("PIZZA")}
    for row in generate(catalog, "pizza_v2", n=20, seed=6):
        assert row["expected"]["pizza_id"] in ids


def test_an_address_case_expects_the_record_the_component_must_produce(catalog):
    for row in generate(catalog, "address_v2", n=20, seed=7):
        expected = row["expected"]["address"]
        if expected is None:                       # a refusal case
            assert not row["servable"]
            continue
        assert set(expected) == {"street", "house_number", "city"}


def test_a_city_we_do_not_deliver_to_expects_nothing(catalog):
    """`:deliverable false` -> the case is a refusal, and that is a test case too."""
    rows = generate(catalog, "address_v2", n=60, seed=8)
    refusals = [row for row in rows if not row["servable"]]
    assert refusals, "no refusal case in 60 draws -- is every city deliverable?"
    assert all(row["expected"]["address"] is None for row in refusals)


def test_a_pizza_that_is_not_on_the_menu_expects_nothing(catalog):
    off_menu = [p for p in catalog.instances("PIZZA") if not catalog.servable(p)]
    if not off_menu:
        pytest.skip("no off-menu pizza in the catalog yet (Task 3 adds them)")
    rows = [row for row in generate(catalog, "pizza_v2", n=80, seed=9) if not row["servable"]]
    assert rows, "off-menu pizzas exist but none was drawn in 80 cases"
    assert all(row["expected"]["pizza_id"] is None for row in rows)


def test_every_row_carries_what_a_number_needs_to_be_honest(catalog):
    for row in generate(catalog, "order_v2", n=5, seed=10):
        assert row["source"] == "generated"
        assert row["seed"] == 10
        assert row["pattern"] and row["benchmark"] == "order_v2"
        assert row["exercises"] == ["address_recognition", "pizza_recognition"]


def test_capacity_grows_with_the_data_and_is_never_a_lie(catalog):
    """`capacity` counts the sentences that exist; drawing can never exceed it."""
    available = capacity(catalog, "address_v2")
    assert available > 0
    assert len(generate(catalog, "address_v2", n=available + 10, seed=11)) <= available


def test_the_artifact_survives_a_round_trip(catalog, tmp_path):
    rows = generate(catalog, "address_v2", n=4, seed=12)
    assert read_jsonl(write_jsonl(tmp_path / "cases.jsonl", rows)) == rows
