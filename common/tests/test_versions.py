"""Every version keeps the contract it was published with.

The expectations below are written out literally, not derived from `main.py`:
a published version is a promise to an exercise, and an edit of `main.py` that
changes what v1 serves must fail here -- not silently pass because the test
read the same list the edit changed.
"""

from __future__ import annotations

import random
import re

import pytest

import main
from conftest import VERSION_KEYS, base, order, validate

MENU_22 = [
    "Margherita", "Pepperoni", "Hawaiian", "Quattro Formaggi", "Funghi", "Salami",
    "Prosciutto", "Diavola", "Vegetariana", "Calzone", "Capricciosa", "Marinara",
    "Siciliana", "Tonno", "Frutti di Mare", "Quattro Stagioni", "Bufala", "Tartufo",
    "Rucola", "Boscaiola", "Ortolana", "Verdure",
]

# What each published version promised -- the exercise it belongs to, its menu,
# whether pizzas sell out, whether GET /city exists, and its delivery area.
PUBLISHED = {
    "v1": {"menu": MENU_22[:10], "sells_out": False, "city": False, "area": "course"},
    "v2": {"menu": MENU_22, "sells_out": False, "city": True, "area": "full"},
    "v3": {"menu": MENU_22, "sells_out": False, "city": True, "area": "full"},
    "v4": {"menu": MENU_22, "sells_out": False, "city": True, "area": "full"},
    "v5": {"menu": MENU_22, "sells_out": True, "city": True, "area": "full"},
    "v6": {"menu": MENU_22, "sells_out": True, "city": True, "area": "full"},
}
LATEST = {"menu": MENU_22, "sells_out": True, "city": True, "area": "full"}
ALL = {**PUBLISHED, "latest": LATEST}

COURSE_CITIES = ["Leipzig", "Halle", "Dresden", "Saint-Étienne", "Saint-Priest-en-Jarez", "Lyon",
                 "Athens", "Piraeus", "Agia Paraskevi"]

# Spellings the course examples use, accepted everywhere (all are course cities).
ACCEPTED_EVERYWHERE = [
    "Athens", "athens", "ATHENS", "Athina", "Athína", "Αθήνα", "Αθηνα",
    "Piraeus", "PIRAEUS", "Pireas", "Πειραιάς",
    "Agia Paraskevi", "agia paraskevi", "Ayia Paraskevi", "Agía Paraskeví", "Αγία Παρασκευή",
    "Saint-Étienne", "Saint-Etienne", "saint etienne", "SAINT-ETIENNE",
    "Saint-Priest-en-Jarez", "Saint Priest en Jarez", "Lyon", "LYON",
    "Leipzig", "Halle", "Dresden",
]
# Abbreviations the benchmark of Exercise 3 relies on being refused, and the
# standing "outside the delivery area" example of every exercise.
REFUSED_EVERYWHERE = ["Barcelona", "barcelona", "Ath.", "Ag. Paraskevi", "St. Etienne", "St Etienne",
                      "St-Étienne", "St-Priest-en-Jarez", "Atlantis", ""]
# In the full area, but not one of the nine cities of v1.
FULL_AREA_ONLY = ["Paris", "PARIS", "Roanne", "Grenoble", "Firminy", "Montbrison", "Thessaloniki",
                  "Salonica", "Patras", "Heraklion", "Marousi", "Kifisia", "Glyfada", "Zografou",
                  "Kavala"]


# ---------------------------------------------------------------- the menu --

@pytest.mark.parametrize("key", list(ALL))
def test_the_menu_is_frozen(client, key):
    menu = client.get(f"{base(key)}/pizza").json()
    assert [pizza["name"] for pizza in menu] == ALL[key]["menu"]
    assert [pizza["id"] for pizza in menu] == list(range(1, len(ALL[key]["menu"]) + 1))
    fields = {"id", "name", "available"} if ALL[key]["sells_out"] else {"id", "name"}
    assert all(set(pizza) == fields for pizza in menu), menu[0]


