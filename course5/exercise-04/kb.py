"""The knowledge base: three Turtle files, and the questions we ask them. GIVEN.

Copy this file into your repository as `pizzabot/kb.py`, and copy `data/`
beside your `pizzabot/` package:

    my-pizzabot/
        pizzabot/kb.py        <- this file
        data/menu-facts.ttl   <- the three Turtle files
        data/wikidata.ttl
        data/wikidata-links.ttl

This is **the only module in your repository that contains SPARQL.** Nodes call
the functions below; if a node ever builds a query itself, the seam has been
drawn in the wrong place. Every query is printed and explained in the exercise
sheet (Task 2b, Q0-Q8) -- read it there, then read it here, and you will have
seen each one twice, which is about what SPARQL needs.

Two rules this file follows and you should keep following:

* **user input is passed as a binding, never concatenated.** `initBindings`
  hands rdflib a value, not a piece of query text -- the same reason you do not
  build SQL with `+`. The one query that *is* assembled (Q7) assembles IRIs
  that came out of Q0/Q8, never words that came from a guest.
* **nothing of rdflib leaves this module.** Every function returns plain str,
  int, bool, dict and list, so that a node never has to know what a `URIRef`
  is -- and so that this file could be swapped for a real triplestore over
  HTTP without a single node noticing.

    python -m pizzabot.kb --selftest      # the row counts of Q0-Q8
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from rdflib import Graph, Literal

PZ = "http://example.org/pizza/"
DATA = Path(__file__).resolve().parent.parent / "data"
FILES = ("menu-facts.ttl", "wikidata.ttl", "wikidata-links.ttl")

PREFIXES = """
PREFIX pz:   <http://example.org/pizza/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX prov: <http://www.w3.org/ns/prov#>
"""


# =========================================================================
# the graph -- loaded once, read only
# =========================================================================


@lru_cache(maxsize=1)
def graph() -> Graph:
    """The three files as one graph. 617 triples; milliseconds to load."""
    merged = Graph()
    for name in FILES:
        merged.parse(DATA / name, format="turtle")
    return merged


def _rows(query: str, **bindings) -> list[dict]:
    """Run a query, return plain dicts. The only place rdflib is touched."""
    result = graph().query(
        PREFIXES + query,
        initBindings={key: Literal(value) for key, value in bindings.items()},
    )
    return [
        {str(var): (None if row[index] is None else str(row[index]))
         for index, var in enumerate(result.vars)}
        for row in result
    ]


def _local(iri: str | None) -> str | None:
    """`http://example.org/pizza/Hawaiian` -> `Hawaiian`. A name, not a thing."""
    return iri.rsplit("/", 1)[1] if iri else None


# =========================================================================
# Q0 / Q8 -- string to thing. Every other question starts here.
# =========================================================================

Q0_PIZZA_IRI = """
SELECT ?pizza ?name WHERE {
  ?pizza a pz:Pizza ; pz:name ?name .
  { ?pizza pz:name ?written } UNION { ?pizza pz:alias ?written }
  FILTER (LCASE(STR(?written)) = LCASE(?wanted))
}
"""

Q8_TOPPING_IRI = """
SELECT ?topping ?name WHERE {
  ?topping a pz:Topping ; pz:name ?name .
  { ?topping pz:name ?written } UNION { ?topping pz:alias ?written }
  FILTER (LCASE(STR(?written)) = LCASE(?wanted))
}
"""


def pizza_iri(word: str) -> str | None:
    """The pizza a guest's word names -- `"hawaii"` -> `"Hawaiian"`, else None."""
    rows = _rows(Q0_PIZZA_IRI, wanted=word.strip())
    return _local(rows[0]["pizza"]) if rows else None


def topping_iri(word: str) -> str | None:
    """The topping a guest's word names -- `"mushrooms"` -> `"Mushroom"`."""
    rows = _rows(Q8_TOPPING_IRI, wanted=word.strip())
    return _local(rows[0]["topping"]) if rows else None


# =========================================================================
# Q1 / Q2 -- the menu, and one pizza's toppings
# =========================================================================

Q1_ALL_PIZZAS = """
SELECT ?id ?name ?pizza WHERE {
  ?pizza a pz:Pizza ;
         pz:apiId ?id ;
         pz:name  ?name .
}
ORDER BY ?id
"""

