"""Pick benchmark instances from the Pizza API and write them into the graph.

The service knows two things this benchmark is about and you do not get to
invent: **which pizzas exist** (`GET /pizza`, twenty of them, with the ids
`POST /order` wants) and **which cities it delivers to** (`GET /city` — every
commune of France plus Leipzig, Halle and Dresden, about 32 700 names). This
tool is how they get from there into `benchmark/data/`.

Browse first, then pick:

    python -m benchmark.fetch cities --search saint-eti      # what is there?
    python -m benchmark.fetch cities --search "" --limit 20  # the twenty largest
    python -m benchmark.fetch pizzas --list                  # the whole menu

    python -m benchmark.fetch cities Grenoble Roanne Firminy Montbrison
    python -m benchmark.fetch pizzas Capricciosa Tartufo Rucola

Every picked instance is appended to `benchmark/data/picked.ttl` with the
canonical value **as the service spells it** and a note saying where it came
from:

    :grenoble a :CITY ; :name "Grenoble" ; :deliverable true ;
        rdfs:label "Grenoble", "grenoble" ;
        tg:source "GET /city" ; tg:fetchedAt "2026-09-18"^^xsd:date .

Three rules this tool enforces, because each of them is a way a benchmark
quietly stops being one:

* **Nothing is written that the service does not know.** A city it has never
  heard of, a pizza that is not on the menu — refused, with the search that
  would have found the right spelling.
* **Nothing is written twice.** If the name is already in the graph, you get a
  line saying which individual already has it. That is the "a city is defined
  exactly once" constraint, enforced at the moment it would be broken rather
  than by a test afterwards.
* **The canonical value comes from the service, the wordings come from you.**
  The tool writes the name and its lower-case form, and that is deliberately
  boring: the wordings a real customer types ("St-Étienne", "the truffle one")
  are the part of a benchmark a human has to add, and Task 3 asks you to.

What this tool does **not** do: streets and house numbers. The service does not
have them — it validates them, it does not list them — so they are yours to
write, by hand, in Turtle, linked to a city you picked here.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import unicodedata
from pathlib import Path

from benchmark.catalog import Catalog, DATA_DIR

PICKED = DATA_DIR / "picked.ttl"

HEADER = """# Instances picked from the Pizza API with `python -m benchmark.fetch`.
#
# The canonical values in this file come from the service -- a pizza's id is the
# one POST /order wants, a city is in the delivery area because GET /city listed
# it. Do not edit those by hand: re-fetch instead, so the graph and the service
# cannot drift apart.
#
# DO add wordings here, or in catalog.ttl: every `rdfs:label` beyond the two the
# tool wrote is a sentence the generator can produce and a spelling your bot has
# to survive.

