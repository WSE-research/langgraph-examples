"""Regenerate `data/cities.tsv.gz` -- the delivery area of the Pizza API.

    python3 build-cities.py            # fetches every source, writes data/cities.tsv.gz
    python3 build-cities.py GR         # refreshes Greece only, keeps every other row as it is

The file is committed, so the image builds offline and a deployment never
depends on somebody else's API being up. Run this script when the source data
should be refreshed, look at the diff in the line count, and commit the result.
Refresh one country at a time when you can: a refresh of France also moves the
population figures, and with them the order of `GET /city`, which the course
material quotes. Then run `pytest tests/` -- every version of the API promises
some cities by name, and the tests hold it to that.

Sources
-------

* **France**: every commune, from the French government's own geo API
  (<https://geo.api.gouv.fr/communes>, Etalab open licence). ~35 000 communes,
  ~32 700 distinct names -- "all cities of France" taken literally, which is
  what makes the Saint-Etienne exercise able to say "pick your own cities from
  the endpoint" instead of shipping a hand-made list of six.
* **Greece**: every populated place that is a village, a town, a city or the
  seat of an administrative unit, from GeoNames (<https://www.geonames.org>,
  CC BY 4.0) -- ~10 300 distinct names. Added 2026-09-30 for the Athens edition
  of the course, whose running example orders to "5 Ermou, Athens". The name is
  the Latin transliteration a visitor would type (`Agia Paraskevi`, not
  `Agía Paraskeví`), with the English exonym for the handful of large cities
  that have one (`Patras`, `Heraklion`); the other spellings GeoNames knows --
  accented, older transliterations, other languages, Greek script (`Athina`,
  `Athen`, `Αθήνα`) -- go into a fourth column and are accepted as well.
* **Germany**: Leipzig, Halle and Dresden, the delivery area of the HTWK course
  that has used this API since 2024. Their population figures are the 2023
  municipal ones, rounded; they are here so that the three cities do not sort
  to the bottom of a population-ordered listing, not because the API reports
  demography.

Format: one city per line, `name<TAB>country<TAB>population[<TAB>aliases]`,
UTF-8, gzipped; `aliases` is optional and `|`-separated. A flat text file and
not JSON on purpose -- it is read once at startup, and a diff of it has to be
readable in a pull request.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import re
import sys
import unicodedata
import urllib.request
import zipfile
from pathlib import Path

SOURCE_FR = "https://geo.api.gouv.fr/communes?fields=nom,population&format=json"
SOURCE_GR = "https://download.geonames.org/export/dump/GR.zip"
TARGET = Path(__file__).parent / "data" / "cities.tsv.gz"

GERMAN_CITIES = [("Leipzig", 628718), ("Halle", 237790), ("Dresden", 566222)]

# GeoNames feature codes kept for Greece: populated places (PPL) and the seats of
# the capital, regions, regional units and municipalities (PPLC, PPLA, PPLA2,
# PPLA3). Left out: sections of a place (PPLX -- Kolonaki is Athens), abandoned,
# historical, destroyed and religious places.
GREEK_FEATURES = {"PPL", "PPLA", "PPLA2", "PPLA3", "PPLC"}

# GeoNames' ASCII name is a transliteration; for these large cities English has
# its own name, and that is the one a student types.
GREEK_EXONYMS = {
    "Patra": "Patras",
    "Irakleion": "Heraklion",
    "Larisa": "Larissa",
    "Khalandrion": "Chalandri",
    "Zografos": "Zografou",
    "Petroupolis": "Petroupoli",
    "Kerkyra": "Corfu",
}


def fold(text: str) -> str:
    """The comparison key -- the same folding `main.py` applies to a city."""
    stripped = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    return " ".join(stripped.replace("-", " ").split()).casefold()


def _usable_alias(alias: str) -> bool:
    """Latin or Greek script, written like a name, and not an airport code.

    GeoNames also lists romanizations of Chinese, Thai or Arabic names in lower
    case ("ya dian" for Athens); nobody types those into a pizza order.
    """
    letters = [ch for ch in alias if ch.isalpha()]
    if not letters or re.fullmatch(r"[A-Z]{3,4}", alias):
        return False
    scripts = {unicodedata.name(ch, "").split()[0] for ch in letters}
    if not scripts <= {"LATIN", "GREEK"}:
        return False
    return not (scripts == {"LATIN"} and letters[0].islower())


def fetch_french_communes() -> list[tuple[str, int]]:
    with urllib.request.urlopen(SOURCE_FR, timeout=120) as response:
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


def fetch_greek_places() -> list[tuple[str, int, list[str]]]:
    with urllib.request.urlopen(SOURCE_GR, timeout=300) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    text = io.TextIOWrapper(archive.open("GR.txt"), encoding="utf-8")
    best: dict[str, tuple[str, int, list[str]]] = {}
    for row in csv.reader(text, delimiter="\t", quoting=csv.QUOTE_NONE):
        if row[6] != "P" or row[7] not in GREEK_FEATURES:
            continue
        name = GREEK_EXONYMS.get(row[2], row[2])
        population = int(row[14] or 0)
        key = fold(name)
        # Same rule as for the French communes: the area is a set of names, and
        # the largest place of a name (there are thirty villages called Agia
        # Paraskevi) gives it its population and its other spellings.
        if key in best and best[key][1] >= population:
            continue
        spellings = [row[1]] + row[3].split(",")
        aliases, seen = [], {key}
        for alias in spellings:
            alias = alias.strip()
            if alias and _usable_alias(alias) and fold(alias) not in seen:
                seen.add(fold(alias))
                aliases.append(alias)
        best[key] = (name, population, sorted(aliases))
    return sorted(best.values())


def read_rows() -> list[tuple[str, str, int, list[str]]]:
    if not TARGET.exists():
        return []
    rows = []
    with gzip.open(TARGET, "rt", encoding="utf-8") as handle:
        for line in handle:
            name, country, population, *rest = line.rstrip("\n").split("\t")
            aliases = rest[0].split("|") if rest and rest[0] else []
            rows.append((name, country, int(population), aliases))
    return rows


def main(argv: list[str]) -> int:
    only = {code.upper() for code in argv}
    previous = read_rows()
    fetched: dict[str, list[tuple[str, str, int, list[str]]]] = {}
    if not only or "FR" in only:
        fetched["FR"] = [(name, "FR", pop, []) for name, pop in fetch_french_communes()]
    if not only or "GR" in only:
        fetched["GR"] = [(name, "GR", pop, aliases) for name, pop, aliases in fetch_greek_places()]
    if not only or "DE" in only:
        fetched["DE"] = [(name, "DE", pop, []) for name, pop in GERMAN_CITIES]

    # Keep the file in a stable order -- France, Greece, Germany -- whichever
    # country was refreshed, so that a diff shows data and not reshuffling.
    rows = []
    for country in ("FR", "GR", "DE"):
        rows += fetched.get(country, [row for row in previous if row[1] == country])

    TARGET.parent.mkdir(exist_ok=True)
    with gzip.open(TARGET, "wt", encoding="utf-8", newline="\n") as handle:
        for name, country, population, aliases in rows:
            extra = "\t" + "|".join(aliases) if aliases else ""
            handle.write(f"{name}\t{country}\t{population}{extra}\n")

    counts = {c: sum(1 for row in rows if row[1] == c) for c in ("FR", "GR", "DE")}
    print(f"{TARGET}: {len(rows)} cities ({len(previous)} before) -- {counts}, "
          f"{sum(len(row[3]) for row in rows)} further spellings, "
          f"{TARGET.stat().st_size // 1024} KiB compressed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