@pytest.mark.parametrize("key", list(ALL))
def test_a_direct_call_on_the_port_answers_like_the_proxy(client, key, minute):
    minute(29_000_000)
    assert client.get(f"{base(key, prefixed=False)}/pizza").json() == client.get(f"{base(key)}/pizza").json()


@pytest.mark.parametrize("key", list(ALL))
def test_no_napoli_and_every_name_of_the_exercises_is_there(client, key):
    """"One Pizza Napoli please" is the not-on-the-menu example of Iteration 2."""
    names = [pizza["name"] for pizza in client.get(f"{base(key)}/pizza").json()]
    assert "Napoli" not in names
    for name in ("Margherita", "Quattro Formaggi", "Funghi", "Salami", "Diavola"):
        assert name in names


def test_v1_is_the_ten_pizza_menu_of_lecture_1(client):
    """Ids above ten do not exist in v1 -- an order for one is a 404, not an order."""
    assert order(client, "v1", 11).status_code == 404
    assert order(client, "v1", 10).status_code == 200


# ------------------------------------------------------------ availability --

@pytest.mark.parametrize("key", [k for k in ALL if not ALL[k]["sells_out"]])
def test_versions_without_availability_accept_every_pizza_in_every_minute(client, key, minute):
    """The Iteration 1-4 processes have no answer to a sold-out pizza, so v1-v4 never sell out."""
    for m in range(28_000_000, 28_000_012):
        minute(m)
        response = client.get(f"{base(key)}/pizza")
        assert not any(h.lower().startswith("x-availability") for h in response.headers)
        for pizza in response.json():
            assert order(client, key, pizza["id"], city="Athens").status_code == 200, (key, m, pizza)


@pytest.mark.parametrize("key", [k for k in ALL if not ALL[k]["sells_out"]])
def test_old_versions_ignore_the_test_driver_header(client, key):
    assert order(client, key, 1, accept_everything=True).status_code == 200


@pytest.mark.parametrize("key", [k for k in ALL if ALL[k]["sells_out"]])
def test_two_pizzas_are_sold_out_in_every_minute(client, key, minute):
    for m in range(28_000_000, 28_000_030):
        minute(m)
        first = client.get(f"{base(key)}/pizza")
        second = client.get(f"{base(key)}/pizza")
        sold_out = [p["id"] for p in first.json() if not p["available"]]
        assert len(sold_out) == 2, (key, m, sold_out)
        assert first.json() == second.json(), "two requests within one minute disagree"
        assert first.headers["x-availability-minute"] == main.minute_iso(m)
        assert first.headers["x-availability-valid-until"] == main.minute_iso(m + 1)
        assert first.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("key", [k for k in ALL if ALL[k]["sells_out"]])
def test_a_sold_out_pizza_is_a_409_unless_a_test_driver_orders_it(client, key, minute):
    for m in range(28_000_100, 28_000_105):
        minute(m)
        menu = client.get(f"{base(key)}/pizza").json()
        gone = next(p for p in menu if not p["available"])
        there = next(p for p in menu if p["available"])
        refused = order(client, key, gone["id"])
        assert refused.status_code == 409
        assert gone["name"] in refused.json()["detail"] and "sold out" in refused.json()["detail"]
        assert order(client, key, gone["id"], accept_everything=True).status_code == 200
        assert order(client, key, there["id"]).status_code == 200


@pytest.mark.parametrize("key", [k for k in ALL if ALL[k]["sells_out"]])
def test_the_order_of_the_checks_is_404_then_409_then_400(client, key, minute):
    minute(28_000_200)
    menu = client.get(f"{base(key)}/pizza").json()
    gone = next(p for p in menu if not p["available"])
    there = next(p for p in menu if p["available"])
    assert order(client, key, 999, city="Barcelona").status_code == 404
    assert order(client, key, gone["id"], city="Barcelona").status_code == 409
    assert order(client, key, there["id"], city="Barcelona").status_code == 400


