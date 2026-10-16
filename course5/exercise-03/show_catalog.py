#!/usr/bin/env python3
"""Print what the benchmark catalog currently contains.

    python show_catalog.py

The one command to run after extending `benchmark/data/*.ttl`: it says how
many things of each kind are in the graph and what a drawn individual means
for the expected output. `pytest -q` then says whether it is still consistent.
"""

from benchmark import Catalog


def main() -> None:
    catalog = Catalog()
    print(f"{catalog}\n")

    for cls in ("PIZZA", "ADDRESS", "STREET", "STREETNUMBER", "CITY", "ORDER", "DELIVER", "ARTICLE"):
        individuals = catalog.instances(cls)
        wordings = sum(len(catalog.labels(i)) for i in individuals)
        plural = "individual " if len(individuals) == 1 else "individuals"
        print(f"  :{cls:<13} {len(individuals):>3} {plural}, {wordings:>3} wordings")

    print("\n  patterns")
    for benchmark in sorted({str(row.benchmark) for row in catalog.query(
            "PREFIX tg: <http://example.org/testgen/> "
            "SELECT DISTINCT ?benchmark WHERE { ?p tg:benchmark ?benchmark }")}):
        for template in catalog.patterns(benchmark):
            print(f"    {benchmark:<12} {template}")

    print("\n  what a drawn individual means")
    for cls, field in sorted(catalog.fills().items()):
        example = catalog.instances(cls)[0]
        print(f"    :{cls:<8} fills {field:<10} e.g. {catalog.expected(example)}")


if __name__ == "__main__":
    main()
