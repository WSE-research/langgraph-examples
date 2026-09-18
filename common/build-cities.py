"""Regenerate `data/cities.tsv.gz` -- the delivery area of the Pizza API.

    python3 build-cities.py            # fetches, writes data/cities.tsv.gz, prints what changed

The file is committed, so the image builds offline and a deployment never
depends on somebody else's API being up. Run this script when the source data
should be refreshed, look at the diff in the line count, and commit the result.

Sources
-------

* **France**: every commune, from the French government's own geo API
  (<https://geo.api.gouv.fr/communes>, Etalab open licence). ~35 000 communes,
  ~32 700 distinct names -- "all cities of France" taken literally, which is
  what makes the Saint-Etienne exercise able to say "pick your own cities from
  the endpoint" instead of shipping a hand-made list of six.
* **Germany**: Leipzig, Halle and Dresden, the delivery area of the HTWK course
  that has used this API since 2024. Their population figures are the 2023
  municipal ones, rounded; they are here so that the three cities do not sort
  to the bottom of a population-ordered listing, not because the API reports
  demography.

Format: one city per line, `name<TAB>country<TAB>population`, UTF-8, gzipped.
A flat text file and not JSON on purpose -- it is read once at startup, and a
diff of it has to be readable in a pull request.
"""

from __future__ import annotations

import gzip
import json
import sys
import urllib.request
from pathlib import Path

SOURCE = "https://geo.api.gouv.fr/communes?fields=nom,population&format=json"
TARGET = Path(__file__).parent / "data" / "cities.tsv.gz"

GERMAN_CITIES = [("Leipzig", 628718), ("Halle", 237790), ("Dresden", 566222)]


def fetch_french_communes() -> list[tuple[str, int]]:
    with urllib.request.urlopen(SOURCE, timeout=120) as response:
        communes = json.load(response)
    best: dict[str, int] = {}
    for commune in communes:
        name, population = commune["nom"], int(commune.get("population") or 0)
        # Several communes share a name (there are two Saint-Martin). The
        # delivery area is a set of NAMES -- the API validates an address, it
        # does not disambiguate a municipality -- so the larger one wins the
        # population column and the name appears once.
        if population >= best.get(name, -1):
            best[name] = population
    return sorted(best.items())


def main() -> int:
    previous = 0
    if TARGET.exists():
        with gzip.open(TARGET, "rt", encoding="utf-8") as handle:
            previous = sum(1 for _ in handle)

    rows = [(name, "FR", population) for name, population in fetch_french_communes()]
    rows += [(name, "DE", population) for name, population in GERMAN_CITIES]

    TARGET.parent.mkdir(exist_ok=True)
    with gzip.open(TARGET, "wt", encoding="utf-8", newline="\n") as handle:
        for name, country, population in rows:
            handle.write(f"{name}\t{country}\t{population}\n")

    print(f"{TARGET}: {len(rows)} cities ({previous} before), "
          f"{TARGET.stat().st_size // 1024} KiB compressed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