def test_the_draw_is_the_draw_of_version_1_3_0(minute):
    """Same seed, same minute, same 22 pizzas: the same two as before the versions existed."""
    ids = list(range(1, 23))
    for m in range(28_000_000, 28_000_050):
        old = set(random.Random(f"{main.AVAILABILITY_SEED}:{m}").sample(ids, 2))
        assert main.sold_out_ids(m, main.pizzas, 2) == old


def test_v5_v6_and_latest_draw_the_same_pizzas(client, minute):
    for m in range(28_000_300, 28_000_310):
        minute(m)
        answers = [client.get(f"{base(k)}/pizza").json() for k in ("v5", "v6", "latest")]
        assert answers[0] == answers[1] == answers[2]


# ---------------------------------------------------------- delivery area --

@pytest.mark.parametrize("key", list(ALL))
@pytest.mark.parametrize("city", ACCEPTED_EVERYWHERE)
def test_every_course_city_is_accepted_in_every_version(client, key, city):
    assert validate(client, key, city).status_code == 200


@pytest.mark.parametrize("key", list(ALL))
@pytest.mark.parametrize("city", REFUSED_EVERYWHERE)
def test_the_refusal_examples_are_refused_in_every_version(client, key, city):
    response = validate(client, key, city)
    assert response.status_code in (400, 422)
    if city:
        assert response.json()["detail"].startswith(f"We don't deliver to {city}.")


@pytest.mark.parametrize("city", FULL_AREA_ONLY)
def test_v1_delivers_only_to_the_nine_cities_of_the_examples(client, city):
    response = validate(client, "v1", city)
    assert response.status_code == 400
    assert response.json()["detail"] == (f"We don't deliver to {city}. Available cities: "
                                         + ", ".join(COURSE_CITIES))


@pytest.mark.parametrize("key", [k for k in ALL if ALL[k]["area"] == "full"])
@pytest.mark.parametrize("city", FULL_AREA_ONLY)
def test_the_full_area_is_france_and_greece(client, key, city):
    assert validate(client, key, city).status_code == 200


@pytest.mark.parametrize("key", [k for k in ALL if ALL[k]["area"] == "full"])
def test_a_refusal_in_the_full_area_points_to_the_city_search(client, key):
    detail = validate(client, key, "Barcelona").json()["detail"]
    assert "every commune of France, every town and village of Greece" in detail
    assert detail.endswith("Look yours up with GET /city?q=Barcelona")


@pytest.mark.parametrize("key", list(ALL))
def test_street_and_house_number_are_checked_after_the_city(client, key):
    assert validate(client, key, "Athens", street="E").json()["detail"] == "Invalid street name"
    assert validate(client, key, "Athens", house_number="").json()["detail"] == "House number is required"
    assert validate(client, key, "Athens", street="Ermou", house_number="12b").status_code == 200


@pytest.mark.parametrize("key", list(ALL))
def test_a_malformed_body_is_a_422(client, key):
    assert client.post(f"{base(key)}/address/validate", json={"city": "Athens"}).status_code == 422
    assert client.post(f"{base(key)}/order", json={"pizza_id": "one"}).status_code == 422


# ---------------------------------------------------------------- GET /city --

def test_v1_has_no_city_endpoint(client):
    assert client.get(f"{base('v1')}/city").status_code == 404


@pytest.mark.parametrize("key", [k for k in ALL if ALL[k]["city"]])
def test_the_city_endpoint_pages_the_whole_area(client, key):
    response = client.get(f"{base(key)}/city?limit=3")
    assert [city["name"] for city in response.json()] == ["Paris", "Marseille", "Athens"]
    assert int(response.headers["x-total-count"]) > 40_000
    assert all(set(city) == {"name", "country", "population"} for city in response.json())
    assert client.get(f"{base(key)}/city?limit=1001").status_code == 422
    assert client.get(f"{base(key)}/city?limit=0").status_code == 422
    second = client.get(f"{base(key)}/city?limit=2&offset=1").json()
    assert [city["name"] for city in second] == ["Marseille", "Athens"]