Q2_TOPPINGS_OF = """
SELECT ?name (GROUP_CONCAT(?topping; separator=", ") AS ?toppings) WHERE {
  VALUES ?pizza { pz:%s }
  ?pizza pz:name ?name ;
         pz:hasTopping/pz:name ?topping .
}
GROUP BY ?name
"""


def all_pizzas() -> list[dict]:
    """Every pizza the graph knows, in menu order. 22 of them -- not 20.

    Every row carries `local` as well as `name`, and you want `local` whenever
    you are going to ask another question about it. They are not the same and
    one cannot be computed from the other: `"Salami"` is `pz:SalamiPizza`, and
    `"Frutti di Mare"` is `pz:FruttiDiMare` -- a `.replace(" ", "")` gets the
    first wrong and the second's capitals wrong. Carry the thing, do not
    reconstruct it.
    """
    return [{"id": int(row["id"]), "name": row["name"], "local": _local(row["pizza"])}
            for row in _rows(Q1_ALL_PIZZAS)]


def toppings_of(local: str) -> list[str]:
    """The toppings of one pizza, in the order the kitchen lists them."""
    rows = _rows(Q2_TOPPINGS_OF % local)
    return rows[0]["toppings"].split(", ") if rows else []


# =========================================================================
# Q3 / Q4 -- a dietary flag, over the whole menu or over a previous answer
# =========================================================================

Q3_BY_FLAG = """
SELECT ?id ?name ?pizza WHERE {
  %s
  ?pizza a pz:Pizza ; pz:apiId ?id ; pz:name ?name ;
         pz:%s %s .
}
ORDER BY ?id
"""

FLAGS = {                       # what a guest may ask for -> (property, value)
    "vegan":       ("vegan", True),
    "vegetarian":  ("vegetarian", True),
    "milk":        ("containsMilk", False),
    "dairy":       ("containsMilk", False),
    "meat":        ("containsMeat", False),
    "fish":        ("containsFish", False),
    "egg":         ("containsEgg", False),
}


def pizzas_with_flag(prop: str, value: bool, only: list[str] | None = None) -> list[dict]:
    """Q3, and -- with `only` -- Q4.

    `only` is the answer to the *previous* question: pass the local names it
    was about and the new constraint is applied to those and to nothing else.
    That one argument is the whole of this exercise's coreference resolution.
    """
    values = ""
    if only:
        values = "VALUES ?pizza { " + " ".join(f"pz:{name}" for name in only) + " }"
    query = Q3_BY_FLAG % (values, prop, "true" if value else "false")
    return [{"id": int(row["id"]), "name": row["name"], "local": _local(row["pizza"])}
            for row in _rows(query)]


# =========================================================================
# Q5 / Q6 -- what Wikidata added, and everything at once
# =========================================================================

Q5_INVENTED_BY = """
SELECT ?name ?inventor ?year ?source WHERE {
  VALUES ?pizza { pz:%s }
  ?pizza pz:name ?name .
  OPTIONAL { ?pizza pz:inventedBy ?person . ?person rdfs:label ?inventor }
  OPTIONAL { ?pizza pz:inventedIn ?year }
  OPTIONAL { ?pizza prov:wasDerivedFrom ?source }
}
"""

Q6_ABOUT = """
SELECT ?name ?description ?toppings ?vegetarian ?vegan ?inventor ?origin WHERE {
  VALUES ?pizza { pz:%s }
  ?pizza pz:name ?name ; pz:description ?description ;
         pz:vegetarian ?vegetarian ; pz:vegan ?vegan .
  { SELECT ?pizza (GROUP_CONCAT(?t; separator=", ") AS ?toppings)
    WHERE { ?pizza pz:hasTopping/pz:name ?t } GROUP BY ?pizza }
  OPTIONAL { ?pizza pz:inventedBy ?p . ?p rdfs:label ?inventor }
  OPTIONAL { ?pizza pz:countryOfOrigin ?c . ?c rdfs:label ?origin }
}
"""


def invented_by(local: str) -> dict:
    """Inventor, year and the source they came from -- any of them may be None.

    Two of the twenty-two pizzas have an inventor and one has a year. A dict
    of Nones is an *answer* ("nobody wrote that down"), and your node has to
    say it as one.
    """
    rows = _rows(Q5_INVENTED_BY % local)
    return rows[0] if rows else {}


def about(local: str) -> dict:
    """Everything we hold about one pizza: ours required, Wikidata's optional."""
    rows = _rows(Q6_ABOUT % local)
    return rows[0] if rows else {}


