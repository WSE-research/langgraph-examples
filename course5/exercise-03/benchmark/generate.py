"""The generator: draw from the catalog, render a sentence, keep what was drawn.

This is the whole idea of Lecture 3, Part B in one file. A pattern is a sentence
with slots; a slot is a **class**; the individual drawn for a slot *is* the
expected value, so nobody ever writes an expected value by hand:

    {ORDER} {ARTICLE?} {PIZZA} to {ADDRESS:STREET}, {ADDRESS:STREETNUMBER}, {ADDRESS:CITY}
      |        |          |                  \\________ one :ADDRESS is drawn for the
      |        |          |                             whole sentence, and each slot
      |        |          |                             renders the part of it it asks for
      |        |          `-- :Margherita, rendered as one of its wordings ("Margarita")
      |        `------------- optional: left out half the time
      `---------------------- wording only, fills nothing

    from benchmark import Catalog
    from benchmark.generate import generate, capacity

    catalog = Catalog()
    capacity(catalog, "address_v2")            # how many DIFFERENT sentences exist
    generate(catalog, "address_v2", n=20, seed=42)

Three properties this generator guarantees, because a benchmark is worthless
without them:

* **reproducible** -- same catalog, same seed, same `n` -> the same cases, in
  the same order. The seed travels with every case.
* **distinct** -- no sentence is drawn twice. If the catalog cannot produce `n`
  different sentences, you get what exists and a warning that names both
  numbers. That warning is the reason the exercise asks you to extend the data.
* **honest about refusals** -- a pizza that is not on the menu and an address in
  a city we do not deliver to are generated on purpose, and their expected
  outcome is `None`: the component must recognise *nothing*. `catalog.servable()`
  decides, from the flags in the graph (`:onMenu`, `:deliverable`).

The generator produces **inputs only**. An expected value is drawn together with
its surface form -- never invented, never asked of a model.

Command line::

    python -m benchmark.generate --benchmark address_v2 -n 50 --seed 42
    python -m benchmark.generate --benchmark order_v2 -n 100 --out benchmark/order_v2.jsonl
    python -m benchmark.generate --capacity            # what the catalog can produce today
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Iterable

from benchmark.catalog import Catalog

SLOT = re.compile(r"{(\w+)(?::(\w+))?(\??)}")      # {CLASS}, {CLASS:PART}, {CLASS?}

#: How many draws we are willing to make per requested case before we accept
#: that the catalog has run out of different sentences. 40 is generous: the
#: birthday problem, not the catalog, is what makes the last few cases slow.
ATTEMPTS_PER_CASE = 40

BENCHMARKS = ("address_v2", "pizza_v2", "order_v2")


def _default_warning(message: str) -> None:
    """Where a warning goes when the caller does not say.

    Python's own channel, so `pytest.warns` sees it and a library user is not
    surprised by something printing to their screen. The scripts in this
    repository pass `on_warning=log.warn` instead, because a student staring at
    a terminal should see the sentence in yellow, not in a stack-trace footer.
    """
    import warnings

    warnings.warn(message, stacklevel=3)


# ---------------------------------------------------------------------------
# What the catalog can produce
# ---------------------------------------------------------------------------


def capacity(catalog: Catalog, benchmark: str) -> int:
    """How many *different* sentences this benchmark can produce today.

    Per pattern: one individual is drawn per slot class, so the pattern's share
    is the product over its classes of "how many renderings that class offers",
    and the benchmark is the sum over its patterns. An optional slot offers one
    rendering more: leaving it out.

    This number is the answer to "why did I ask for 200 cases and get 96?" --
    and the number that grows when you add a wording, a street or a pizza.
    """
    return sum(_pattern_capacity(catalog, template) for template in catalog.patterns(benchmark))


def _pattern_capacity(catalog: Catalog, template: str) -> int:
    total = 1
    for cls, parts, optional in _slots_by_class(template):
        renderings = 0
        for individual in catalog.instances(cls):
            if parts:                                      # {ADDRESS:STREET} + {ADDRESS:CITY}: one address, several parts
                combinations = 1
                for part_class in parts:
                    part = catalog.part(individual, part_class)
                    combinations *= len(catalog.labels(part)) if part is not None else 0
                renderings += combinations
            else:
                renderings += len(catalog.labels(individual))
        total *= renderings + 1 if optional else renderings
    return total


def _slots_by_class(template: str) -> list[tuple[str, tuple[str, ...], bool]]:
    """The slots of a template, grouped by class: (class, part classes, optional).

    Grouping is what makes `{ADDRESS:STREET}` and `{ADDRESS:CITY}` one draw and
    not two -- which is what keeps a street and a city in the same town.
    """
    grouped: dict[str, list[str]] = {}
    optional: dict[str, bool] = {}
    for cls, part, mark in SLOT.findall(template):
        grouped.setdefault(cls, [])
        if part:
            grouped[cls].append(part)
        optional[cls] = optional.get(cls, False) or bool(mark)
    return [(cls, tuple(parts), optional[cls]) for cls, parts in grouped.items()]


# ---------------------------------------------------------------------------
# Drawing cases
# ---------------------------------------------------------------------------


def generate(catalog: Catalog, benchmark: str, n: int = 20, seed: int = 42,
             on_warning=None) -> list[dict]:
    """`n` distinct test cases for `benchmark`, drawn with `seed`.

    Every row is a complete, self-contained test case::

        {"id": "address_v2-0003",
         "input": "Bring it to R. Michelet, no 5, St. Etienne",
         "benchmark": "address_v2", "pattern": "{DELIVER} {ADDRESS:STREET}, ...",
         "exercises": ["address_recognition"],
         "expected": {"address": {"street": "Rue Michelet", ...}},   # None = must recognise nothing
         "accepted": {"address": {"street": ["R. Michelet", "Rue Michelet", ...], ...}},
         "servable": true, "source": "generated", "seed": 42}

    `expected` is the canonical value from the graph; `accepted` lists the
    wordings that count as the same answer, because a component copies what the
    user wrote ("R. Michelet") and the graph stores what it means ("Rue
    Michelet"). An evaluator that ignores `accepted` measures spelling.
    """
    warn = on_warning or _default_warning
    templates = catalog.patterns(benchmark)
    if not templates:
        raise ValueError(f"no pattern in the graph for benchmark {benchmark!r} -- "
                         f"known: {', '.join(sorted(_known_benchmarks(catalog)))}")

    available = capacity(catalog, benchmark)
    if n > available:
        warn(f"{benchmark}: {n} cases requested, but the catalog can only produce {available} "
              f"different sentences. Extend benchmark/data/catalog.ttl -- one more wording, "
              f"one more street, one more city -- and run this again.")

    rnd = random.Random(seed)
    fills = catalog.fills()
    rows: list[dict] = []
    seen: set[str] = set()
    for _ in range(max(n, 0) * ATTEMPTS_PER_CASE):
        if len(rows) >= n:
            break
        template = rnd.choice(templates)
        utterance, drawn = _render(catalog, template, rnd)
        if utterance in seen:
            continue                                        # distinct: a sentence is drawn once
        seen.add(utterance)
        rows.append(_case(catalog, benchmark, template, utterance, drawn, fills,
                          index=len(rows), seed=seed))

    if len(rows) < n:
        warn(f"{benchmark}: asked for {n} cases, produced {len(rows)}. "
              f"The catalog offers {available} different sentences in total.")
    return rows


def _render(catalog: Catalog, template: str, rnd: random.Random) -> tuple[str, dict]:
    """One sentence, plus the individuals it was built from."""
    utterance, drawn = template, {}
    for cls, part, optional in SLOT.findall(template):
        if optional and rnd.random() < 0.5:                 # optional: leave it out
            utterance = utterance.replace("{%s?} " % cls, "")
            continue
        individual = drawn.setdefault(cls, rnd.choice(catalog.instances(cls)))
        target = catalog.part(individual, part) if part else individual
        slot = "{%s%s%s}" % (cls, ":" + part if part else "", optional)
        utterance = utterance.replace(slot, rnd.choice(catalog.labels(target)))
    return _tidy(utterance), drawn


def _tidy(utterance: str) -> str:
    """What a chat window would have delivered: single spaces, no space before a comma.

    A wording in the catalog may carry a stray space (`"Rue Michelet "` is in
    there on purpose, as a data-hygiene case). Rendering it must not produce
    `"Rue Michelet , 5"` -- nobody types that, so measuring it measures nothing.
    """
    return " ".join(utterance.split()).replace(" ,", ",").replace(" .", ".")


def _case(catalog: Catalog, benchmark: str, template: str, utterance: str,
          drawn: dict, fills: dict[str, str], index: int, seed: int) -> dict:
    expected, accepted = {}, {}
    for cls, individual in drawn.items():
        field = fills.get(cls)
        if field is None:                                   # wording-only slot: fills nothing
            continue
        if catalog.servable(individual):
            expected[field] = catalog.expected(individual)
            accepted[field] = _accepted(catalog, individual)
        else:
            expected[field] = None                          # the component must recognise nothing
            accepted[field] = None
    return {
        "id": f"{benchmark}-{index:04d}",
        "input": utterance,
        "benchmark": benchmark,
        "pattern": template,
        "exercises": _exercises(catalog, template),
        "expected": expected,
        "accepted": accepted,
        "servable": all(catalog.servable(i) for i in drawn.values()),
        "source": "generated",
        "seed": seed,
    }


def _accepted(catalog: Catalog, individual) -> dict | None:
    """Every wording that counts as this individual -- per field, if it has parts.

    A component copies what the user wrote, so "R. Michelet" and "Rue Michelet"
    are the same answer. A scalar value (a pizza id) has no spellings and gets
    None: there is nothing to be lenient about.
    """
    if not isinstance(catalog.expected(individual), dict):
        return None
    fields: dict[str, list[str]] = {}
    for _, part in catalog.g.predicate_objects(individual):
        field = catalog.field_of(part)
        if field is not None:
            wordings = {catalog.name(part), *catalog.labels(part)} - {None}
            fields[field] = sorted(wordings)
    return fields


def _exercises(catalog: Catalog, template: str) -> list[str]:
    """Which components a case of this pattern measures, as the graph says."""
    from benchmark.catalog import TG
    from rdflib import Literal

    for pattern in catalog.g.subjects(TG.template, Literal(template)):
        return sorted(str(o) for o in catalog.g.objects(pattern, TG.exercises))
    return []


def _known_benchmarks(catalog: Catalog) -> set[str]:
    from benchmark.catalog import TG

    return {str(o) for o in catalog.g.objects(None, TG.benchmark)}


# ---------------------------------------------------------------------------
# The artifact
# ---------------------------------------------------------------------------


def write_jsonl(path: Path | str, rows: Iterable[dict]) -> Path:
    """One case per line -- a diffable, committable artifact."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return target


def read_jsonl(path: Path | str) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    import argparse

    from pizzabot import log

    parser = argparse.ArgumentParser(description="Generate test cases from the knowledge graph.")
    parser.add_argument("--benchmark", default="address_v2", choices=list(BENCHMARKS),
                        help="which benchmark to draw from (default: address_v2)")
    parser.add_argument("-n", "--cases", type=int, default=20, help="how many cases (default: 20)")
    parser.add_argument("--seed", type=int, default=42, help="the randomizer seed (default: 42)")
    parser.add_argument("--data", default=None, help="a .ttl file or a directory of them (default: benchmark/data/)")
    parser.add_argument("--out", default=None, help="write the cases as JSONL to this file")
    parser.add_argument("--capacity", action="store_true", help="only report what the catalog can produce")
    arguments = parser.parse_args()

    catalog = Catalog(arguments.data) if arguments.data else Catalog()
    log.title(f"Test-case generator -- {catalog!r}")

    if arguments.capacity:
        for benchmark in BENCHMARKS:
            log.result(f"{benchmark:<12} {capacity(catalog, benchmark):>8} different sentences "
                       f"from {len(catalog.patterns(benchmark))} pattern(s)")
        return

    rows = generate(catalog, arguments.benchmark, n=arguments.cases, seed=arguments.seed,
                    on_warning=log.warn)
    log.plain()
    for row in rows[:10]:
        log.detail(f"{row['input']}\n            -> {row['expected']}", indent="  ")
    if len(rows) > 10:
        log.detail(f"... and {len(rows) - 10} more", indent="  ")
    log.plain()
    log.result(f"{len(rows)} case(s) for {arguments.benchmark}, seed {arguments.seed}, "
               f"{sum(1 for r in rows if not r['servable'])} of them refusals")
    if arguments.out:
        written = write_jsonl(arguments.out, rows)
        log.ok(f"written: {written}")


if __name__ == "__main__":
    main()
