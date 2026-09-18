"""The fetcher: the benchmark catalog, behind an easy API.

The data is a knowledge graph (`benchmark/data/*.ttl`) served in-process by
RDFlib -- no triplestore, no server, no network, so the tests run offline and
on every machine in the room. The SPARQL lives in this module; nothing above
it writes a query.

    catalog = Catalog()
    catalog.patterns("address_v2")          # ['{DELIVER} {ADDRESS:STREET}, ...']
    catalog.instances("PIZZA")              # [rdflib.URIRef('...Margherita'), ...]
    catalog.labels(pizza)                   # ['Margarita', 'Margherita', ...]
    catalog.part(address, "CITY")           # rdflib.URIRef('...saintEtienne')
    catalog.expected(pizza)                 # 1
    catalog.expected(address)               # {'street': ..., 'city': ...}
    catalog.servable(pizza)                 # False -> the right answer is "nothing"

Extending the data means editing Turtle, never this file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.term import Node

PZ = Namespace("http://example.org/pizza/")
TG = Namespace("http://example.org/testgen/")

DATA_DIR = Path(__file__).parent / "data"
QUERY_DIR = Path(__file__).parent / "queries"


def _query(name: str) -> str:
    return (QUERY_DIR / f"{name}.sparql").read_text(encoding="utf-8")


PATTERN_Q = _query("pattern")
INSTANCE_Q = _query("instances")
PART_Q = _query("part")


class Catalog:
    """Read-only access to the benchmark catalog."""

    def __init__(self, source: Path | str | Iterable[Path | str] = DATA_DIR) -> None:
        self.sources = self._resolve(source)
        if not self.sources:
            raise FileNotFoundError(f"no Turtle file found in {source}")
        self.g = Graph()
        for path in self.sources:
            self.g.parse(str(path), format="turtle")
        # The graph is read-only, so every answer can be remembered. Without
        # this, a generator drawing a few thousand sentences would run the same
        # three SPARQL queries a few thousand times -- the data has not changed
        # in between. Parse once, ask once, answer from memory after that.
        self._cache: dict[tuple, object] = {}

    def _cached(self, key: tuple, compute):
        if key not in self._cache:
            self._cache[key] = compute()
        return self._cache[key]

    # ---- the four methods a generator needs --------------------------------

    def patterns(self, benchmark: str) -> list[str]:
        """The sentence patterns of one benchmark, as written in the graph."""
        def compute():
            rows = self._q(PATTERN_Q, benchmark=Literal(benchmark))
            return sorted(str(row.template) for row in rows)

        return self._cached(("patterns", benchmark), compute)

    def instances(self, cls: str) -> list[URIRef]:
        """Every individual typed with the slot class `cls` (e.g. "PIZZA")."""
        def compute():
            rows = self._q(INSTANCE_Q, **{"class": PZ[cls]})
            return sorted({row.individual for row in rows})

        return self._cached(("instances", cls), compute)

    def part(self, instance: Node, cls: str) -> URIRef | None:
        """The part of `instance` typed `cls` -- {ADDRESS:STREET} on :a1 -> :st1."""
        def compute():
            rows = list(self._q(PART_Q, instance=instance, **{"class": PZ[cls]}))
            return rows[0].part if rows else None

        return self._cached(("part", instance, cls), compute)

    def labels(self, resource: Node) -> list[str]:
        """Every wording this resource may be rendered with."""
        return self._cached(("labels", resource),
                            lambda: sorted(str(o) for o in self.g.objects(resource, RDFS.label)))

    # ---- what a drawn individual means for the expected output -------------

    def fills(self) -> dict[str, str]:
        """Slot class -> the state field it fills: {"PIZZA": "pizza_id", ...}."""
        return {self._local(s): str(o) for s, o in self.g.subject_objects(TG.fills)}

    def expected(self, resource: Node):
        """The canonical value a component must produce for this individual.

        A scalar class declares `tg:value` (`:PIZZA tg:value :pizzaId`) and
        yields that value; a structured one yields a record built from the
        parts whose classes declare `tg:field`.
        """
        value_property = self._declared(resource, TG.value)
        if value_property is not None:
            value = self.g.value(resource, value_property)
            return value.toPython() if isinstance(value, Literal) else value
        record = {}
        for _, part in self.g.predicate_objects(resource):
            field = self._declared(part, TG.field)
            if field is not None:
                record[str(field)] = self.name(part)
        return record

    def field_of(self, resource: Node) -> str | None:
        """The key this resource contributes to a structured record, or None.

        `:st1` is typed `:STREET`, and `:STREET tg:field "street"` -- so this
        street is the "street" of the address that owns it. The generator needs
        it to list the wordings a component may answer with, per field.
        """
        field = self._declared(resource, TG.field)
        return str(field) if field is not None else None

    def servable(self, resource: Node) -> bool:
        """Can the service actually serve this individual -- and everything in it?

        A class may declare which property carries its availability flag
        (`:PIZZA tg:available :onMenu`, `:CITY tg:available :deliverable`). A
        pizza that is not on the menu and an address whose city is outside the
        delivery area are both perfectly good sentences whose correct outcome is
        *nothing recognised* -- this method is how the generator knows which of
        the two expected outcomes a drawn individual deserves.

        Structured individuals inherit: an :ADDRESS is servable when every part
        it links to is, because the city is what the service refuses.
        """
        flag_property = self._declared(resource, TG.available)
        if flag_property is not None:
            flag = self.g.value(resource, flag_property)
            if flag is None or not flag.toPython():
                return False
        for _, part in self.g.predicate_objects(resource):
            if isinstance(part, URIRef) and part != resource and list(self.g.objects(part, RDF.type)):
                if self._declared(part, TG.available) is not None and not self.servable(part):
                    return False
        return True

    def name(self, resource: Node) -> str | None:
        """The canonical spelling of a resource (`:name`), not one of its labels."""
        value = self.g.value(resource, PZ.name)
        return str(value) if value is not None else None

    # ---- serving the graph itself ------------------------------------------

    def serialize(self, fmt: str = "turtle") -> str:
        """The whole graph, for a test environment that wants to serve it."""
        return self.g.serialize(format=fmt)

    def query(self, sparql: str, **bindings):
        """Escape hatch: run your own SPARQL against the catalog."""
        return self._q(sparql, **bindings)

    def classes_of(self, resource: Node) -> list[str]:
        return sorted(self._local(o) for o in self.g.objects(resource, RDF.type))

    def __len__(self) -> int:
        return len(self.g)

    def __repr__(self) -> str:
        return f"<Catalog {len(self.g)} triples from {len(self.sources)} file(s)>"

    # ---- internals ----------------------------------------------------------

    def _q(self, sparql: str, **bindings):
        return self.g.query(sparql, initBindings=bindings)

    def _declared(self, resource: Node, prop: URIRef):
        """The value of `prop` declared for any class of `resource`."""
        for cls in self.g.objects(resource, RDF.type):
            declared = self.g.value(cls, prop)
            if declared is not None:
                return declared
        return None

    @staticmethod
    def _local(uri: Node) -> str:
        return str(uri).rsplit("/", 1)[-1].rsplit("#", 1)[-1]

    @staticmethod
    def _resolve(source) -> list[Path]:
        if isinstance(source, (str, Path)):
            path = Path(source)
            return sorted(path.glob("*.ttl")) if path.is_dir() else [path]
        return [Path(item) for item in source]