# =========================================================================
# Q7 -- the only query that is built, and it is built from IRIs
# =========================================================================


def matching(with_toppings: list[str] | None = None,
             without_toppings: list[str] | None = None,
             flags: list[tuple[str, bool]] | None = None) -> list[dict]:
    """Q7: the pizzas that satisfy every constraint at once.

    One line per constraint, in three shapes -- a wanted topping, an unwanted
    one, a flag. Every extra line makes the result smaller, which is why an
    empty result is not a failure but the sentence "nothing has all of that".

    The arguments are **local names out of `topping_iri()`**, never words a
    guest typed: `matching(["Pineapple"])`, not `matching(["pineapple"])`.
    """
    lines = ["SELECT ?id ?name ?pizza WHERE {",
             "  ?pizza a pz:Pizza ; pz:apiId ?id ; pz:name ?name ."]
    for prop, value in (flags or []):
        lines.append(f"  ?pizza pz:{prop} {'true' if value else 'false'} .")
    for topping in (with_toppings or []):
        lines.append(f"  ?pizza pz:hasTopping pz:{topping} .")
    for topping in (without_toppings or []):
        lines.append(f"  FILTER NOT EXISTS {{ ?pizza pz:hasTopping pz:{topping} }}")
    lines += ["}", "ORDER BY ?id"]
    return [{"id": int(row["id"]), "name": row["name"], "local": _local(row["pizza"])}
            for row in _rows("\n".join(lines))]


# =========================================================================
# the self-test -- the row counts the exercise sheet prints beside each query
# =========================================================================

EXPECTED = [
    ("Q0  'hawaii' is a pizza",            lambda: [pizza_iri("hawaii")],                 1),
    ("Q0  'napoli' is not",                lambda: [x for x in [pizza_iri("napoli")] if x], 0),
    ("Q1  the whole menu",                 all_pizzas,                                    22),
    ("Q2  toppings of the Hawaiian",       lambda: toppings_of("Hawaiian"),                4),
    ("Q3  vegan",                          lambda: pizzas_with_flag("vegan", True),        2),
    ("Q3  vegetarian",                     lambda: pizzas_with_flag("vegetarian", True),  10),
    ("Q3  without milk",                   lambda: pizzas_with_flag("containsMilk", False), 3),
    ("Q3  without meat",                   lambda: pizzas_with_flag("containsMeat", False), 13),
    ("Q4  of the vegetarian ones, without milk",
     lambda: pizzas_with_flag("containsMilk", False,
                              only=[p["local"]
                                    for p in pizzas_with_flag("vegetarian", True)]),       2),
    ("Q5  who invented the Hawaiian",      lambda: [invented_by("Hawaiian")["inventor"]],  1),
    ("Q5  who invented the Rucola",
     lambda: [x for x in [invented_by("Rucola").get("inventor")] if x],                    0),
    ("Q6  everything about the Hawaiian",  lambda: [about("Hawaiian")["origin"]],          1),
    ("Q7  with pineapple",                 lambda: matching(["Pineapple"]),                1),
    ("Q7  vegan",                          lambda: matching(flags=[("vegan", True)]),      2),
    ("Q7  vegetarian with mushrooms",
     lambda: matching(["Mushroom"], flags=[("vegetarian", True)]),                         3),
    ("Q7  vegetarian with aubergine",
     lambda: matching(["Aubergine"], flags=[("vegetarian", True)]),                        2),
    ("Q7  vegan with olives",              lambda: matching(["Olive"], flags=[("vegan", True)]), 0),
    ("Q8  'mushrooms' is a topping",       lambda: [topping_iri("mushrooms")],             1),
    ("Q8  'kale' is not",                  lambda: [x for x in [topping_iri("kale")] if x], 0),
]


def selftest() -> int:
    print(f"{len(graph())} triples from {', '.join(FILES)}\n")
    bad = 0
    for label, call, expected in EXPECTED:
        got = len(call())
        mark = "ok  " if got == expected else "FAIL"
        if got != expected:
            bad += 1
        print(f"   {mark} {label:<45s} {got:>3d} row(s)"
              + ("" if got == expected else f"   expected {expected}"))
    print("\n" + ("all queries answer as the sheet says" if not bad
                  else f"{bad} query/queries disagree with the sheet"))
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    print(__doc__)