@pytest.mark.parametrize("key", [k for k in ALL if ALL[k]["city"]])
@pytest.mark.parametrize("query, first", [
    ("saint-eti", "Saint-Étienne"), ("saint etienne", "Saint-Étienne"), ("lyon", "Lyon"),
    ("athens", "Athens"), ("athina", "Athens"), ("Αθήνα", "Athens"), ("pireas", "Piraeus"),
    ("agia paraskevi", "Agia Paraskevi"), ("patra", "Patras"), ("thessaloniki", "Thessaloniki"),
    ("salonica", "Thessaloniki"), ("leipzig", "Leipzig"), ("grenoble", "Grenoble"),
])
def test_the_city_search_finds_the_examples_first(client, key, query, first):
    found = client.get(f"{base(key)}/city", params={"q": query, "limit": 5}).json()
    assert found and found[0]["name"] == first, (query, found)


@pytest.mark.parametrize("key", [k for k in ALL if ALL[k]["city"]])
def test_whatever_the_search_returns_validates(client, key):
    for query in ("saint", "agia", "athin", "pirae"):
        for city in client.get(f"{base(key)}/city", params={"q": query, "limit": 50}).json():
            assert validate(client, key, city["name"]).status_code == 200, city


@pytest.mark.parametrize("key", [k for k in ALL if ALL[k]["city"]])
def test_barcelona_is_not_in_the_area(client, key):
    response = client.get(f"{base(key)}/city", params={"q": "barcelona"})
    assert response.json() == [] and response.headers["x-total-count"] == "0"


# ------------------------------------------------------------------ orders --

@pytest.mark.parametrize("key", list(ALL))
def test_an_order_can_be_read_back_from_its_own_version(client, key):
    placed = order(client, key, 1, city="Αθήνα", accept_everything=True)
    assert placed.status_code == 200 and placed.json()["status"] == "received"
    order_id = placed.json()["order_id"]
    stored = client.get(f"{base(key)}/order/{order_id}").json()
    assert stored["pizza_id"] == 1 and stored["address"]["city"] == "Αθήνα"   # the spelling sent
    other = "v2" if key == "v1" else "v1"
    assert client.get(f"{base(other)}/order/{order_id}").status_code == 404
    assert client.get(f"{base(key)}/order/does-not-exist").status_code == 404


# ------------------------------------------------------------ documentation --

@pytest.mark.parametrize("key", list(ALL))
def test_every_version_documents_itself_at_its_own_url(client, key):
    page = client.get(f"{base(key)}/")
    assert page.status_code == 200 and "swagger" in page.text.lower()
    assert f"url: '{base(key)}/openapi.json'" in page.text
    schema = client.get(f"{base(key)}/openapi.json").json()
    expected = {"/pizza", "/address/validate", "/order", "/order/{order_id}"}
    if ALL[key]["city"]:
        expected.add("/city")
    assert set(schema["paths"]) == expected
    assert schema["info"]["version"] == (key if key != "latest" else main.LATEST.number)


@pytest.mark.parametrize("key", VERSION_KEYS)
def test_a_version_without_its_slash_is_redirected_relatively(client, key):
    for path in (f"/pizza-api/{key}", f"/{key}"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 307 and response.headers["location"] == f"{key}/"


def test_the_latest_version_lists_every_exercise_version(client):
    description = client.get("/pizza-api/openapi.json").json()["info"]["description"]
    for key in VERSION_KEYS:
        assert re.search(rf"\[`{key}`\]\({key}/\)", description), key


def test_the_published_versions_are_exactly_v1_to_v6():
    assert VERSION_KEYS == ["v1", "v2", "v3", "v4", "v5", "v6"]
    assert set(PUBLISHED) == set(VERSION_KEYS)