@prefix :     <http://example.org/pizza/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix tg:   <http://example.org/testgen/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
"""


def slug(name: str, upper: bool = False) -> str:
    """A URI-safe local name: "Saint-Étienne" -> saintEtienne, "Frutti di Mare" -> FruttiDiMare.

    Deterministic on purpose: picking Saint-Étienne twice produces the same
    resource, which is what makes "already in the graph" detectable at all.
    """
    stripped = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(c for c in stripped if not unicodedata.combining(c))
    words = [w for w in "".join(c if c.isalnum() else " " for c in ascii_only).split() if w]
    if not words:
        raise ValueError(f"{name!r} has no letters to make a name from")
    parts = [w[0].upper() + w[1:] for w in words]
    if not upper:
        parts[0] = parts[0][0].lower() + parts[0][1:]
    return "".join(parts)


def wordings(name: str) -> list[str]:
    """The two spellings the tool is willing to claim: as written, and lower case."""
    return sorted({name, name.lower()})


def existing_names(catalog: Catalog, cls: str) -> dict[str, str]:
    """name (folded) -> the individual that already has it."""
    return {fold(catalog.name(individual)): str(individual).rsplit("/", 1)[-1]
            for individual in catalog.instances(cls) if catalog.name(individual)}


def fold(text: str | None) -> str:
    stripped = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(c for c in stripped if not unicodedata.combining(c))
    return " ".join(stripped.replace("-", " ").split()).casefold()


def append(turtle: str) -> Path:
    """Append to picked.ttl, creating it with its header the first time."""
    if not PICKED.exists():
        PICKED.write_text(HEADER, encoding="utf-8")
    with PICKED.open("a", encoding="utf-8") as handle:
        handle.write(turtle)
    return PICKED


def today() -> str:
    return _datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# cities
# ---------------------------------------------------------------------------


def search_cities(query: str, limit: int) -> int:
    from pizzabot import log, pizza_api

    found = pizza_api.cities(q=query or None, limit=limit)
    log.step(f"GET /city?q={query}&limit={limit} -- {len(found)} city/cities, largest first")
    for city in found:
        log.detail(f"{city['name']:<32} {city['country']}  {city['population']:>9,}", indent="    ")
    log.plain()
    log.hint("pick some:  python -m benchmark.fetch cities " +
             " ".join(f'"{city["name"]}"' for city in found[:3]))
    return 0


def pick_cities(names: list[str]) -> int:
    from pizzabot import log, pizza_api

    catalog = Catalog()
    known = existing_names(catalog, "CITY")
    written, skipped = [], []
    for name in names:
        found = [city for city in pizza_api.cities(q=name, limit=1000)
                 if fold(city["name"]) == fold(name)]
        if not found:
            log.fail(f"{name}: the service does not deliver there")
            log.hint(f"search for the right spelling: "
                     f"python -m benchmark.fetch cities --search {name[:12]}")
            skipped.append(name)
            continue
        city = found[0]
        if fold(city["name"]) in known:
            log.warn(f"{city['name']}: already in the graph as :{known[fold(city['name'])]} "
                     f"-- a city is defined exactly once, so nothing was written. "
                     f"Link your address to it: :hasCity :{known[fold(city['name'])]}")
            skipped.append(name)
            continue
        local = slug(city["name"])
        labels = ", ".join(f'"{wording}"' for wording in wordings(city["name"]))
        append(f'\n:{local} a :CITY ; :name "{city["name"]}" ; :deliverable true ;\n'
               f'    rdfs:label {labels} ;\n'
               f'    tg:source "GET /city" ; tg:fetchedAt "{today()}"^^xsd:date .\n')
        known[fold(city["name"])] = local
        written.append(f":{local} ({city['country']}, {city['population']:,} inhabitants)")
        log.ok(f"{city['name']} -> :{local}")

    return _report(written, skipped, "city", "cities")


# ---------------------------------------------------------------------------
# pizzas
# ---------------------------------------------------------------------------


def list_menu() -> int:
    from pizzabot import log, pizza_api

    catalog = Catalog()
    known = existing_names(catalog, "PIZZA")
    log.step("GET /pizza -- the menu")
    for item in pizza_api.menu():
        mark = "already in the graph" if fold(item["name"]) in known else ""
        log.detail(f"{item['id']:>3}  {item['name']:<24} {mark}", indent="    ")
    log.plain()
    log.hint("pick some:  python -m benchmark.fetch pizzas \"Capricciosa\" \"Tartufo\"")
    return 0


def pick_pizzas(names: list[str]) -> int:
    from pizzabot import log, pizza_api

    catalog = Catalog()
    known = existing_names(catalog, "PIZZA")
    menu = pizza_api.menu()
    written, skipped = [], []
    for name in names:
        found = [item for item in menu if fold(item["name"]) == fold(name)]
        if not found:
            log.fail(f"{name}: not on the menu of GET /pizza")
            log.hint("see what is: python -m benchmark.fetch pizzas --list")
            skipped.append(name)
            continue
        item = found[0]
        if fold(item["name"]) in known:
            log.warn(f"{item['name']}: already in the graph as :{known[fold(item['name'])]} "
                     f"-- nothing written")
            skipped.append(name)
            continue
        local = slug(item["name"], upper=True)
        labels = ", ".join(f'"{wording}"' for wording in wordings(item["name"]))
        append(f'\n:{local} a :PIZZA ; :pizzaId {item["id"]} ; :name "{item["name"]}" ; :onMenu true ;\n'
               f'    rdfs:label {labels} ;\n'
               f'    tg:source "GET /pizza" ; tg:fetchedAt "{today()}"^^xsd:date .\n')
        known[fold(item["name"])] = local
        written.append(f":{local} (id {item['id']})")
        log.ok(f"{item['name']} -> :{local}, id {item['id']}")

    return _report(written, skipped, "pizza", "pizzas")


def _report(written: list[str], skipped: list[str], singular: str, plural: str) -> int:
    from pizzabot import log

    log.plain()
    if written:
        log.result(f"{len(written)} {plural if len(written) != 1 else singular} written to {PICKED}")
        log.hint("now: add the wordings a customer would type, then `pytest -q`")
    if skipped:
        log.warn(f"{len(skipped)} skipped: {', '.join(skipped)}")
    return 1 if skipped and not written else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pick benchmark instances from the Pizza API.",
        epilog="Streets and house numbers are not here: the service does not have them. "
               "Write them by hand, linked to a city you picked.")
    sub = parser.add_subparsers(dest="what", required=True)

    cities = sub.add_parser("cities", help="pick cities from GET /city")
    cities.add_argument("names", nargs="*", help="the cities to write into the graph")
    cities.add_argument("--search", metavar="TEXT", help="browse the delivery area instead of picking")
    cities.add_argument("--limit", type=int, default=20, help="how many to show when searching")

    pizzas = sub.add_parser("pizzas", help="pick pizzas from GET /pizza")
    pizzas.add_argument("names", nargs="*", help="the pizzas to write into the graph")
    pizzas.add_argument("--list", action="store_true", help="show the menu instead of picking")

    arguments = parser.parse_args(argv)

    from pizzabot import log, pizza_api

    log.title(f"benchmark.fetch -- Pizza API at {pizza_api.BASE}")
    try:
        if arguments.what == "cities":
            if arguments.search is not None:
                return search_cities(arguments.search, arguments.limit)
            if not arguments.names:
                return search_cities("", arguments.limit)
            return pick_cities(arguments.names)
        if arguments.list or not arguments.names:
            return list_menu()
        return pick_pizzas(arguments.names)
    except pizza_api.PizzaApiError as error:
        pizza_api.explain_and_exit(error)


if __name__ == "__main__":
    raise SystemExit(main())
